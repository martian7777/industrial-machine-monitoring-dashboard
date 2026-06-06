"""IoT telemetry simulator for the 10 factory machines.

Generates realistic, type-specific timeseries (temperature, vibration, pressure,
energy, rpm) with smooth random-walk drift, daily duty cycles, and occasional
injected faults that ramp a machine into degraded/critical territory. Readings
are POSTed to the FastAPI backend's /api/telemetry endpoint.
"""
from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import requests

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
INGEST_ENDPOINT = f"{BACKEND_URL}/api/telemetry"
MACHINES_ENDPOINT = f"{BACKEND_URL}/api/machines"
INTERVAL = float(os.getenv("SIM_INTERVAL_SECONDS", "2"))
FAULT_PROB = float(os.getenv("SIM_FAULT_PROBABILITY", "0.02"))


# Baseline operating envelope per machine type.
# (temp, vibration, pressure, energy_per_tick, rpm)
PROFILES: dict[str, dict[str, float]] = {
    "CNC Mill":         {"temp": 48, "vib": 2.2, "pres": 6.0, "energy": 0.35, "rpm": 8000},
    "Robotic Arm":      {"temp": 42, "vib": 1.6, "pres": 4.5, "energy": 0.18, "rpm": 1500},
    "Conveyor":         {"temp": 38, "vib": 1.2, "pres": 2.5, "energy": 0.12, "rpm": 300},
    "Hydraulic Pump":   {"temp": 55, "vib": 2.8, "pres": 9.0, "energy": 0.50, "rpm": 1800},
    "Air Compressor":   {"temp": 60, "vib": 3.0, "pres": 8.0, "energy": 0.60, "rpm": 2900},
    "Injection Molder": {"temp": 65, "vib": 2.0, "pres": 7.5, "energy": 0.75, "rpm": 200},
    "Furnace":          {"temp": 80, "vib": 0.8, "pres": 1.5, "energy": 0.95, "rpm": 0},
}
DEFAULT_PROFILE = {"temp": 50, "vib": 2.0, "pres": 5.0, "energy": 0.4, "rpm": 1000}


@dataclass
class MachineState:
    id: int
    code: str
    type: str
    base: dict[str, float]
    operating_hours: float
    # current offsets from baseline (random walk)
    drift: dict[str, float] = field(default_factory=lambda: {"temp": 0, "vib": 0, "pres": 0, "energy": 0})
    # active fault: sensor -> remaining ticks of escalation
    fault: dict | None = None


def _walk(value: float, scale: float, bound: float) -> float:
    value += random.uniform(-scale, scale)
    return max(-bound, min(bound, value))


def fetch_machines(retries: int = 30) -> list[dict]:
    for attempt in range(retries):
        try:
            r = requests.get(MACHINES_ENDPOINT, timeout=5)
            r.raise_for_status()
            data = r.json()
            if data:
                return data
        except Exception as exc:
            print(f"[sim] waiting for backend/machines ({attempt + 1}/{retries}): {exc}")
        time.sleep(2)
    raise RuntimeError("Backend did not return machines in time")


def init_states() -> list[MachineState]:
    machines = fetch_machines()
    states: list[MachineState] = []
    for m in machines:
        profile = PROFILES.get(m["type"], DEFAULT_PROFILE)
        # seed operating hours from install age so RUL looks realistic
        try:
            install = datetime.fromisoformat(str(m["install_date"]))
            years = max(0.0, (datetime.now() - install).days / 365.25)
        except Exception:
            years = 3.0
        op_hours = years * 16 * 300  # ~16h/day, 300 days/yr
        states.append(
            MachineState(
                id=m["id"],
                code=m["code"],
                type=m["type"],
                base=profile,
                operating_hours=round(op_hours, 1),
            )
        )
    print(f"[sim] initialized {len(states)} machines")
    return states


def maybe_inject_fault(st: MachineState) -> None:
    if st.fault is None and random.random() < FAULT_PROB:
        sensor = random.choice(["temp", "vib", "pres"])
        st.fault = {
            "sensor": sensor,
            "ticks": random.randint(8, 25),   # how long it escalates
            "intensity": random.uniform(1.5, 3.0),
        }
        print(f"[sim] !! injecting {sensor} fault into {st.code}")


def generate_reading(st: MachineState) -> dict:
    b = st.base

    # smooth random-walk drift around baseline
    st.drift["temp"] = _walk(st.drift["temp"], 0.6, 6)
    st.drift["vib"] = _walk(st.drift["vib"], 0.15, 1.5)
    st.drift["pres"] = _walk(st.drift["pres"], 0.2, 1.5)
    st.drift["energy"] = _walk(st.drift["energy"], 0.02, 0.15)

    temp = b["temp"] + st.drift["temp"] + random.uniform(-1, 1)
    vib = b["vib"] + st.drift["vib"] + random.uniform(-0.3, 0.3)
    pres = b["pres"] + st.drift["pres"] + random.uniform(-0.2, 0.2)
    energy = max(0.0, b["energy"] + st.drift["energy"] + random.uniform(-0.03, 0.03))
    rpm = max(0.0, b["rpm"] + random.uniform(-0.02, 0.02) * b["rpm"])

    # apply active fault escalation
    maybe_inject_fault(st)
    if st.fault:
        f = st.fault
        progress = 1.0 + (25 - f["ticks"]) * 0.12 * f["intensity"]
        if f["sensor"] == "temp":
            temp += 18 * progress
        elif f["sensor"] == "vib":
            vib += 3.5 * progress
        elif f["sensor"] == "pres":
            pres += 3.0 * progress
        energy *= 1.0 + 0.05 * progress
        f["ticks"] -= 1
        if f["ticks"] <= 0:
            print(f"[sim] .. fault on {st.code} cleared")
            st.fault = None

    st.operating_hours += INTERVAL / 3600.0

    return {
        "machine_id": st.id,
        "temperature": round(temp, 2),
        "vibration": round(max(0.0, vib), 3),
        "pressure": round(max(0.0, pres), 2),
        "energy_use": round(energy, 3),
        "rpm": round(rpm, 1),
        "operating_hours": round(st.operating_hours, 2),
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    print(f"[sim] backend={BACKEND_URL} interval={INTERVAL}s fault_prob={FAULT_PROB}")
    states = init_states()
    session = requests.Session()
    while True:
        for st in states:
            reading = generate_reading(st)
            try:
                resp = session.post(INGEST_ENDPOINT, json=reading, timeout=5)
                if resp.status_code == 200:
                    anoms = resp.json().get("anomalies", [])
                    if anoms:
                        for a in anoms:
                            print(f"[sim] {st.code} ANOMALY {a['severity']}: {a['message']}")
                else:
                    print(f"[sim] {st.code} ingest failed {resp.status_code}: {resp.text[:120]}")
            except Exception as exc:
                print(f"[sim] {st.code} post error: {exc}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
