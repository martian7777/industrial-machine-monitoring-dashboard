"""FastAPI application: telemetry ingestion, dashboards API, real-time WebSocket."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import analytics
from .config import get_settings
from .database import get_db
from .models import Anomaly, Machine, MaintenancePrediction, TelemetryRaw
from .schemas import (
    AnomalyOut,
    IngestResult,
    MachineOut,
    MachineStatus,
    Overview,
    PredictionOut,
    TelemetryIn,
    TelemetryOut,
)
from .seed import init_and_seed
from .ws import manager

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auto_init_db:
        try:
            added = init_and_seed()
            print(f"[startup] DB ready. Seeded {added} new machine(s).")
        except Exception as exc:  # don't crash if DB is briefly unavailable
            print(f"[startup] WARNING: could not init/seed DB: {exc}")
    yield


app = FastAPI(
    title="Industrial Machine Monitoring API",
    description="Telemetry ingestion, anomaly detection, predictive maintenance & live stream.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
#  Health
# ---------------------------------------------------------------------------
@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "ws_clients": manager.count, "time": datetime.now(timezone.utc)}


# ---------------------------------------------------------------------------
#  Telemetry ingestion (called by the simulator / edge devices)
# ---------------------------------------------------------------------------
@app.post("/api/telemetry", response_model=IngestResult, tags=["telemetry"])
async def ingest_telemetry(payload: TelemetryIn, db: Session = Depends(get_db)) -> IngestResult:
    machine = db.get(Machine, payload.machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail=f"Unknown machine_id {payload.machine_id}")

    ts = payload.ts or datetime.now(timezone.utc)
    reading = {
        "temperature": payload.temperature,
        "vibration": payload.vibration,
        "pressure": payload.pressure,
        "energy_use": payload.energy_use,
    }

    # 1) anomaly detection against rolling window (before inserting this row)
    detected = analytics.detect_anomalies(db, machine.id, reading)

    # 2) persist the raw reading
    row = TelemetryRaw(
        machine_id=machine.id,
        ts=ts,
        temperature=payload.temperature,
        vibration=payload.vibration,
        pressure=payload.pressure,
        energy_use=payload.energy_use,
        rpm=payload.rpm,
        operating_hours=payload.operating_hours,
    )
    db.add(row)
    db.flush()  # assign row.id

    # 3) persist anomalies
    saved_anoms = analytics.persist_anomalies(db, machine.id, row.id, ts, detected)

    # 4) predictive maintenance + status update
    prediction = analytics.compute_prediction(db, machine, row)
    db.add(prediction)
    machine.status = analytics.derive_status(float(prediction.maintenance_risk_score), detected)

    db.commit()
    db.refresh(row)
    for a in saved_anoms:
        db.refresh(a)
    db.refresh(prediction)

    result = IngestResult(
        telemetry_id=row.id,
        anomalies=[AnomalyOut.model_validate(a) for a in saved_anoms],
        prediction=PredictionOut.model_validate(prediction),
    )

    # 5) broadcast to live dashboard clients
    await manager.broadcast(
        {
            "type": "telemetry",
            "machine_id": machine.id,
            "machine_code": machine.code,
            "status": machine.status,
            "reading": {
                "id": row.id,
                "ts": ts,
                "temperature": payload.temperature,
                "vibration": payload.vibration,
                "pressure": payload.pressure,
                "energy_use": payload.energy_use,
                "rpm": payload.rpm,
            },
            "prediction": {
                "risk": float(prediction.maintenance_risk_score),
                "health": float(prediction.health_index),
                "rul_hours": float(prediction.rul_hours),
            },
            "anomalies": [
                {"sensor": a.sensor, "severity": a.severity, "message": a.message, "value": float(a.value)}
                for a in saved_anoms
            ],
        }
    )
    return result


# ---------------------------------------------------------------------------
#  Machines & status
# ---------------------------------------------------------------------------
@app.get("/api/machines", response_model=list[MachineOut], tags=["machines"])
def list_machines(db: Session = Depends(get_db)) -> list[Machine]:
    return db.execute(select(Machine).order_by(Machine.id)).scalars().all()


@app.get("/api/machines/status", response_model=list[MachineStatus], tags=["machines"])
def machines_status(db: Session = Depends(get_db)) -> list[MachineStatus]:
    machines = db.execute(select(Machine).order_by(Machine.id)).scalars().all()
    out: list[MachineStatus] = []
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    for m in machines:
        latest = db.execute(
            select(TelemetryRaw)
            .where(TelemetryRaw.machine_id == m.id)
            .order_by(TelemetryRaw.ts.desc())
            .limit(1)
        ).scalar_one_or_none()
        pred = db.execute(
            select(MaintenancePrediction)
            .where(MaintenancePrediction.machine_id == m.id)
            .order_by(MaintenancePrediction.ts.desc())
            .limit(1)
        ).scalar_one_or_none()
        open_count = db.execute(
            select(func.count(Anomaly.id)).where(
                Anomaly.machine_id == m.id, Anomaly.ts >= since
            )
        ).scalar_one()
        out.append(
            MachineStatus(
                machine=MachineOut.model_validate(m),
                latest=TelemetryOut.model_validate(latest) if latest else None,
                prediction=PredictionOut.model_validate(pred) if pred else None,
                open_anomalies=open_count,
            )
        )
    return out


@app.get("/api/machines/{machine_id}/telemetry", response_model=list[TelemetryOut], tags=["telemetry"])
def machine_telemetry(
    machine_id: int,
    limit: int = Query(100, ge=1, le=2000),
    db: Session = Depends(get_db),
) -> list[TelemetryRaw]:
    if db.get(Machine, machine_id) is None:
        raise HTTPException(status_code=404, detail="Unknown machine")
    rows = db.execute(
        select(TelemetryRaw)
        .where(TelemetryRaw.machine_id == machine_id)
        .order_by(TelemetryRaw.ts.desc())
        .limit(limit)
    ).scalars().all()
    return list(reversed(rows))  # chronological for charts


# ---------------------------------------------------------------------------
#  Anomalies & maintenance
# ---------------------------------------------------------------------------
@app.get("/api/anomalies", response_model=list[AnomalyOut], tags=["anomalies"])
def list_anomalies(
    limit: int = Query(50, ge=1, le=500),
    machine_id: int | None = None,
    severity: str | None = None,
    db: Session = Depends(get_db),
) -> list[Anomaly]:
    stmt = select(Anomaly).order_by(Anomaly.ts.desc()).limit(limit)
    if machine_id is not None:
        stmt = stmt.where(Anomaly.machine_id == machine_id)
    if severity is not None:
        stmt = stmt.where(Anomaly.severity == severity)
    return db.execute(stmt).scalars().all()


@app.get("/api/maintenance", response_model=list[PredictionOut], tags=["maintenance"])
def maintenance_report(db: Session = Depends(get_db)) -> list[PredictionOut]:
    """Latest maintenance prediction per machine, highest risk first."""
    machines = db.execute(select(Machine.id)).scalars().all()
    preds: list[PredictionOut] = []
    for mid in machines:
        p = db.execute(
            select(MaintenancePrediction)
            .where(MaintenancePrediction.machine_id == mid)
            .order_by(MaintenancePrediction.ts.desc())
            .limit(1)
        ).scalar_one_or_none()
        if p:
            preds.append(PredictionOut.model_validate(p))
    preds.sort(key=lambda x: x.maintenance_risk_score, reverse=True)
    return preds


# ---------------------------------------------------------------------------
#  Overview / KPIs
# ---------------------------------------------------------------------------
@app.get("/api/overview", response_model=Overview, tags=["overview"])
def overview(db: Session = Depends(get_db)) -> Overview:
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    machines = db.execute(select(Machine)).scalars().all()
    machine_count = len(machines)

    status_counts = {"running": 0, "fault": 0, "maintenance": 0, "idle": 0}
    for m in machines:
        status_counts[m.status] = status_counts.get(m.status, 0) + 1

    # latest health per machine
    healths: list[float] = []
    high_risk = 0
    for m in machines:
        p = db.execute(
            select(MaintenancePrediction)
            .where(MaintenancePrediction.machine_id == m.id)
            .order_by(MaintenancePrediction.ts.desc())
            .limit(1)
        ).scalar_one_or_none()
        if p:
            healths.append(float(p.health_index))
            if float(p.maintenance_risk_score) >= 55:
                high_risk += 1
    avg_health = round(sum(healths) / len(healths), 1) if healths else 100.0

    anomalies_24h = db.execute(
        select(func.count(Anomaly.id)).where(Anomaly.ts >= since)
    ).scalar_one()
    critical_24h = db.execute(
        select(func.count(Anomaly.id)).where(
            Anomaly.ts >= since, Anomaly.severity == "critical"
        )
    ).scalar_one()
    total_energy = db.execute(
        select(func.coalesce(func.sum(TelemetryRaw.energy_use), 0)).where(
            TelemetryRaw.ts >= since
        )
    ).scalar_one()

    # Simplified OEE proxy: availability from running ratio, performance & quality
    # degraded by anomaly load. Real OEE needs cycle/quality data.
    availability = status_counts["running"] / machine_count if machine_count else 0
    quality = max(0.0, 1.0 - (critical_24h / (anomalies_24h + 1)) * 0.5)
    performance = avg_health / 100.0
    avg_oee = round(availability * quality * performance * 100.0, 1)

    return Overview(
        machine_count=machine_count,
        running=status_counts["running"],
        fault=status_counts["fault"],
        maintenance=status_counts["maintenance"],
        idle=status_counts["idle"],
        avg_health_index=avg_health,
        avg_oee=avg_oee,
        anomalies_24h=anomalies_24h,
        critical_24h=critical_24h,
        total_energy_24h=round(float(total_energy), 2),
        high_risk_machines=high_risk,
    )


# ---------------------------------------------------------------------------
#  WebSocket live stream
# ---------------------------------------------------------------------------
@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        await websocket.send_json({"type": "hello", "message": "connected"})
        while True:
            # We don't expect inbound messages; keep the socket alive.
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)
