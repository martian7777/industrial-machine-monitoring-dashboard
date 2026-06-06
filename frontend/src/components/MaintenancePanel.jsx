function riskTone(r) {
  if (r >= 70) return "bad";
  if (r >= 45) return "warn";
  return "good";
}

function fmtRul(hours) {
  if (hours == null) return "—";
  if (hours >= 1000) return `${(hours / 1000).toFixed(1)}k h`;
  return `${Math.round(hours)} h`;
}

export default function MaintenancePanel({ maintenance, machines, onSelect }) {
  const nameById = {};
  machines.forEach((m) => {
    nameById[m.machine.id] = m.machine;
  });

  return (
    <div className="maint">
      <div className="panel-head">
        <h2>Predictive Maintenance</h2>
        <span className="muted">RUL &amp; risk ranking</span>
      </div>
      <div className="maint-table">
        <div className="maint-row head">
          <span>Asset</span>
          <span>Risk</span>
          <span>RUL</span>
          <span>Next service</span>
          <span className="drivers-col">Drivers</span>
        </div>
        {(!maintenance || maintenance.length === 0) && (
          <div className="empty">No predictions yet…</div>
        )}
        {maintenance &&
          maintenance.map((p) => {
            const m = nameById[p.machine_id];
            const tone = riskTone(p.maintenance_risk_score);
            return (
              <div
                key={p.machine_id}
                className="maint-row"
                onClick={() => onSelect && onSelect(p.machine_id)}
                role="button"
              >
                <span className="asset">
                  <strong>{m ? m.code : `M${p.machine_id}`}</strong>
                  <small>{m ? m.type : ""}</small>
                </span>
                <span className={`risk ${tone}`}>
                  <span className="risk-num">{Math.round(p.maintenance_risk_score)}%</span>
                  <span className="risk-track">
                    <span
                      className="risk-meter"
                      style={{ width: `${p.maintenance_risk_score}%` }}
                    />
                  </span>
                </span>
                <span className="rul">{fmtRul(p.rul_hours)}</span>
                <span className="next">{p.next_recommended_maintenance || "—"}</span>
                <span className="drivers-col drivers">{p.drivers}</span>
              </div>
            );
          })}
      </div>
    </div>
  );
}
