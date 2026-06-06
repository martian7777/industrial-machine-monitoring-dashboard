# 📊 Sentinel·SCADA — Industrial Analytics Findings

This document summarizes the live operational findings gathered from the running machine monitoring dashboard and the backend analytics API.

---

## 1. Dashboard Visual Overview

The web interface utilizes a high-fidelity glassmorphic UI design, projecting live sensor feeds, system status cards, machine-specific analytics, and a scrolling anomaly feed.

![Sentinel·SCADA Live Dashboard Overview](C:/Users/saqib/.gemini/antigravity/brain/55cc3813-356d-4178-a98a-2ef086ad0043/artifacts/dashboard_overview.png)

*Figure 1: Main overview of Sentinel·SCADA Web Dashboard, showcasing the 10 monitored assets, current overall OEE, machine health indices, and the real-time sensor plot on the right (ROB-02 selected).*

---

## 2. Fleet Overview & Performance metrics

The system currently tracks **10 machines** across multiple plant locations. Below is a snapshot of the fleet-wide KPIs:

| Metric | Current Value | Meaning |
| :--- | :--- | :--- |
| **Active Fleet Size** | 10 Machines | Total registered IoT assets |
| **Fleet Health Index** | 67.3% | Average health rating across all machines |
| **Overall Equipment Effectiveness (OEE)** | 68.0% | Derived availability × performance × quality metric |
| **Active Faults** | 2 | Machines currently shut down due to critical anomalies |
| **24-Hour Anomalies** | 3 | Total anomaly occurrences over the last 24 hours |
| **Total Energy (24h)** | 43.82 kWh | Fleet-wide cumulative energy consumption |

### API Snapshot: `/api/overview`
```json
{
  "machine_count": 10,
  "running": 8,
  "fault": 2,
  "maintenance": 0,
  "idle": 0,
  "avg_health_index": 67.3,
  "avg_oee": 33.6,
  "anomalies_24h": 3,
  "critical_24h": 3,
  "total_energy_24h": 43.82,
  "high_risk_machines": 0
}
```

---

## 3. Asset-Specific Health & Diagnostics

The assets represent a diverse range of factory machinery. Their current states are as follows:

| Machine ID | Code | Name | Location | Health Index | Status | Primary Driver |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `CNC-01` | CNC Milling Machine | Plant 1 / Line A / Cell 1 | 74.0% | `running` | Moderate usage (29,679h / 40k) |
| 2 | `CNC-02` | CNC Lathe | Plant 1 / Line A / Cell 2 | 79.0% | `running` | Nominal operation |
| 3 | `ROB-01` | 6-Axis Assembly Robot | Plant 1 / Line B / Cell 1 | 77.0% | `running` | Nominal operation |
| 4 | `ROB-02` | Welding Robot | Plant 1 / Line B / Cell 2 | 82.0% | `running` | Nominal operation |
| 5 | `CNV-01` | Main Assembly Conveyor | Plant 1 / Main Line | 59.0% | `running` | High usage (35,713h / 40k) |
| 6 | `CNV-02` | Packaging Conveyor | Plant 1 / Packaging | 59.0% | `running` | High usage (36,429h / 40k) |
| 7 | `PMP-01` | Hydraulic Pump Unit | Plant 1 / Utilities | 56.9% | `running` | High usage (43,078h / 45k) |
| 8 | `CMP-01` | Air Compressor | Plant 1 / Utilities | 55.1% | `fault` | High usage (49,295h / 50k); Critical anomalies |
| 9 | `INJ-01` | Injection Molder | Plant 2 / Line D / Cell 1 | 80.2% | `running` | Nominal operation |
| 10 | `FUR-01` | Heat Treat Furnace | Plant 2 / Line D / Heat | 58.2% | `running` | High usage (53,552h / 80k); Temp stress |

---

## 4. Anomaly Log & Incident Analysis

Anomalies are detected using a combination of **rolling Z-scores** and **hard physical limit thresholds**. Below are the 5 most recent anomalies recorded by the backend:

```json
[
  {
    "id": 6,
    "machine_id": 8,
    "ts": "2026-06-06T15:47:13.273814Z",
    "sensor": "pressure",
    "value": 17.5,
    "z_score": 3.308,
    "severity": "critical",
    "message": "Pressure out of safe range: 17.50 (limit 0.5-12.0)"
  },
  {
    "id": 4,
    "machine_id": 7,
    "ts": "2026-06-06T15:47:09.586315Z",
    "sensor": "temperature",
    "value": 126.42,
    "z_score": 105.689,
    "severity": "critical",
    "message": "Temperature out of safe range: 126.42 (limit 5.0-95.0)"
  },
  {
    "id": 5,
    "machine_id": 7,
    "ts": "2026-06-06T15:47:09.586315Z",
    "sensor": "energy_use",
    "value": 0.748,
    "z_score": 3.996,
    "severity": "warning",
    "message": "Energy Use high anomaly: 0.75 (z=4.00)"
  },
  {
    "id": 3,
    "machine_id": 2,
    "ts": "2026-06-06T15:46:54.938002Z",
    "sensor": "pressure",
    "value": 14.17,
    "z_score": 3.517,
    "severity": "critical",
    "message": "Pressure out of safe range: 14.17 (limit 0.5-12.0)"
  },
  {
    "id": 2,
    "machine_id": 8,
    "ts": "2026-06-06T15:46:41.332857Z",
    "sensor": "pressure",
    "value": 16.68,
    "z_score": null,
    "severity": "critical",
    "message": "Pressure out of safe range: 16.68 (limit 0.5-12.0)"
  }
]
```

### Key Outliers & Physical Limit Violations:
1. **Air Compressor (`CMP-01`)**: Has suffered multiple critical pressure anomalies (e.g. pressure spikes to 16.68 and 17.50 bar, violating the upper safe boundary of 12.0 bar). This caused the system to transition the compressor's state to `fault`.
2. **Hydraulic Pump (`PMP-01`)**: Tripped a major critical temperature anomaly (vibration or internal oil temperature surged to 126.42°C, violating the safe upper boundary of 95.0°C). This was accompanied by a warning anomaly on energy usage (0.75 kW vs z-score threshold of 4.00), demonstrating a clear correlation between thermal stress and load.

---

## 5. Predictive Maintenance & Risk Profiling

The backend ranks assets by risk using wear and stress inputs:
* **`CMP-01` (Air Compressor)** has the lowest Remaining Useful Life (RUL) of **689 hours** due to approaching its maximum design operating hours of 50,000h (currently at 49,295h). The risk score is **44.95%**, indicating immediate maintenance needs.
* **`PMP-01` (Hydraulic Pump Unit)** has an RUL of **1,921 hours** (43,078h of 45,000h used) with a risk score of **43.08%**.
* The remaining machinery operates with nominal RUL hours ranging from 15,000h to 40,000h.

> [!TIP]
> The system has flagged `CMP-01` and `PMP-01` as priority service candidates for the next scheduled factory downtime on **2026-07-06**.
