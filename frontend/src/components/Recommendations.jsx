import React, { useEffect, useState } from "react";
import { getRecommendations } from "../api";

const typeIcon = {
  best_travel_time: "🕒",
  congestion_reduction: "🚦",
  load_balancing: "🔀",
};

export default function Recommendations({ routeId }) {
  const [recs, setRecs] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!routeId) return;
    setLoading(true);
    getRecommendations(routeId)
      .then((res) => setRecs(res.recommendations || []))
      .finally(() => setLoading(false));
  }, [routeId]);

  return (
    <div className="card">
      <div className="card-header">
        <h3>Mobility Optimization Recommendations</h3>
      </div>
      {loading && <p className="muted">Generating recommendations…</p>}
      {!loading && recs.length === 0 && <p className="muted">No recommendations available yet.</p>}
      <ul className="rec-list">
        {recs.map((r, i) => (
          <li key={i}>
            <span className="rec-icon">{typeIcon[r.recommendation_type] || "💡"}</span>
            <div>
              <div>{r.message}</div>
              {r.estimated_benefit && <span className="tag small">{r.estimated_benefit}</span>}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
