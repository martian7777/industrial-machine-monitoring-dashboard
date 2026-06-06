import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const axisStyle = { fontSize: 10, fill: "rgba(255,255,255,0.45)" };
const grid = "rgba(255,255,255,0.06)";

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tip">
      <div className="chart-tip-t">{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} className="chart-tip-row">
          <span className="dot" style={{ background: p.color }} />
          {p.name}: <strong>{Number(p.value).toFixed(2)}</strong>
        </div>
      ))}
    </div>
  );
}

function MiniChart({ title, dataKey, color, data, area }) {
  const Wrapper = area ? AreaChart : LineChart;
  return (
    <div className="chart-card glass">
      <div className="chart-title">
        <span className="dot" style={{ background: color }} /> {title}
      </div>
      <ResponsiveContainer width="100%" height={150}>
        <Wrapper data={data} margin={{ top: 6, right: 10, left: -18, bottom: 0 }}>
          <defs>
            <linearGradient id={`grad-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.4} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={grid} vertical={false} />
          <XAxis dataKey="t" tick={axisStyle} minTickGap={40} axisLine={false} tickLine={false} />
          <YAxis tick={axisStyle} width={42} axisLine={false} tickLine={false} domain={["auto", "auto"]} />
          <Tooltip content={<ChartTooltip />} />
          {area ? (
            <Area
              type="monotone"
              dataKey={dataKey}
              name={title}
              stroke={color}
              strokeWidth={2}
              fill={`url(#grad-${dataKey})`}
              isAnimationActive={false}
              dot={false}
            />
          ) : (
            <Line
              type="monotone"
              dataKey={dataKey}
              name={title}
              stroke={color}
              strokeWidth={2}
              isAnimationActive={false}
              dot={false}
            />
          )}
        </Wrapper>
      </ResponsiveContainer>
    </div>
  );
}

export default function TelemetryCharts({ data }) {
  if (!data || !data.length) {
    return <div className="empty">Select a machine — streaming telemetry will appear here.</div>;
  }
  return (
    <div className="charts-grid">
      <MiniChart title="Temperature (°C)" dataKey="temperature" color="#ff6b6b" data={data} area />
      <MiniChart title="Vibration (mm/s)" dataKey="vibration" color="#4dd4ac" data={data} />
      <MiniChart title="Pressure (bar)" dataKey="pressure" color="#5b9dff" data={data} />
      <MiniChart title="Energy (kWh)" dataKey="energy_use" color="#ffd166" data={data} area />
    </div>
  );
}
