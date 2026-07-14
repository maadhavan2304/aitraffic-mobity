import React, { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { getHistory } from "../api";

export default function RouteComparison({ routes }) {
  const [data, setData] = useState([]);

  useEffect(() => {
    if (!routes?.length) return;
    Promise.all(routes.map((r) => getHistory(r, 168))).then((results) => {
      const merged = results.map((hist, i) => {
        const avgVol = hist.reduce((s, h) => s + h.vehicle_count, 0) / (hist.length || 1);
        const avgSpeed = hist.filter((h) => h.avg_speed).reduce((s, h) => s + h.avg_speed, 0) /
          (hist.filter((h) => h.avg_speed).length || 1);
        const avgCong = hist.filter((h) => h.congestion_index).reduce((s, h) => s + h.congestion_index, 0) /
          (hist.filter((h) => h.congestion_index).length || 1);
        return {
          route: routes[i],
          avgVolume: Math.round(avgVol),
          avgSpeed: Math.round(avgSpeed || 0),
          congestion: Math.round((avgCong || 0) * 100),
        };
      });
      setData(merged);
    });
  }, [routes]);

  return (
    <div className="card">
      <div className="card-header">
        <h3>Route Comparison (last 7 days)</h3>
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2b38" />
          <XAxis dataKey="route" tick={{ fill: "#8fa3b3", fontSize: 12 }} />
          <YAxis tick={{ fill: "#8fa3b3", fontSize: 11 }} />
          <Tooltip contentStyle={{ background: "#111823", border: "1px solid #223142", color: "#e6edf3" }} />
          <Legend />
          <Bar dataKey="avgVolume" fill="#5b8cff" name="Avg Volume" radius={[4, 4, 0, 0]} />
          <Bar dataKey="avgSpeed" fill="#63d2a5" name="Avg Speed (km/h)" radius={[4, 4, 0, 0]} />
          <Bar dataKey="congestion" fill="#ffb84d" name="Congestion Index (%)" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
