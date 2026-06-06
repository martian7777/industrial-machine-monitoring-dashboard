"""Pydantic schemas for request/response validation."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class TelemetryIn(BaseModel):
    """Incoming reading from the simulator / IoT edge."""

    machine_id: int
    temperature: float = Field(..., description="deg C")
    vibration: float = Field(..., description="mm/s RMS")
    pressure: float = Field(..., description="bar")
    energy_use: float = Field(..., description="kWh for the interval")
    rpm: float = 0.0
    operating_hours: float = 0.0
    ts: datetime | None = None


class AnomalyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    machine_id: int
    ts: datetime
    sensor: str
    value: float
    z_score: float | None
    severity: str
    message: str


class TelemetryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    machine_id: int
    ts: datetime
    temperature: float
    vibration: float
    pressure: float
    energy_use: float
    rpm: float
    operating_hours: float


class PredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    machine_id: int
    ts: datetime
    maintenance_risk_score: float
    rul_hours: float
    next_recommended_maintenance: date | None
    health_index: float
    drivers: str | None


class MachineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    type: str
    location: str
    install_date: date
    rated_power_kw: float
    status: str


class MachineStatus(BaseModel):
    """Composite view for the dashboard machine cards."""

    machine: MachineOut
    latest: TelemetryOut | None = None
    prediction: PredictionOut | None = None
    open_anomalies: int = 0


class IngestResult(BaseModel):
    telemetry_id: int
    anomalies: list[AnomalyOut] = []
    prediction: PredictionOut | None = None


class Overview(BaseModel):
    """Top-of-dashboard KPI tiles."""

    machine_count: int
    running: int
    fault: int
    maintenance: int
    idle: int
    avg_health_index: float
    avg_oee: float
    anomalies_24h: int
    critical_24h: int
    total_energy_24h: float
    high_risk_machines: int
