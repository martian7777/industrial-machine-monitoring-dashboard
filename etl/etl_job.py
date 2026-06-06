"""ETL worker: aggregate raw telemetry + anomalies into machine_daily_aggregates.

Runs on a loop (ETL_INTERVAL_SECONDS). Uses Pandas for the per-day rollups and
UPSERTs into the aggregate table so Power BI imports stay small and fast.
"""
from __future__ import annotations

import os
import time

import pandas as pd
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@db:5432/monitoring")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

DB_SSLMODE = os.getenv("DB_SSLMODE", "require")
INTERVAL = int(os.getenv("ETL_INTERVAL_SECONDS", "3600"))
LOOKBACK_DAYS = int(os.getenv("ETL_LOOKBACK_DAYS", "7"))

connect_args = {}
if "supabase" in DATABASE_URL or DB_SSLMODE in {"require", "verify-full", "verify-ca"}:
    connect_args = {"sslmode": DB_SSLMODE}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True, future=True)


UPSERT_SQL = text(
    """
    INSERT INTO machine_daily_aggregates
        (machine_id, day, avg_temperature, max_temperature, avg_vibration,
         max_vibration, avg_pressure, total_energy_kwh, reading_count,
         anomaly_count, critical_count, uptime_ratio, avg_risk_score)
    VALUES
        (:machine_id, :day, :avg_temperature, :max_temperature, :avg_vibration,
         :max_vibration, :avg_pressure, :total_energy_kwh, :reading_count,
         :anomaly_count, :critical_count, :uptime_ratio, :avg_risk_score)
    ON CONFLICT (machine_id, day) DO UPDATE SET
        avg_temperature  = EXCLUDED.avg_temperature,
        max_temperature  = EXCLUDED.max_temperature,
        avg_vibration    = EXCLUDED.avg_vibration,
        max_vibration    = EXCLUDED.max_vibration,
        avg_pressure     = EXCLUDED.avg_pressure,
        total_energy_kwh = EXCLUDED.total_energy_kwh,
        reading_count    = EXCLUDED.reading_count,
        anomaly_count    = EXCLUDED.anomaly_count,
        critical_count   = EXCLUDED.critical_count,
        uptime_ratio     = EXCLUDED.uptime_ratio,
        avg_risk_score   = EXCLUDED.avg_risk_score
    """
)


def run_once() -> int:
    """Compute and upsert daily aggregates for the lookback window. Returns rows."""
    with engine.begin() as conn:
        telemetry = pd.read_sql(
            text(
                """
                SELECT machine_id, ts, temperature, vibration, pressure, energy_use
                FROM telemetry_raw
                WHERE ts >= now() - make_interval(days => :days)
                """
            ),
            conn,
            params={"days": LOOKBACK_DAYS},
        )
        anomalies = pd.read_sql(
            text(
                """
                SELECT machine_id, ts, severity
                FROM anomalies
                WHERE ts >= now() - make_interval(days => :days)
                """
            ),
            conn,
            params={"days": LOOKBACK_DAYS},
        )
        risk = pd.read_sql(
            text(
                """
                SELECT machine_id, ts, maintenance_risk_score
                FROM maintenance_predictions
                WHERE ts >= now() - make_interval(days => :days)
                """
            ),
            conn,
            params={"days": LOOKBACK_DAYS},
        )

    if telemetry.empty:
        print("[etl] no telemetry in window; nothing to aggregate")
        return 0

    telemetry["day"] = pd.to_datetime(telemetry["ts"], utc=True).dt.date
    tel_agg = (
        telemetry.groupby(["machine_id", "day"])
        .agg(
            avg_temperature=("temperature", "mean"),
            max_temperature=("temperature", "max"),
            avg_vibration=("vibration", "mean"),
            max_vibration=("vibration", "max"),
            avg_pressure=("pressure", "mean"),
            total_energy_kwh=("energy_use", "sum"),
            reading_count=("temperature", "count"),
        )
        .reset_index()
    )

    # anomaly counts per machine/day
    if not anomalies.empty:
        anomalies["day"] = pd.to_datetime(anomalies["ts"], utc=True).dt.date
        anom_agg = (
            anomalies.groupby(["machine_id", "day"])
            .agg(
                anomaly_count=("severity", "count"),
                critical_count=("severity", lambda s: int((s == "critical").sum())),
            )
            .reset_index()
        )
        merged = tel_agg.merge(anom_agg, on=["machine_id", "day"], how="left")
    else:
        merged = tel_agg
        merged["anomaly_count"] = 0
        merged["critical_count"] = 0

    # avg risk per machine/day
    if not risk.empty:
        risk["day"] = pd.to_datetime(risk["ts"], utc=True).dt.date
        risk_agg = (
            risk.groupby(["machine_id", "day"])
            .agg(avg_risk_score=("maintenance_risk_score", "mean"))
            .reset_index()
        )
        merged = merged.merge(risk_agg, on=["machine_id", "day"], how="left")
    else:
        merged["avg_risk_score"] = 0.0

    merged[["anomaly_count", "critical_count"]] = (
        merged[["anomaly_count", "critical_count"]].fillna(0).astype(int)
    )
    merged["avg_risk_score"] = merged["avg_risk_score"].fillna(0.0)

    # uptime ratio: fraction of readings without a critical anomaly that day
    merged["uptime_ratio"] = (
        1.0 - (merged["critical_count"] / merged["reading_count"].clip(lower=1))
    ).clip(lower=0.0, upper=1.0)

    records = merged.to_dict(orient="records")
    with engine.begin() as conn:
        for rec in records:
            conn.execute(
                UPSERT_SQL,
                {
                    "machine_id": int(rec["machine_id"]),
                    "day": rec["day"],
                    "avg_temperature": round(float(rec["avg_temperature"]), 2),
                    "max_temperature": round(float(rec["max_temperature"]), 2),
                    "avg_vibration": round(float(rec["avg_vibration"]), 3),
                    "max_vibration": round(float(rec["max_vibration"]), 3),
                    "avg_pressure": round(float(rec["avg_pressure"]), 2),
                    "total_energy_kwh": round(float(rec["total_energy_kwh"]), 3),
                    "reading_count": int(rec["reading_count"]),
                    "anomaly_count": int(rec["anomaly_count"]),
                    "critical_count": int(rec["critical_count"]),
                    "uptime_ratio": round(float(rec["uptime_ratio"]), 4),
                    "avg_risk_score": round(float(rec["avg_risk_score"]), 2),
                },
            )
    print(f"[etl] upserted {len(records)} machine/day aggregate rows")
    return len(records)


def main() -> None:
    print(f"[etl] starting. interval={INTERVAL}s lookback={LOOKBACK_DAYS}d")
    while True:
        try:
            run_once()
        except Exception as exc:
            print(f"[etl] ERROR: {exc}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
