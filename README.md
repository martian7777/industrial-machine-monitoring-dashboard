# 🏭 Sentinel·SCADA — Industrial Machine Monitoring Dashboard

An end-to-end, industrial-grade machine monitoring platform that simulates a
smart factory of **10 machines** emitting IoT sensor data (temperature,
vibration, pressure, energy), automatically flags **anomalies**, and computes
**predictive-maintenance** risk & Remaining Useful Life (RUL) — all visualised
on a premium real-time dashboard and ready for **Power BI** reporting.

```
IoT Simulator ─POST▶ FastAPI ─┬─ ingest + anomaly + RUL ─▶ PostgreSQL / Supabase
   (10 machines)              │                                 ▲          │
                              └─ WebSocket ─▶ React Dashboard   │          │
                                                                │          ▼
                              ETL (Pandas) ─ daily aggregates ──┘    Power BI (views)
```

## Stack

| Layer       | Tech                                                        |
|-------------|------------------------------------------------------------|
| Database    | PostgreSQL / **Supabase** (cloud by default)               |
| Backend     | **FastAPI**, SQLAlchemy 2, WebSockets                       |
| Analytics   | Rolling Z-score anomaly detection + RUL/risk model         |
| Simulator   | Python daemon, realistic per-type profiles + fault injection |
| ETL         | Python + **Pandas**, hourly daily-aggregate upserts        |
| Frontend    | **Vite + React**, **Recharts**, vanilla CSS (glassmorphic) |
| BI          | Power BI star-schema views + DAX kit                       |

---

## Quick start (cloud Supabase)

### 1. Configure environment
```powershell
Copy-Item .env.example .env
```
Edit `.env` and set your Supabase connection string:
```
DATABASE_URL=postgresql+psycopg2://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
DB_SSLMODE=require
```
> Get this from **Supabase → Project Settings → Database → Connection string**.
> Keep the `postgresql+psycopg2://` prefix (the backend also auto-fixes a plain URL).

### 2. Create the schema
Open the **Supabase SQL Editor**, paste the contents of
[`db/init.sql`](db/init.sql), and run it. This creates all tables, seeds the 10
machines, and creates the Power BI views.

> The backend will also auto-create tables + seed machines on startup
> (`AUTO_INIT_DB=true`), but the **Power BI views** are only created by `init.sql`.

### 3. Launch the stack
```powershell
docker compose up --build -d
```
This starts: `backend` (:8000), `simulator`, `etl`, `frontend` (:5173).

### 4. Open it
| What            | URL                                |
|-----------------|------------------------------------|
| Dashboard       | http://localhost:5173              |
| API docs        | http://localhost:8000/docs         |
| Health          | http://localhost:8000/health       |

Within a few seconds the simulator begins POSTing telemetry; machine cards,
live charts and the anomaly feed update in real time over WebSocket.

---

## Run with a local Postgres instead of cloud

```powershell
# point the DB at the bundled container, then bring up the local-db profile
#   DATABASE_URL=postgresql+psycopg2://postgres:postgres@db:5432/monitoring
#   DB_SSLMODE=disable
docker compose --profile local-db up --build -d
```
`db/init.sql` runs automatically on first boot of the local Postgres volume.

---

## Local development (without Docker)

```powershell
# Backend
cd backend
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload

# Simulator (new terminal)
cd simulator ; pip install -r requirements.txt
$env:BACKEND_URL="http://localhost:8000" ; python simulator.py

# Frontend (new terminal)
cd frontend ; npm install ; npm run dev
```

---

## API surface

| Method | Path                                   | Purpose                              |
|--------|----------------------------------------|--------------------------------------|
| POST   | `/api/telemetry`                       | Ingest a reading (anomaly + RUL + WS)|
| GET    | `/api/machines`                        | List machines                        |
| GET    | `/api/machines/status`                 | Cards: latest reading + prediction   |
| GET    | `/api/machines/{id}/telemetry?limit=`  | Recent telemetry (chronological)     |
| GET    | `/api/anomalies?limit=&severity=`      | Recent anomalies                     |
| GET    | `/api/maintenance`                     | Latest prediction per machine (ranked)|
| GET    | `/api/overview`                        | KPI tiles (OEE, health, energy…)     |
| WS     | `/ws/live`                             | Real-time telemetry + anomaly stream |

---

## How the analytics work

- **Anomaly detection** ([backend/app/analytics.py](backend/app/analytics.py)):
  rolling **Z-score** over the last N readings per sensor (`warning` ≥ 3σ,
  `critical` ≥ 4.5σ) plus **hard physical limits** that always escalate to
  critical.
- **Predictive maintenance**: an explainable blend of **usage wear**
  (operating hours vs design life), **recent anomaly pressure** (24h,
  severity-weighted), and **instantaneous stress** (temperature/vibration
  headroom) → `risk_score`, `health_index`, `rul_hours`, and a recommended
  service date with human-readable **drivers**.

---

## Project layout
```
.
├── docker-compose.yml          # full-stack orchestration
├── .env.example                # copy to .env and fill Supabase creds
├── db/init.sql                 # schema + seed + Power BI views
├── backend/                    # FastAPI app (api, analytics, ws)
├── simulator/                  # IoT data generator
├── etl/                        # Pandas daily aggregator
├── frontend/                   # Vite + React dashboard (Recharts)
└── powerbi/README.md           # Power BI connection + DAX kit
```

---

## Verification checklist
1. `docker compose up --build -d` → all 4 services healthy (`docker compose ps`).
2. `GET http://localhost:8000/health` → `{"status":"ok"}`.
3. Swagger at `/docs` → `POST /api/telemetry` returns anomalies/prediction.
4. Simulator logs show telemetry being posted (and occasional injected faults).
5. Dashboard at `:5173` shows live cards, charts, and the anomaly feed updating.
6. In Supabase SQL editor: `SELECT count(*) FROM telemetry_raw;` grows over time.
7. Power BI: connect to the `vw_*` views (see [powerbi/README.md](powerbi/README.md)).
