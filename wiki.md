# 📖 Sentinel·SCADA — Project Wiki

Welcome to the operator and developer wiki for the Sentinel·SCADA system. This documentation provides information for configuring, extending, administering, and troubleshooting the machine monitoring platform.

---

## 1. System Configurations Reference

All configuration is managed through environment variables (stored in the `.env` file). Below is a comprehensive lookup of all configuration options:

### Database Settings
* `DATABASE_URL`: The PostgreSQL connection string. Must use the `postgresql+psycopg2://` driver prefix.
* `DB_SSLMODE`: Set to `require` for Supabase/cloud hosting, or `disable` for local Docker databases.
* `SUPABASE_URL` / `SUPABASE_ANON_KEY`: Supabase project reference URL and public token (optional, for custom JS/Python client integrations).

### Backend Settings
* `BACKEND_HOST` / `BACKEND_PORT`: Host interface and port for the FastAPI server (default: `0.0.0.0:8000`).
* `CORS_ORIGINS`: Comma-separated list of browser origins permitted to request resource endpoints (e.g. `http://localhost:5173`).
* `AUTO_INIT_DB`: If `true`, the backend auto-creates core tables and seeds default machines on startup if they do not exist.

### Simulator Settings
* `BACKEND_URL`: URL of the FastAPI endpoint. Inside Docker, this should be `http://backend:8000`.
* `SIM_INTERVAL_SECONDS`: The simulation frequency per machine (default: `2`). Lower values increase telemetry volume.
* `SIM_FAULT_PROBABILITY`: The statistical chance (0 to 1) per tick of injecting a machine fault (default: `0.02`).

### ETL Settings
* `ETL_INTERVAL_SECONDS`: The frequency at which daily rollups are calculated (default: `3600` for hourly updates).
* `ETL_LOOKBACK_DAYS`: The size of the historical rolling aggregation window (default: `7`).

---

## 2. Developer Onboarding & Local Setup

If you wish to run components bare-metal without Docker:

### Prerequisites
- Python 3.10+
- Node.js 18+
- Active PostgreSQL server instance

### A. FastAPI Backend Setup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
The swagger docs will load at `http://localhost:8000/docs`.

### B. Simulator Setup
```bash
cd simulator
pip install -r requirements.txt
export BACKEND_URL="http://localhost:8000"  # On Windows: $env:BACKEND_URL="http://localhost:8000"
python simulator.py
```

### C. Frontend Dashboard Setup
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` to view the live dashboard.

---

## 3. How-To: Add a New Machine Asset

To register a new physical machine into the system:

1. **Insert Metadata into the Database**: Run an insert query to populate the `machines` table.
   ```sql
   INSERT INTO machines (code, name, type, location, install_date, rated_power_kw, status)
   VALUES ('CNC-03', 'CNC Lathe C', 'CNC Mill', 'Plant 1 / Line A / Cell 3', '2024-01-15', 24.50, 'running');
   ```
2. **Configure Simulator Profile (Optional)**: If you want the simulator to emulate custom telemetry for your new machine, edit `simulator/simulator.py` and register its machine code inside the telemetry profiles mapping:
   ```python
   # Example: Adding specific sensor boundaries for CNC-03
   MACHINE_PROFILES["CNC-03"] = {
       "temp_base": 42.0, "temp_std": 2.5,
       "vib_base": 1.2, "vib_std": 0.3,
       "press_base": 6.0, "press_std": 0.5,
       ...
   }
   ```
   If no profile is registered, the simulator defaults to using a standard template based on the machine's declared `type`.

---

## 4. Database Administration & Maintenance

As raw IoT telemetry accumulates, table sizes will grow rapidly. Follow these operational guidelines to maintain database performance:

### Indexes
The raw time-series table has compound indexes:
* `idx_telemetry_machine_ts` on `(machine_id, ts DESC)`
* `idx_telemetry_ts` on `(ts DESC)`

These indexes ensure that sub-second queries like "get the last 50 readings of machine X" remain instant. Do not remove them.

### Telemetry Archival (Partitioning)
If database performance slows down after millions of rows:
1. **Aggregates as Source of Truth**: Ensure the daily aggregates ETL is running. The `machine_daily_aggregates` table serves as the primary dataset for long-term trends and BI reporting.
2. **Raw Telemetry Pruning**: Implement a rolling retention window where raw telemetry older than 30 or 90 days is deleted or archived:
   ```sql
   DELETE FROM telemetry_raw WHERE ts < now() - INTERVAL '90 days';
   ```

---

## 5. Troubleshooting Common Issues

### ❌ Problem: `SSL connection error` or `no pg_hba.conf entry`
* **Root Cause**: Cloud databases like Supabase enforce secure SSL connections, but the DB client did not request an encrypted session.
* **Fix**: Ensure your `.env` contains `DB_SSLMODE=require`. When running bare-metal, ensure your Python environment is able to find your OS root SSL certificates, or use a direct non-pooled connection URI.

### ❌ Problem: Dashboard shows "WebSocket Connection Failed"
* **Root Cause**: The React client cannot connect to the WebSocket endpoint at `VITE_WS_URL`.
* **Fix**: Check that the backend container is running. If running the backend locally or under a non-standard port, update your `.env`:
  ```env
  VITE_WS_URL=ws://localhost:8000/ws/live
  ```
  Ensure there are no firewalls or reverse proxies blocking WS handshakes.

### ❌ Problem: ETL Pipeline fails with `Relation "machine_daily_aggregates" does not exist`
* **Root Cause**: The database tables were not created prior to the ETL starting up.
* **Fix**: Set `AUTO_INIT_DB=true` in `.env` to let the backend auto-create tables, or execute the SQL schema in `db/init.sql` manually inside your PostgreSQL shell or Supabase SQL editor.
