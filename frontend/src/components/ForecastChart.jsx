import React, { useEffect, useState } from "react";
import {
  ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { getHistory, getForecast } from "../api";

const fmt = (ts) =>
  new Date(ts).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit" });

export default function ForecastChart({ routeId }) {
  const [horizon, setHorizon] = useState("24h");
  const [data, setData] = useState([]);
  const [meta, setMeta] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!routeId) return;
    setLoading(true);
    setError(null);
    Promise.all([getHistory(routeId, 72), getForecast(routeId, horizon)])
      .then(([hist, fcst]) => {
        const histPoints = hist.map((h) => ({
          timestamp: h.timestamp,
          label: fmt(h.timestamp),
          historical: Math.round(h.vehicle_count),
        }));
        const fcstPoints = fcst.points.map((p) => ({
          timestamp: p.timestamp,
          label: fmt(p.timestamp),
          predicted: Math.round(p.predicted_volume),
          band: p.upper_bound && p.lower_bound ? Math.round(p.upper_bound - p.lower_bound) : 0,
          lower_bound: p.lower_bound ? Math.round(p.lower_bound) : null,
        }));
        setData([...histPoints, ...fcstPoints]);
        setMeta(fcst);
      })
      .catch((e) => setError(e?.response?.data?.detail || "Failed to load forecast"))
      .finally(() => setLoading(false));
  }, [routeId, horizon]);

  return (
    <div className="card">
      <div className="card-header">
        <h3>Historical vs Predicted Traffic — {routeId}</h3>
        <div className="pill-group">
          {["24h", "7d"].map((h) => (
            <button key={h} className={`pill ${horizon === h ? "active" : ""}`} onClick={() => setHorizon(h)}>
              Next {h === "24h" ? "24 Hours" : "7 Days"}
            </button>
          ))}
        </div>
      </div>
      {loading && <p className="muted">Loading forecast…</p>}
      {error && <p className="error">{error}</p>}
      {!loading && !error && (
        <>
          <ResponsiveContainer width="100%" height={320}>
            <ComposedChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2b38" />
              <XAxis dataKey="label" tick={{ fill: "#8fa3b3", fontSize: 11 }} interval="preserveStartEnd" />
              <YAxis tick={{ fill: "#8fa3b3", fontSize: 11 }} />
              <Tooltip contentStyle={{ background: "#111823", border: "1px solid #223142", color: "#e6edf3" }} />
              <Legend />
              <Area type="monotone" dataKey="lower_bound" stroke="none" fill="#5b8cff" fillOpacity={0.08} name="Confidence" />
              <Line type="monotone" dataKey="historical" stroke="#63d2a5" dot={false} strokeWidth={2} name="Historical" />
              <Line type="monotone" dataKey="predicted" stroke="#5b8cff" dot={false} strokeWidth={2} strokeDasharray="5 3" name="Predicted" />
            </ComposedChart>
          </ResponsiveContainer>
          {meta && (
            <div className="meta-row">
              <span className="tag">Model: {meta.model_used}</span>
              <span className="tag">Peak windows: {meta.peak_hours.slice(0, 3).join(", ")}</span>
            </div>
          )}
          {meta?.alerts?.length > 0 && (
            <ul className="alert-list">
              {meta.alerts.map((a, i) => (
                <li key={i}>⚠ {a}</li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
