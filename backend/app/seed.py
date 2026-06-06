"""Create tables and seed the 10 machines on a fresh database.

Used when AUTO_INIT_DB=true so a brand-new cloud Supabase project works without
manually running db/init.sql first. The Power BI VIEWS are NOT created here —
run db/init.sql for those.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine
from .models import Machine

SEED_MACHINES = [
    ("CNC-01", "CNC Milling Center A", "CNC Mill", "Plant 1 / Line A / Cell 1", date(2019, 3, 12), 22.0),
    ("CNC-02", "CNC Milling Center B", "CNC Mill", "Plant 1 / Line A / Cell 2", date(2020, 7, 1), 22.0),
    ("ROB-01", "Robotic Arm Welder", "Robotic Arm", "Plant 1 / Line B / Cell 1", date(2021, 1, 20), 11.5),
    ("ROB-02", "Robotic Arm Pick&Place", "Robotic Arm", "Plant 1 / Line B / Cell 2", date(2022, 5, 9), 9.0),
    ("CNV-01", "Packaging Conveyor 1", "Conveyor", "Plant 1 / Line C / Pack", date(2018, 11, 3), 7.5),
    ("CNV-02", "Packaging Conveyor 2", "Conveyor", "Plant 1 / Line C / Pack", date(2018, 11, 3), 7.5),
    ("PMP-01", "Hydraulic Pump Unit", "Hydraulic Pump", "Plant 1 / Utilities", date(2017, 6, 15), 30.0),
    ("CMP-01", "Air Compressor", "Air Compressor", "Plant 1 / Utilities", date(2016, 2, 28), 37.0),
    ("INJ-01", "Injection Molder", "Injection Molder", "Plant 2 / Line D / Cell 1", date(2020, 9, 30), 45.0),
    ("FUR-01", "Heat Treat Furnace", "Furnace", "Plant 2 / Line D / Heat", date(2015, 4, 10), 60.0),
]


def init_and_seed() -> None:
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        existing = set(db.execute(select(Machine.code)).scalars().all())
        added = 0
        for code, name, mtype, loc, install, power in SEED_MACHINES:
            if code in existing:
                continue
            db.add(
                Machine(
                    code=code,
                    name=name,
                    type=mtype,
                    location=loc,
                    install_date=install,
                    rated_power_kw=power,
                    status="running",
                )
            )
            added += 1
        if added:
            db.commit()
        return added
    finally:
        db.close()
