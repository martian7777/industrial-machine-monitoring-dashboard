-- ============================================================================
--  Industrial Machine Monitoring — Database Schema
--  Target: PostgreSQL 14+ / Supabase
--
--  Run this in the Supabase SQL Editor (or psql) for a complete setup.
--  The FastAPI backend can also auto-create these tables on startup
--  (AUTO_INIT_DB=true), but the Power BI VIEWS below are only created here.
-- ============================================================================

-- ----------------------------------------------------------------------------
--  Dimension: machines
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS machines (
    id              SERIAL PRIMARY KEY,
    code            TEXT        NOT NULL UNIQUE,          -- e.g. CNC-01
    name            TEXT        NOT NULL,
    type            TEXT        NOT NULL,                 -- CNC Mill, Robotic Arm, ...
    location        TEXT        NOT NULL,                 -- plant / line / cell
    install_date    DATE        NOT NULL,
    rated_power_kw  NUMERIC(8,2) NOT NULL DEFAULT 0,
    status          TEXT        NOT NULL DEFAULT 'running' -- running | idle | maintenance | fault
);

-- ----------------------------------------------------------------------------
--  Fact: telemetry_raw  (high-volume IoT readings)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS telemetry_raw (
    id              BIGSERIAL PRIMARY KEY,
    machine_id      INTEGER     NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
    ts              TIMESTAMPTZ NOT NULL DEFAULT now(),
    temperature     NUMERIC(7,2) NOT NULL,               -- deg C
    vibration       NUMERIC(7,3) NOT NULL,               -- mm/s RMS
    pressure        NUMERIC(7,2) NOT NULL,               -- bar
    energy_use      NUMERIC(9,3) NOT NULL,               -- kWh (interval)
    rpm             NUMERIC(8,1) NOT NULL DEFAULT 0,
    operating_hours NUMERIC(10,2) NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_telemetry_machine_ts ON telemetry_raw (machine_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_ts          ON telemetry_raw (ts DESC);

-- ----------------------------------------------------------------------------
--  Fact: anomalies
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS anomalies (
    id              BIGSERIAL PRIMARY KEY,
    machine_id      INTEGER     NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
    telemetry_id    BIGINT      REFERENCES telemetry_raw(id) ON DELETE SET NULL,
    ts              TIMESTAMPTZ NOT NULL DEFAULT now(),
    sensor          TEXT        NOT NULL,                 -- temperature | vibration | pressure | energy_use
    value           NUMERIC(10,3) NOT NULL,
    z_score         NUMERIC(8,3),
    severity        TEXT        NOT NULL,                 -- info | warning | critical
    message         TEXT        NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_anomalies_machine_ts ON anomalies (machine_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_ts          ON anomalies (ts DESC);

-- ----------------------------------------------------------------------------
--  Fact: maintenance_predictions  (latest prediction per machine kept fresh)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS maintenance_predictions (
    id                          BIGSERIAL PRIMARY KEY,
    machine_id                  INTEGER     NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
    ts                          TIMESTAMPTZ NOT NULL DEFAULT now(),
    maintenance_risk_score      NUMERIC(5,2) NOT NULL,    -- 0..100
    rul_hours                   NUMERIC(10,1) NOT NULL,   -- Remaining Useful Life
    next_recommended_maintenance DATE,
    health_index                NUMERIC(5,2) NOT NULL,    -- 0..100 (100 = perfect)
    drivers                     TEXT                       -- short explanation of top risk drivers
);

CREATE INDEX IF NOT EXISTS idx_predictions_machine_ts ON maintenance_predictions (machine_id, ts DESC);

-- ----------------------------------------------------------------------------
--  Aggregate: machine_daily_aggregates  (ETL output for BI)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS machine_daily_aggregates (
    id                  BIGSERIAL PRIMARY KEY,
    machine_id          INTEGER NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
    day                 DATE    NOT NULL,
    avg_temperature     NUMERIC(7,2),
    max_temperature     NUMERIC(7,2),
    avg_vibration       NUMERIC(7,3),
    max_vibration       NUMERIC(7,3),
    avg_pressure        NUMERIC(7,2),
    total_energy_kwh    NUMERIC(12,3),
    reading_count       INTEGER,
    anomaly_count       INTEGER,
    critical_count      INTEGER,
    uptime_ratio        NUMERIC(5,4),                     -- 0..1
    avg_risk_score      NUMERIC(5,2),
    UNIQUE (machine_id, day)
);

CREATE INDEX IF NOT EXISTS idx_daily_day ON machine_daily_aggregates (day DESC);

-- ----------------------------------------------------------------------------
--  Seed: 10 machines (idempotent)
-- ----------------------------------------------------------------------------
INSERT INTO machines (code, name, type, location, install_date, rated_power_kw, status) VALUES
    ('CNC-01',  'CNC Milling Center A',   'CNC Mill',         'Plant 1 / Line A / Cell 1', DATE '2019-03-12', 22.00, 'running'),
    ('CNC-02',  'CNC Milling Center B',   'CNC Mill',         'Plant 1 / Line A / Cell 2', DATE '2020-07-01', 22.00, 'running'),
    ('ROB-01',  'Robotic Arm Welder',     'Robotic Arm',      'Plant 1 / Line B / Cell 1', DATE '2021-01-20', 11.50, 'running'),
    ('ROB-02',  'Robotic Arm Pick&Place', 'Robotic Arm',      'Plant 1 / Line B / Cell 2', DATE '2022-05-09',  9.00, 'running'),
    ('CNV-01',  'Packaging Conveyor 1',   'Conveyor',         'Plant 1 / Line C / Pack',   DATE '2018-11-03',  7.50, 'running'),
    ('CNV-02',  'Packaging Conveyor 2',   'Conveyor',         'Plant 1 / Line C / Pack',   DATE '2018-11-03',  7.50, 'running'),
    ('PMP-01',  'Hydraulic Pump Unit',    'Hydraulic Pump',   'Plant 1 / Utilities',       DATE '2017-06-15', 30.00, 'running'),
    ('CMP-01',  'Air Compressor',         'Air Compressor',   'Plant 1 / Utilities',       DATE '2016-02-28', 37.00, 'running'),
    ('INJ-01',  'Injection Molder',       'Injection Molder', 'Plant 2 / Line D / Cell 1', DATE '2020-09-30', 45.00, 'running'),
    ('FUR-01',  'Heat Treat Furnace',     'Furnace',          'Plant 2 / Line D / Heat',   DATE '2015-04-10', 60.00, 'running')
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
--  POWER BI — Star Schema Views
--  Import these views from Power BI Desktop (Get Data -> PostgreSQL database).
--  Build relationships: dim_machine[machine_id] 1->* each fact view.
-- ============================================================================

-- Dimension: machine
CREATE OR REPLACE VIEW vw_dim_machine AS
SELECT
    m.id                AS machine_id,
    m.code,
    m.name,
    m.type,
    m.location,
    split_part(m.location, ' / ', 1) AS plant,
    split_part(m.location, ' / ', 2) AS line,
    m.install_date,
    m.rated_power_kw,
    m.status,
    DATE_PART('year', AGE(now(), m.install_date)) AS age_years
FROM machines m;

-- Dimension: date (covers any day we have data for; extend the range as needed)
CREATE OR REPLACE VIEW vw_dim_date AS
WITH bounds AS (
    SELECT
        COALESCE(MIN(day), CURRENT_DATE) AS min_d,
        COALESCE(MAX(day), CURRENT_DATE) AS max_d
    FROM machine_daily_aggregates
)
SELECT
    d::date                              AS date_key,
    EXTRACT(YEAR    FROM d)::int         AS year,
    EXTRACT(QUARTER FROM d)::int         AS quarter,
    EXTRACT(MONTH   FROM d)::int         AS month,
    TO_CHAR(d, 'Mon')                    AS month_name,
    EXTRACT(DAY     FROM d)::int         AS day_of_month,
    EXTRACT(ISODOW  FROM d)::int         AS day_of_week,
    TO_CHAR(d, 'Dy')                     AS day_name,
    (EXTRACT(ISODOW FROM d) >= 6)        AS is_weekend
FROM bounds, generate_series(bounds.min_d, bounds.max_d, INTERVAL '1 day') AS d;

-- Fact: daily aggregates (primary BI fact — fast to import)
CREATE OR REPLACE VIEW vw_fact_daily AS
SELECT
    a.machine_id,
    a.day                AS date_key,
    a.avg_temperature,
    a.max_temperature,
    a.avg_vibration,
    a.max_vibration,
    a.avg_pressure,
    a.total_energy_kwh,
    a.reading_count,
    a.anomaly_count,
    a.critical_count,
    a.uptime_ratio,
    a.avg_risk_score
FROM machine_daily_aggregates a;

-- Fact: anomalies (for drill-through)
CREATE OR REPLACE VIEW vw_fact_anomaly AS
SELECT
    an.id            AS anomaly_id,
    an.machine_id,
    an.ts::date      AS date_key,
    an.ts,
    an.sensor,
    an.value,
    an.z_score,
    an.severity,
    an.message
FROM anomalies an;

-- Fact: latest maintenance prediction per machine (current health snapshot)
CREATE OR REPLACE VIEW vw_fact_latest_prediction AS
SELECT DISTINCT ON (p.machine_id)
    p.machine_id,
    p.ts,
    p.maintenance_risk_score,
    p.rul_hours,
    p.next_recommended_maintenance,
    p.health_index,
    p.drivers
FROM maintenance_predictions p
ORDER BY p.machine_id, p.ts DESC;
