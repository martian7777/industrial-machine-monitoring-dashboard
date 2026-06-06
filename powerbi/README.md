# Power BI Integration Kit

Connect Power BI Desktop directly to the monitoring database (cloud Supabase or
local Postgres) using the **star-schema views** created by [`db/init.sql`](../db/init.sql).

---

## 1. Connect Power BI to Supabase / PostgreSQL

> Power BI Desktop ships with the Npgsql PostgreSQL connector. If prompted,
> install **Npgsql** (https://github.com/npgsql/npgsql/releases) and restart Power BI.

1. **Home → Get Data → More… → PostgreSQL database**.
2. Fill in the connection (from Supabase → Project Settings → Database):

   | Field    | Value                                                        |
   |----------|-------------------------------------------------------------|
   | Server   | `db.<project-ref>.supabase.co` (or pooler host) `:5432`     |
   | Database | `postgres`                                                  |

   For the **pooler** host use e.g. `aws-0-<region>.pooler.supabase.com:5432`
   and username `postgres.<project-ref>`.
3. **Data Connectivity mode**: choose **Import** (recommended — fast, works with
   the pre-aggregated views) or **DirectQuery** (live, heavier on the DB).
4. **User / Password**: your Supabase database user + password.
5. **Encryption**: tick **"Use encrypted connection"** (Supabase requires SSL).
6. In the **Navigator**, select these views (not the raw tables):

   - `vw_dim_machine`
   - `vw_dim_date`
   - `vw_fact_daily`            ← primary fact (one row per machine per day)
   - `vw_fact_latest_prediction`
   - `vw_fact_anomaly`          ← optional, for drill-through

7. **Load**.

---

## 2. Model relationships (Star Schema)

In **Model view**, create these relationships (single-direction, 1 → *):

```
vw_dim_machine[machine_id]  1 ── *  vw_fact_daily[machine_id]
vw_dim_machine[machine_id]  1 ── *  vw_fact_anomaly[machine_id]
vw_dim_machine[machine_id]  1 ── *  vw_fact_latest_prediction[machine_id]
vw_dim_date[date_key]       1 ── *  vw_fact_daily[date_key]
vw_dim_date[date_key]       1 ── *  vw_fact_anomaly[date_key]
```

Mark `vw_dim_date` as the official **Date table** (Table tools → Mark as date
table → `date_key`) so time-intelligence DAX works.

```
            ┌──────────────────┐
            │   vw_dim_date    │
            └────────┬─────────┘
                     │ 1
                     ▼ *
┌───────────────┐ * ┌──────────────────┐ * ┌────────────────────────────┐
│ vw_dim_machine│──►│   vw_fact_daily  │   │  vw_fact_latest_prediction │
└───────┬───────┘ 1 └──────────────────┘   └────────────────────────────┘
        │ 1                                  ▲ *
        └──────────────────────────────────-┘
        │ 1
        ▼ *
┌──────────────────┐
│  vw_fact_anomaly │
└──────────────────┘
```

---

## 3. Recommended DAX measures

Create a **measures table** (Modeling → New table → `Measures = {BLANK()}`) or add
measures to `vw_fact_daily`, then paste:

```dax
-- Energy & throughput -------------------------------------------------------
Total Energy (kWh) =
    SUM ( vw_fact_daily[total_energy_kwh] )

Total Readings =
    SUM ( vw_fact_daily[reading_count] )

-- Reliability ---------------------------------------------------------------
Total Anomalies =
    SUM ( vw_fact_daily[anomaly_count] )

Critical Anomalies =
    SUM ( vw_fact_daily[critical_count] )

Avg Uptime % =
    AVERAGE ( vw_fact_daily[uptime_ratio] ) * 100

Avg Risk Score =
    AVERAGE ( vw_fact_daily[avg_risk_score] )

Fleet Health % =
    100 - [Avg Risk Score]

-- Simplified OEE (availability x performance x quality) ---------------------
OEE % =
VAR Availability = AVERAGE ( vw_fact_daily[uptime_ratio] )
VAR Performance  = DIVIDE ( 100 - [Avg Risk Score], 100 )
VAR Quality      =
    1 - DIVIDE ( [Critical Anomalies], [Total Anomalies] + 1 ) * 0.5
RETURN
    Availability * Performance * Quality * 100

-- Predictive maintenance (current snapshot) --------------------------------
Machines At Risk =
    CALCULATE (
        DISTINCTCOUNT ( vw_fact_latest_prediction[machine_id] ),
        vw_fact_latest_prediction[maintenance_risk_score] >= 55
    )

Min RUL (hours) =
    MIN ( vw_fact_latest_prediction[rul_hours] )

-- Time intelligence ---------------------------------------------------------
Energy MTD =
    TOTALMTD ( [Total Energy (kWh)], vw_dim_date[date_key] )

Anomalies 7d Trend =
    VAR Cur  = [Total Anomalies]
    VAR Prev =
        CALCULATE ( [Total Anomalies],
            DATEADD ( vw_dim_date[date_key], -7, DAY ) )
    RETURN DIVIDE ( Cur - Prev, Prev )
```

---

## 4. Suggested report pages

1. **Executive Overview** — cards: `OEE %`, `Fleet Health %`, `Machines At Risk`,
   `Total Energy (kWh)`; line chart of `Total Anomalies` by `vw_dim_date[date_key]`.
2. **Asset Reliability** — matrix of `vw_dim_machine[name]` × measures, conditional
   formatting on `Avg Risk Score` (green→red).
3. **Predictive Maintenance** — table from `vw_fact_latest_prediction` sorted by
   `maintenance_risk_score`, with `rul_hours` and `next_recommended_maintenance`.
4. **Anomaly Drill-through** — `vw_fact_anomaly` detail table filtered by machine/date.

---

## 5. Scheduled refresh (Power BI Service)

When publishing to the Power BI Service, configure a **Gateway** (or use the cloud
connector for Supabase) and set scheduled refresh to align with the ETL cadence
(`ETL_INTERVAL_SECONDS`, default hourly). Importing the **views** (which read the
small `machine_daily_aggregates` table) keeps refreshes fast even as
`telemetry_raw` grows.
