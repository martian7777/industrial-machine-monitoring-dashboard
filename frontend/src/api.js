// REST + WebSocket helpers for the monitoring backend.

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
export const WS_URL =
  import.meta.env.VITE_WS_URL || API_BASE.replace(/^http/, "ws") + "/ws/live";

async function getJSON(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

export const api = {
  overview: () => getJSON("/api/overview"),
  machinesStatus: () => getJSON("/api/machines/status"),
  anomalies: (limit = 50) => getJSON(`/api/anomalies?limit=${limit}`),
  maintenance: () => getJSON("/api/maintenance"),
  telemetry: (machineId, limit = 120) =>
    getJSON(`/api/machines/${machineId}/telemetry?limit=${limit}`),
};
