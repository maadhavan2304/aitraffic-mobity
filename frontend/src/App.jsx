import React, { useEffect, useState } from "react";
import "./styles.css";
import { getRoutes, getSummary, generateSynthetic, uploadCsv } from "./api";
import ForecastChart from "./components/ForecastChart.jsx";
import AnomalyChart from "./components/AnomalyChart.jsx";
import Recommendations from "./components/Recommendations.jsx";
import Simulation from "./components/Simulation.jsx";
import RouteComparison from "./components/RouteComparison.jsx";

export default function App() {
  const [routes, setRoutes] = useState([]);
  const [activeRoute, setActiveRoute] = useState(null);
  const [summary, setSummary] = useState(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);

  const refresh = () => {
    getRoutes().then((r) => {
      setRoutes(r);
      if (r.length && !activeRoute) setActiveRoute(r[0]);
    });
    getSummary().then(setSummary).catch(() => {});
  };

  useEffect(() => { refresh(); }, []);

  const handleGenerate = () => {
    setBusy(true);
    generateSynthetic(30)
      .then((res) => {
        setToast(`Synthetic dataset generated: ${res.rows_ingested} rows across ${res.routes.length} routes.`);
        refresh();
      })
      .catch(() => setToast("Failed to generate synthetic data."))
      .finally(() => setBusy(false));
  };

  const handleUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    uploadCsv(file)
      .then((res) => {
        setToast(`Uploaded: ${res.rows_ingested} rows ingested.`);
        refresh();
      })
      .catch((err) => setToast(err?.response?.data?.detail || "Upload failed."))
      .finally(() => setBusy(false));
  };

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <h1>🚦 AI Traffic &amp; Mobility Forecasting</h1>
          <p className="subtitle">Forecasting · Anomaly Detection · Optimization · Simulation</p>
        </div>
        <div className="topbar-actions">
          <label className="btn-secondary">
            Upload CSV
            <input type="file" accept=".csv" hidden onChange={handleUpload} />
          </label>
          <button className="btn-primary" onClick={handleGenerate} disabled={busy}>
            {busy ? "Working…" : "Generate Demo Data"}
          </button>
        </div>
      </header>

      {toast && (
        <div className="toast" onClick={() => setToast(null)}>{toast}</div>
      )}

      {summary && (
        <div className="summary-strip">
          <div><span>{summary.total_records ?? 0}</span> records</div>
          <div><span>{summary.route_count ?? 0}</span> routes</div>
          <div>
            <span>
              {summary.start_date ? new Date(summary.start_date).toLocaleDateString() : "—"} →{" "}
              {summary.end_date ? new Date(summary.end_date).toLocaleDateString() : "—"}
            </span>
          </div>
        </div>
      )}

      {routes.length === 0 ? (
        <div className="empty-state">
          <h2>No data yet</h2>
          <p>Upload a CSV (timestamp, route_id, vehicle_count, ...) or generate a synthetic demo dataset to get started.</p>
          <button className="btn-primary" onClick={handleGenerate}>Generate Demo Data</button>
        </div>
      ) : (
        <>
          <nav className="route-tabs">
            {routes.map((r) => (
              <button
                key={r}
                className={`route-tab ${activeRoute === r ? "active" : ""}`}
                onClick={() => setActiveRoute(r)}
              >
                {r}
              </button>
            ))}
          </nav>

          {activeRoute && (
            <div className="grid">
              <ForecastChart routeId={activeRoute} />
              <AnomalyChart routeId={activeRoute} />
              <Recommendations routeId={activeRoute} />
              <Simulation routeId={activeRoute} />
              <div className="full-span">
                <RouteComparison routes={routes} />
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
