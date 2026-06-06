import { useEffect, useMemo, useState } from "react";
import { useLiveData } from "./hooks/useLiveData";
import KpiStrip from "./components/KpiStrip";
import MachineCard from "./components/MachineCard";
import TelemetryCharts from "./components/TelemetryCharts";
import AnomalyLog from "./components/AnomalyLog";
import MaintenancePanel from "./components/MaintenancePanel";
import { api } from "./api";

export default function App() {
  const { overview, machines, maintenance, feed, series, connected } = useLiveData();
  const [selectedId, setSelectedId] = useState(null);
  const [history, setHistory] = useState([]);

  // default selection -> first machine
  useEffect(() => {
    if (selectedId == null && machines.length) {
      setSelectedId(machines[0].machine.id);
    }
  }, [machines, selectedId]);

  // seed chart history from REST when selection changes
  useEffect(() => {
    if (selectedId == null) return;
    let alive = true;
    api
      .telemetry(selectedId, 120)
      .then((rows) => {
        if (!alive) return;
        setHistory(
          rows.map((r) => ({
            t: new Date(r.ts).toLocaleTimeString(),
            temperature: Number(r.temperature),
            vibration: Number(r.vibration),
            pressure: Number(r.pressure),
            energy_use: Number(r.energy_use),
          }))
        );
      })
      .catch(() => setHistory([]));
    return () => {
      alive = false;
    };
  }, [selectedId]);

  // merge REST history with live websocket points for the selected machine
  const chartData = useMemo(() => {
    const live = series[selectedId] || [];
    if (!live.length) return history;
    if (!history.length) return live;
    // append only the live points newer than what history already covers
    return [...history, ...live].slice(-120);
  }, [history, series, selectedId]);

  const selected = machines.find((m) => m.machine.id === selectedId) || null;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">⬡</div>
          <div>
            <h1>SENTINEL<span className="accent">·SCADA</span></h1>
            <p className="subtitle">Industrial Machine Monitoring &amp; Predictive Maintenance</p>
          </div>
        </div>
        <div className={`conn ${connected ? "online" : "offline"}`}>
          <span className="dot" />
          {connected ? "LIVE · WebSocket" : "RECONNECTING…"}
        </div>
      </header>

      <KpiStrip overview={overview} />

      <main className="layout">
        <section className="panel machines-panel">
          <div className="panel-head">
            <h2>Machine Fleet</h2>
            <span className="muted">{machines.length} assets</span>
          </div>
          <div className="machine-grid">
            {machines.map((m) => (
              <MachineCard
                key={m.machine.id}
                data={m}
                active={m.machine.id === selectedId}
                onClick={() => setSelectedId(m.machine.id)}
              />
            ))}
            {!machines.length && <div className="empty">Waiting for telemetry…</div>}
          </div>
        </section>

        <section className="panel charts-panel">
          <div className="panel-head">
            <h2>
              Telemetry
              {selected && <span className="muted"> · {selected.machine.name}</span>}
            </h2>
          </div>
          <TelemetryCharts data={chartData} />
        </section>

        <section className="panel feed-panel">
          <AnomalyLog feed={feed} />
        </section>

        <section className="panel maint-panel">
          <MaintenancePanel
            maintenance={maintenance}
            machines={machines}
            onSelect={setSelectedId}
          />
        </section>
      </main>

      <footer className="footer">
        <span>PostgreSQL / Supabase · FastAPI · Recharts</span>
        <span className="muted">Power BI star-schema views available in /powerbi</span>
      </footer>
    </div>
  );
}
