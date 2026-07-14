"""
Mobility optimization engine.
Rule-based reasoning layer on top of forecasts + historical stats: identifies
low-traffic travel windows, compares routes for load-balancing suggestions,
and estimates time savings. Deliberately transparent/explainable (no black-box
model) since these are operational recommendations, not predictions.
"""
import pandas as pd
import numpy as np


def best_travel_windows(df: pd.DataFrame, route_id: str, top_n: int = 3):
    g = df[df["route_id"] == route_id].copy()
    if g.empty:
        return []
    g["hour"] = pd.to_datetime(g["timestamp"]).dt.hour
    hourly = g.groupby("hour")["vehicle_count"].mean().sort_values()
    peak_avg = g.groupby("hour")["vehicle_count"].mean().max()

    recs = []
    for hour, vol in hourly.head(top_n).items():
        pct_reduction = ((peak_avg - vol) / peak_avg) * 100 if peak_avg > 0 else 0
        recs.append({
            "route_id": route_id,
            "recommendation_type": "best_travel_time",
            "message": f"Travel around {hour:02d}:00 on {route_id} to reduce exposure to "
                       f"congestion by ~{pct_reduction:.0f}% compared to peak hour.",
            "estimated_benefit": f"~{pct_reduction:.0f}% less congestion",
        })
    return recs


def route_load_balancing(df: pd.DataFrame):
    """Compares average load across all routes at overlapping time windows and
    suggests redirecting traffic from the busiest to the least busy route."""
    if df.empty or df["route_id"].nunique() < 2:
        return []
    g = df.copy()
    g["hour"] = pd.to_datetime(g["timestamp"]).dt.hour
    pivot = g.groupby(["hour", "route_id"])["vehicle_count"].mean().unstack()
    recs = []
    for hour, row in pivot.iterrows():
        row = row.dropna()
        if len(row) < 2:
            continue
        busiest = row.idxmax()
        quietest = row.idxmin()
        if row[busiest] <= 0:
            continue
        diff_pct = ((row[busiest] - row[quietest]) / row[busiest]) * 100
        if diff_pct > 30:
            recs.append({
                "route_id": busiest,
                "recommendation_type": "load_balancing",
                "message": f"At {hour:02d}:00, redirect traffic from {busiest} to {quietest} "
                           f"during peak hours — {quietest} carries {diff_pct:.0f}% less load.",
                "estimated_benefit": f"Balances load by ~{diff_pct:.0f}%",
            })
    # dedupe & cap
    seen = set()
    unique = []
    for r in recs:
        key = (r["route_id"], r["message"][:30])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique[:5]


def congestion_reduction_tips(df: pd.DataFrame, route_id: str):
    g = df[df["route_id"] == route_id]
    if g.empty:
        return []
    avg_congestion = g["congestion_index"].mean() if "congestion_index" in g and g["congestion_index"].notna().any() else None
    tips = []
    if avg_congestion is not None and avg_congestion > 0.6:
        tips.append({
            "route_id": route_id,
            "recommendation_type": "congestion_reduction",
            "message": f"{route_id} shows sustained high congestion (avg index "
                       f"{avg_congestion:.2f}). Consider staggered work-hours or carpool "
                       f"incentives to flatten peak demand.",
            "estimated_benefit": "Reduces peak load",
        })
    late_night = g[pd.to_datetime(g["timestamp"]).dt.hour.isin([22, 23, 0, 1])]
    if not late_night.empty:
        night_avg = late_night["vehicle_count"].mean()
        day_avg = g["vehicle_count"].mean()
        if day_avg > 0 and night_avg < day_avg * 0.4:
            savings = (1 - night_avg / day_avg) * 100
            tips.append({
                "route_id": route_id,
                "recommendation_type": "best_travel_time",
                "message": f"Travel after 10 PM on {route_id} to reduce travel time by "
                           f"~{savings:.0f}%.",
                "estimated_benefit": f"~{savings:.0f}% faster",
            })
    return tips


def generate_recommendations(df: pd.DataFrame, route_id: str = None):
    routes = [route_id] if route_id else sorted(df["route_id"].unique())
    recs = []
    for r in routes:
        recs.extend(best_travel_windows(df, r))
        recs.extend(congestion_reduction_tips(df, r))
    recs.extend(route_load_balancing(df))
    return recs
