import { useCallback, useEffect, useRef, useState } from "react";
import { api, WS_URL } from "../api";

const POLL_MS = 5000;
const MAX_FEED = 60;

// Central data hook: seeds from REST, then keeps state live via WebSocket,
// with a slow REST poll as a safety net for KPIs / status.
export function useLiveData() {
  const [overview, setOverview] = useState(null);
  const [machines, setMachines] = useState([]);
  const [maintenance, setMaintenance] = useState([]);
  const [feed, setFeed] = useState([]); // recent anomaly events (live)
  const [series, setSeries] = useState({}); // machine_id -> [points]
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);

  const refresh = useCallback(async () => {
    try {
      const [ov, ms, mt, an] = await Promise.all([
        api.overview(),
        api.machinesStatus(),
        api.maintenance(),
        api.anomalies(MAX_FEED),
      ]);
      setOverview(ov);
      setMachines(ms);
      setMaintenance(mt);
      setFeed(an);
    } catch (e) {
      // backend may still be warming up; poll will retry
      console.warn("refresh failed", e.message);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  // WebSocket live stream
  useEffect(() => {
    let alive = true;
    let reconnectTimer;

    function connect() {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => alive && setConnected(true);
      ws.onclose = () => {
        if (!alive) return;
        setConnected(false);
        reconnectTimer = setTimeout(connect, 2000);
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (evt) => {
        let msg;
        try {
          msg = JSON.parse(evt.data);
        } catch {
          return;
        }
        if (msg.type !== "telemetry") return;

        // append to per-machine series (keep last 120 points)
        setSeries((prev) => {
          const arr = prev[msg.machine_id] ? [...prev[msg.machine_id]] : [];
          arr.push({
            t: new Date(msg.reading.ts).toLocaleTimeString(),
            temperature: msg.reading.temperature,
            vibration: msg.reading.vibration,
            pressure: msg.reading.pressure,
            energy_use: msg.reading.energy_use,
          });
          if (arr.length > 120) arr.shift();
          return { ...prev, [msg.machine_id]: arr };
        });

        // live patch machine card status / prediction
        setMachines((prev) =>
          prev.map((m) =>
            m.machine.id === msg.machine_id
              ? {
                  ...m,
                  machine: { ...m.machine, status: msg.status },
                  latest: { ...(m.latest || {}), ...msg.reading, machine_id: msg.machine_id },
                  prediction: {
                    ...(m.prediction || {}),
                    maintenance_risk_score: msg.prediction.risk,
                    health_index: msg.prediction.health,
                    rul_hours: msg.prediction.rul_hours,
                  },
                }
              : m
          )
        );

        // push anomalies into the live feed
        if (msg.anomalies && msg.anomalies.length) {
          setFeed((prev) => {
            const events = msg.anomalies.map((a, i) => ({
              id: `${Date.now()}-${msg.machine_id}-${i}`,
              ts: new Date().toISOString(),
              machine_id: msg.machine_id,
              machine_code: msg.machine_code,
              sensor: a.sensor,
              severity: a.severity,
              value: a.value,
              message: a.message,
            }));
            return [...events, ...prev].slice(0, MAX_FEED);
          });
        }
      };
    }

    connect();
    return () => {
      alive = false;
      clearTimeout(reconnectTimer);
      wsRef.current && wsRef.current.close();
    };
  }, []);

  return { overview, machines, maintenance, feed, series, connected, refresh };
}
