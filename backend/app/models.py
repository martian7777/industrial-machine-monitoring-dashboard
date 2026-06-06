"""SQLAlchemy ORM models mapping to the database schema in db/init.sql."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Machine(Base):
    __tablename__ = "machines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str] = mapped_column(String, nullable=False)
    install_date: Mapped[date] = mapped_column(Date, nullable=False)
    rated_power_kw: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")

    telemetry = relationship("TelemetryRaw", back_populates="machine", cascade="all, delete-orphan")
    anomalies = relationship("Anomaly", back_populates="machine", cascade="all, delete-orphan")


class TelemetryRaw(Base):
    __tablename__ = "telemetry_raw"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    machine_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    temperature: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    vibration: Mapped[float] = mapped_column(Numeric(7, 3), nullable=False)
    pressure: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    energy_use: Mapped[float] = mapped_column(Numeric(9, 3), nullable=False)
    rpm: Mapped[float] = mapped_column(Numeric(8, 1), nullable=False, default=0)
    operating_hours: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)

    machine = relationship("Machine", back_populates="telemetry")


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    machine_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    telemetry_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("telemetry_raw.id", ondelete="SET NULL"), nullable=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    sensor: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    z_score: Mapped[float | None] = mapped_column(Numeric(8, 3), nullable=True)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    machine = relationship("Machine", back_populates="anomalies")


class MaintenancePrediction(Base):
    __tablename__ = "maintenance_predictions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    machine_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    maintenance_risk_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    rul_hours: Mapped[float] = mapped_column(Numeric(10, 1), nullable=False)
    next_recommended_maintenance: Mapped[date | None] = mapped_column(Date, nullable=True)
    health_index: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    drivers: Mapped[str | None] = mapped_column(Text, nullable=True)


class MachineDailyAggregate(Base):
    __tablename__ = "machine_daily_aggregates"
    __table_args__ = (UniqueConstraint("machine_id", "day", name="uq_machine_day"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    machine_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("machines.id", ondelete="CASCADE"), nullable=False
    )
    day: Mapped[date] = mapped_column(Date, nullable=False)
    avg_temperature: Mapped[float | None] = mapped_column(Numeric(7, 2))
    max_temperature: Mapped[float | None] = mapped_column(Numeric(7, 2))
    avg_vibration: Mapped[float | None] = mapped_column(Numeric(7, 3))
    max_vibration: Mapped[float | None] = mapped_column(Numeric(7, 3))
    avg_pressure: Mapped[float | None] = mapped_column(Numeric(7, 2))
    total_energy_kwh: Mapped[float | None] = mapped_column(Numeric(12, 3))
    reading_count: Mapped[int | None] = mapped_column(Integer)
    anomaly_count: Mapped[int | None] = mapped_column(Integer)
    critical_count: Mapped[int | None] = mapped_column(Integer)
    uptime_ratio: Mapped[float | None] = mapped_column(Numeric(5, 4))
    avg_risk_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
