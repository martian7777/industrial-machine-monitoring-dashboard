"""Analytics core: rolling z-score anomaly detection + predictive maintenance.

These are intentionally lightweight, dependency-free statistical models so the
whole stack runs without a training pipeline. They are deterministic given the
recent telemetry window and produce explainable outputs.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Anomaly, MaintenancePrediction, Machine, TelemetryRaw

settings = get_settings()

SENSORS = ("temperature", "vibration", "pressure", "energy_use")

# Hard physical limits — independent of statistics. (lo, hi) per sensor.
HARD_LIMITS: dict[str, tuple[float, float]] = {
    "temperature": (5.0, 95.0),    # deg C
    "vibration": (0.0, 11.0),      # mm/s RMS (ISO 10816 "danger" territory)
    "pressure": (0.5, 12.0),       # bar
    "energy_use": (0.0, 1000.0),   # kWh interval guard
}


@dataclass
class DetectedAnomaly:
    sensor: str
    value: float
    z_score: float | None
    severity: str
    message: str


def _severity_for_z(z: float) -> str | None:
    az = abs(z)
    if az >= settings.zscore_critical:
        return "critical"
    if az >= settings.zscore_warning:
        return "warning"
    return None


def detect_anomalies(
    db: Session, machine_id: int, reading: dict[str, float]
) -> list[DetectedAnomaly]:
    """Detect anomalies for a single reading using rolling z-score + hard limits.

    The rolling window is the last N readings for this machine (excluding the
    one just inserted, which the caller passes via ``reading``).
    """
    window = settings.zscore_window
    rows = (
        db.execute(
            select(
                TelemetryRaw.temperature,
                TelemetryRaw.vibration,
                TelemetryRaw.pressure,
                TelemetryRaw.energy_use,
            )
            .where(TelemetryRaw.machine_id == machine_id)
            .order_by(TelemetryRaw.ts.desc())
            .limit(window)
        )
        .all()
    )

    detected: list[DetectedAnomaly] = []

    for idx, sensor in enumerate(SENSORS):
        value = float(reading[sensor])
        history = [float(r[idx]) for r in rows]

        # 1) Statistical (rolling z-score) — needs enough history with spread.
        z = None
        severity = None
        if len(history) >= 10:
            mean = statistics.fmean(history)
            stdev = statistics.pstdev(history)
            if stdev > 1e-6:
                z = (value - mean) / stdev
                severity = _severity_for_z(z)

        # 2) Hard physical limits always override toward critical.
        lo, hi = HARD_LIMITS[sensor]
        breached_limit = value < lo or value > hi
        if breached_limit:
            severity = "critical"

        if severity:
            direction = "high" if (z is None or z >= 0) else "low"
            if breached_limit:
                msg = (
                    f"{sensor.replace('_', ' ').title()} out of safe range: "
                    f"{value:.2f} (limit {lo}-{hi})"
                )
            else:
                msg = (
                    f"{sensor.replace('_', ' ').title()} {direction} anomaly: "
                    f"{value:.2f} (z={z:.2f})"
                )
            detected.append(
                DetectedAnomaly(
                    sensor=sensor,
                    value=value,
                    z_score=round(z, 3) if z is not None else None,
                    severity=severity,
                    message=msg,
                )
            )

    return detected


def persist_anomalies(
    db: Session,
    machine_id: int,
    telemetry_id: int,
    ts: datetime,
    detected: list[DetectedAnomaly],
) -> list[Anomaly]:
    saved: list[Anomaly] = []
    for d in detected:
        row = Anomaly(
            machine_id=machine_id,
            telemetry_id=telemetry_id,
            ts=ts,
            sensor=d.sensor,
            value=d.value,
            z_score=d.z_score,
            severity=d.severity,
            message=d.message,
        )
        db.add(row)
        saved.append(row)
    return saved


# ---------------------------------------------------------------------------
#  Predictive maintenance
# ---------------------------------------------------------------------------

# Nominal design life per machine type, in operating hours.
DESIGN_LIFE_HOURS: dict[str, float] = {
    "CNC Mill": 60000,
    "Robotic Arm": 50000,
    "Conveyor": 40000,
    "Hydraulic Pump": 45000,
    "Air Compressor": 50000,
    "Injection Molder": 70000,
    "Furnace": 80000,
}
DEFAULT_DESIGN_LIFE = 50000.0


def compute_prediction(
    db: Session, machine: Machine, latest: TelemetryRaw
) -> MaintenancePrediction:
    """Estimate health, risk score and Remaining Useful Life (RUL).

    Approach (explainable):
      * base wear from operating hours vs design life
      * recent anomaly pressure (24h window, severity-weighted)
      * instantaneous stress from temperature & vibration headroom
    """
    design_life = DESIGN_LIFE_HOURS.get(machine.type, DEFAULT_DESIGN_LIFE)
    op_hours = float(latest.operating_hours or 0.0)

    # --- wear from age/usage (0..1) ---
    wear = min(op_hours / design_life, 1.0)

    # --- recent anomaly pressure (last 24h) ---
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    recent = (
        db.execute(
            select(Anomaly.severity).where(
                Anomaly.machine_id == machine.id, Anomaly.ts >= since
            )
        )
        .scalars()
        .all()
    )
    weighted = sum(3 if s == "critical" else 1 for s in recent)
    # Saturate: ~15 weighted points => full anomaly pressure.
    anomaly_pressure = min(weighted / 15.0, 1.0)

    # --- instantaneous stress from temperature & vibration headroom ---
    temp = float(latest.temperature)
    vib = float(latest.vibration)
    temp_stress = max(0.0, (temp - 60.0) / 35.0)        # >60C starts to count, 95C = full
    vib_stress = max(0.0, (vib - 4.5) / 6.5)            # >4.5 mm/s counts, 11 = full
    stress = min(max(temp_stress, vib_stress), 1.0)

    # --- blended risk (0..100) ---
    risk = 100.0 * min(
        0.45 * wear + 0.35 * anomaly_pressure + 0.20 * stress, 1.0
    )
    health = max(0.0, 100.0 - risk)

    # --- RUL: remaining design hours discounted by current condition ---
    remaining_base = max(design_life - op_hours, 0.0)
    condition_factor = max(0.05, 1.0 - 0.5 * (anomaly_pressure + stress) / 2.0 - 0.5 * stress)
    rul_hours = round(remaining_base * condition_factor, 1)

    # --- next recommended maintenance date ---
    # Assume ~16 operating hours/day; schedule sooner as risk rises.
    if risk >= 75:
        days_ahead = 2
    elif risk >= 50:
        days_ahead = 7
    elif risk >= 25:
        days_ahead = 30
    else:
        days_ahead = 90
    next_date = date.today() + timedelta(days=days_ahead)

    # --- explain the top drivers ---
    drivers = []
    if wear >= 0.6:
        drivers.append(f"high usage ({op_hours:.0f}h / {design_life:.0f}h)")
    if anomaly_pressure >= 0.3:
        drivers.append(f"{len(recent)} anomalies in 24h")
    if temp_stress >= 0.3:
        drivers.append(f"temp stress {temp:.0f}C")
    if vib_stress >= 0.3:
        drivers.append(f"vibration {vib:.1f}mm/s")
    drivers_text = "; ".join(drivers) if drivers else "nominal operation"

    return MaintenancePrediction(
        machine_id=machine.id,
        ts=datetime.now(timezone.utc),
        maintenance_risk_score=round(risk, 2),
        rul_hours=rul_hours,
        next_recommended_maintenance=next_date,
        health_index=round(health, 2),
        drivers=drivers_text,
    )


def derive_status(risk: float, detected: list[DetectedAnomaly]) -> str:
    """Map current risk + live anomalies to a machine operating status."""
    if any(d.severity == "critical" for d in detected) or risk >= 80:
        return "fault"
    if risk >= 55:
        return "maintenance"
    return "running"
