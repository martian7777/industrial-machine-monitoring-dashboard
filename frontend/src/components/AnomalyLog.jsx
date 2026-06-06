function timeOf(ts) {
  try {
    return new Date(ts).toLocaleTimeString();
  } catch {
    return "--:--:--";
  }
}

export default function AnomalyLog({ feed }) {
  return (
    <div className="anomaly-log">
      <div className="panel-head">
        <h2>Anomaly Feed</h2>
        <span className="muted live-tag">● live</span>
      </div>
      <div className="terminal">
        {(!feed || feed.length === 0) && (
          <div className="term-line muted">system: monitoring nominal — no anomalies</div>
        )}
        {feed &&
          feed.map((a) => (
            <div key={a.id || `${a.machine_id}-${a.ts}-${a.sensor}`} className={`term-line ${a.severity}`}>
              <span className="term-time">[{timeOf(a.ts)}]</span>
              <span className={`term-sev ${a.severity}`}>{(a.severity || "info").toUpperCase()}</span>
              <span className="term-code">{a.machine_code || `M${a.machine_id}`}</span>
              <span className="term-msg">{a.message}</span>
            </div>
          ))}
      </div>
    </div>
  );
}
