import React, { useEffect, useState } from "react";
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import { getAnomalies } from "../api";

const severityColor = { high: "#ff5d6c", medium: "#ffb84d", low: "#63d2a5" };

export default function AnomalyChart({ routeId }) {
  const [anomalies, setAnomalies] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!routeId) return;
    setLoading(true);
    setError(null);
    getAnomalies(routeId)
      .then((res) => setAnomalies(res.anomalies || []))
      .catch((e) => setError(e?.response?.data?.detail || "Failed to load anomalies"))
      .finally(() => setLoading(false));
  }, [routeId]);

  const points = anomalies.map((a) => ({
    x: new Date(a.timestamp).getTime(),
    y: a.vehicle_count,
    severity: a.severity,
    method: a.method,
    description: a.description,
    label: new Date(a.timestamp).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit" }),
  }));

  return (
    <div className="card">
      <div className="card-header">
        <h3>Anomaly Detection — {routeId}</h3>
        <span className="tag">{anomalies.length} detected</span>
      </div>
      {loading && <p className="muted">Scanning for anomalies…</p>}
      {error && <p className="error">{error}</p>}
      {!loading && !error && (
        <>
          <ResponsiveContainer width="100%" height={280}>
            <ScatterChart margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2b38" />
              <XAxis
                dataKey="x" type="number" domain={["dataMin", "dataMax"]}
                tickFormatter={(v) => new Date(v).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                tick={{ fill: "#8fa3b3", fontSize: 11 }}
              />
              <YAxis dataKey="y" tick={{ fill: "#8fa3b3", fontSize: 11 }} name="Vehicle Count" />
              <ZAxis range={[60, 60]} />
              <Tooltip
                contentStyle={{ background: "#111823", border: "1px solid #223142", color: "#e6edf3" }}
                formatter={(value, name, props) => [value, name]}
                labelFormatter={() => ""}
                content={({ active, payload }) =>
                  active && payload?.length ? (
                    <div style={{ background: "#111823", border: "1px solid #223142", padding: 8, borderRadius: 6 }}>
                      <div>{payload[0].payload.label}</div>
                      <div>Vehicles: {payload[0].payload.y}</div>
                      <div>Severity: {payload[0].payload.severity}</div>
                      <div style={{ maxWidth: 220 }}>{payload[0].payload.description}</div>
                    </div>
                  ) : null
                }
              />
              <Legend />
              {["high", "medium", "low"].map((sev) => (
                <Scatter
                  key={sev}
                  name={sev}
                  data={points.filter((p) => p.severity === sev)}
                  fill={severityColor[sev]}
                />
              ))}
            </ScatterChart>
          </ResponsiveContainer>
          <ul className="anomaly-list">
            {anomalies.slice(0, 6).map((a, i) => (
              <li key={i}>
                <span className={`dot ${a.severity}`} /> {a.description}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
