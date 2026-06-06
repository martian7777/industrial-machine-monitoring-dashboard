const STATUS_META = {
  running: { label: "RUNNING", tone: "good" },
  maintenance: { label: "MAINTENANCE", tone: "warn" },
  fault: { label: "FAULT", tone: "bad" },
  idle: { label: "IDLE", tone: "muted" },
};

function Gauge({ value }) {
  // simple conic health ring
  const v = Math.max(0, Math.min(100, value ?? 0));
  const tone = v >= 70 ? "var(--good)" : v >= 45 ? "var(--warn)" : "var(--bad)";
  return (
    <div
      className="gauge"
      style={{
        background: `conic-gradient(${tone} ${v * 3.6}deg, rgba(255,255,255,0.07) 0deg)`,
      }}
    >
      <div className="gauge-inner">
        <span className="gauge-val">{Math.round(v)}</span>
        <span className="gauge-cap">health</span>
      </div>
    </div>
  );
}

function Metric({ label, value, unit }) {
  return (
    <div className="metric">
      <span className="metric-label">{label}</span>
      <span className="metric-value">
        {value == null ? "—" : Number(value).toFixed(1)}
        <small>{unit}</small>
      </span>
    </div>
  );
}

export default function MachineCard({ data, active, onClick }) {
  const { machine, latest, prediction, open_anomalies } = data;
  const meta = STATUS_META[machine.status] || STATUS_META.idle;
  const risk = prediction?.maintenance_risk_score ?? 0;
  const health = prediction?.health_index ?? 100;

  return (
    <button
      className={`machine-card glass ${meta.tone} ${active ? "active" : ""}`}
      onClick={onClick}
    >
      <div className="mc-top">
        <div>
          <div className="mc-code">{machine.code}</div>
          <div className="mc-name">{machine.name}</div>
          <div className="mc-type">{machine.type}</div>
        </div>
        <Gauge value={health} />
      </div>

      <div className={`status-pill ${meta.tone}`}>
        <span className="dot" />
        {meta.label}
      </div>

      <div className="mc-metrics">
        <Metric label="Temp" value={latest?.temperature} unit="°C" />
        <Metric label="Vib" value={latest?.vibration} unit="mm/s" />
        <Metric label="Pres" value={latest?.pressure} unit="bar" />
        <Metric label="kWh" value={latest?.energy_use} unit="" />
      </div>

      <div className="mc-foot">
        <div className="risk-bar">
          <div
            className="risk-fill"
            style={{
              width: `${risk}%`,
              background:
                risk >= 70 ? "var(--bad)" : risk >= 45 ? "var(--warn)" : "var(--good)",
            }}
          />
        </div>
        <div className="mc-foot-labels">
          <span>risk {Math.round(risk)}%</span>
          {open_anomalies > 0 && <span className="badge bad">{open_anomalies} alerts 24h</span>}
        </div>
      </div>
    </button>
  );
}
