import React, { useEffect, useState } from "react";
import { getScenarios, runSimulation } from "../api";

const scenarioLabels = {
  road_closure: "Road Closure",
  heavy_rain: "Heavy Rain",
  event_surge: "Festival / Event Surge",
  vehicle_load_increase: "Increased Vehicle Load",
};

export default function Simulation({ routeId }) {
  const [scenarios, setScenarios] = useState([]);
  const [scenario, setScenario] = useState("road_closure");
  const [intensity, setIntensity] = useState(1.5);
  const [duration, setDuration] = useState(4);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getScenarios().then(setScenarios).catch(() => setScenarios(Object.keys(scenarioLabels)));
  }, []);

  const run = () => {
    if (!routeId) return;
    setLoading(true);
    runSimulation({ route_id: routeId, scenario, intensity: Number(intensity), duration_hours: Number(duration) })
      .then(setResult)
      .finally(() => setLoading(false));
  };

  return (
    <div className="card">
      <div className="card-header">
        <h3>Scenario Simulation — {routeId}</h3>
      </div>
      <div className="sim-controls">
        <label>
          Scenario
          <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
            {(scenarios.length ? scenarios : Object.keys(scenarioLabels)).map((s) => (
              <option key={s} value={s}>{scenarioLabels[s] || s}</option>
            ))}
          </select>
        </label>
        <label>
          Intensity ({intensity}x)
          <input type="range" min="0.5" max="3" step="0.1" value={intensity}
                 onChange={(e) => setIntensity(e.target.value)} />
        </label>
        <label>
          Duration (hrs)
          <input type="number" min="1" max="24" value={duration} onChange={(e) => setDuration(e.target.value)} />
        </label>
        <button className="btn-primary" onClick={run} disabled={loading}>
          {loading ? "Simulating…" : "Run Simulation"}
        </button>
      </div>
      {result && (
        <div className="sim-result">
          <div className="sim-stats">
            <div>
              <span className="stat-label">Baseline Congestion</span>
              <span className="stat-value">{result.baseline_congestion}</span>
            </div>
            <div>
              <span className="stat-label">Projected Congestion</span>
              <span className="stat-value warn">{result.projected_congestion}</span>
            </div>
            <div>
              <span className="stat-label">Delta</span>
              <span className="stat-value warn">{result.congestion_delta_pct}%</span>
            </div>
            <div>
              <span className="stat-label">Est. Delay</span>
              <span className="stat-value warn">{result.estimated_delay_minutes} min</span>
            </div>
          </div>
          <p className="narrative">{result.narrative}</p>
        </div>
      )}
    </div>
  );
}
