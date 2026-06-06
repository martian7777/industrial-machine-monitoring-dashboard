function Tile({ label, value, unit, sub, tone }) {
  return (
    <div className={`kpi ${tone || ""}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">
        {value}
        {unit && <span className="kpi-unit">{unit}</span>}
      </div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}

export default function KpiStrip({ overview }) {
  const o = overview || {};
  const fmt = (v, d = 0) => (v == null ? "—" : Number(v).toFixed(d));

  return (
    <div className="kpi-strip">
      <Tile label="Overall OEE" value={fmt(o.avg_oee, 1)} unit="%" tone="accent"
            sub="Availability × Performance × Quality" />
      <Tile label="Avg Health Index" value={fmt(o.avg_health_index, 1)} unit="%"
            tone={o.avg_health_index >= 70 ? "good" : o.avg_health_index >= 45 ? "warn" : "bad"} />
      <Tile label="Running" value={fmt(o.running)} sub={`of ${fmt(o.machine_count)} machines`} tone="good" />
      <Tile label="In Maintenance" value={fmt(o.maintenance)} tone="warn" />
      <Tile label="Faulted" value={fmt(o.fault)} tone={o.fault > 0 ? "bad" : ""} />
      <Tile label="High-Risk Assets" value={fmt(o.high_risk_machines)}
            tone={o.high_risk_machines > 0 ? "warn" : "good"} />
      <Tile label="Anomalies · 24h" value={fmt(o.anomalies_24h)}
            sub={`${fmt(o.critical_24h)} critical`} tone={o.critical_24h > 0 ? "bad" : ""} />
      <Tile label="Energy · 24h" value={fmt(o.total_energy_24h, 1)} unit="kWh" />
    </div>
  );
}
