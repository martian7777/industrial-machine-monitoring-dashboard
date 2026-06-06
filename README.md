# 🏭 Sentinel·SCADA — Industrial Machine Monitoring Dashboard

![PostgreSQL](https://img.shields.io/badge/database-PostgreSQL%20%2F%20Supabase-blue?style=for-the-badge&logo=postgresql)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688?style=for-the-badge&logo=fastapi)
![React](https://img.shields.io/badge/frontend-React%20%2F%20Vite-61DAFB?style=for-the-badge&logo=react)
![Pandas](https://img.shields.io/badge/analytics-Pandas%20%2F%20SQLAlchemy-150458?style=for-the-badge&logo=pandas)
![Docker](https://img.shields.io/badge/infrastructure-Docker%20Compose-2496ED?style=for-the-badge&logo=docker)

An end-to-end, industrial-grade machine monitoring and predictive maintenance platform simulating a smart factory of **10 machines** emitting real-time IoT sensor data (temperature, vibration, pressure, energy usage). The system automatically detects **anomalies** using rolling statistics, computes **predictive-maintenance** risks & Remaining Useful Life (RUL) on-the-fly, and serves a live glassmorphic dashboard alongside pre-configured views for **Power BI** reporting.

---

## 🗺️ Project Documentation Navigation

To explore detailed specifications, deployment guides, or live dashboard results, navigate through the following documents:

* 📊 **[Live Operational Findings](findings.md)**: View a snapshot of fleet performance, key insights on active equipment faults (e.g. `CMP-01` compressor and `PMP-01` hydraulic pump), API responses, and screenshot captures of the live user interface.
* 🏗️ **[System Architecture](architecture.md)**: Discover details on the end-to-end data pipeline, database star schema, real-time WebSocket ingestion sequence, and mathematical formulations for the anomaly detection Z-score and Remaining Useful Life (RUL) estimation.
* 📖 **[Project Operator Wiki](wiki.md)**: Find developer onboarding instructions, comprehensive environment configuration reference, guides on scaling/registering new assets, data partition guidelines, and solutions to common SSL or Docker networking issues.

---

## ⚙️ Core Stack Overview

| Layer | Technologies & Implementations |
| :--- | :--- |
| **Database** | PostgreSQL / **Supabase** (Fully relational schema with custom indexes and Power BI reporting views) |
| **Backend** | **FastAPI** (Python 3.10+), SQLAlchemy 2, real-time WebSockets, Swagger UI auto-documentation |
| **Analytics** | Deterministic rolling Z-score anomaly detection + condition-based wear & risk estimation model |
| **Simulator** | Python daemon generating realistic telemetry based on specific machine profiles + random fault injections |
| **ETL Pipeline** | Python daemon utilizing **Pandas** for batch-aggregation of time-series records into daily metrics |
| **Frontend** | **Vite + React**, **Recharts** for live telemetry plots, and glassmorphic vanilla CSS UI |
| **BI Reporting** | Pre-defined relational database views supporting a standard **Power BI Star Schema** and DAX measure kit |

---

## ⚡ Quick Start

### 1. Configure the Environment
Copy the example environment file:
```powershell
Copy-Item .env.example .env
```
Edit `.env` and set your Supabase or local PostgreSQL connection string:
```env
DATABASE_URL=postgresql+psycopg2://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
DB_SSLMODE=require
```

### 2. Set Up the Schema
Open the **Supabase SQL Editor** (or database client), paste the contents of [`db/init.sql`](db/init.sql), and run it. This creates the relational tables, seeds the default 10 machines, and registers the Power BI views.

### 3. Launch the Stack
Start all services in Docker Compose:
```powershell
docker compose up --build -d
```
This starts:
* `backend` (:8000)
* `simulator` (POSTs telemetry)
* `etl` (runs hourly aggregate rollups)
* `frontend` (:5173)

### 4. Access the Applications
| Interface / Service | Endpoint URL |
| :--- | :--- |
| **Glassmorphic Web Dashboard** | [http://localhost:5173](http://localhost:5173) |
| **FastAPI Swagger API Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) |
| **Backend Health Endpoint** | [http://localhost:8000/health](http://localhost:8000/health) |

Within seconds, the simulator begins posting live telemetry. Machine cards, sensor charts, and critical anomaly feeds will automatically update in real-time.

---

## 📁 Project Directory Structure

```
.
├── docker-compose.yml          # Full-stack Docker orchestration
├── .env.example                # Template for environment settings
├── db/
│   └── init.sql                # SQL schema, metadata seeds, and Power BI views
├── backend/
│   ├── Dockerfile              # Backend container file
│   └── app/                    # FastAPI application (endpoints, db models, analytics, websockets)
├── simulator/
│   ├── Dockerfile              # Simulator container file
│   └── simulator.py            # IoT telemetry generator
├── etl/
│   ├── Dockerfile              # ETL worker container file
│   └── etl_job.py              # Pandas aggregate generator
├── frontend/
│   ├── src/                    # React dashboard sources (Recharts component, WebSocket hooks)
│   └── index.html              # Main dashboard wrapper
├── powerbi/
│   └── README.md               # Power BI connection guidelines & DAX measures
├── findings.md                 # Live dashboard screenshots & operational findings
├── architecture.md             # Data flow blueprints, schemas, and analytics logic
└── wiki.md                     # Operator manuals, setup guides, and troubleshooting
```
