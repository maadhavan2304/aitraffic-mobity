"""
Scenario simulation layer.
Applies empirically-motivated multipliers to baseline historical congestion to
estimate impact of hypothetical events. Not a full traffic-flow micro-simulation
(that would need SUMO/road-network graph data) — this is a fast, explainable
what-if estimator suitable for dashboard-level decision support.
"""
import pandas as pd

SCENARIO_FACTORS = {
    "road_closure": {"congestion_mult": 1.9, "speed_mult": 0.45, "label": "a road closure"},
    "heavy_rain": {"congestion_mult": 1.35, "speed_mult": 0.75, "label": "heavy rain"},
    "event_surge": {"congestion_mult": 1.6, "speed_mult": 0.6, "label": "an event-driven surge"},
    "vehicle_load_increase": {"congestion_mult": 1.25, "speed_mult": 0.85, "label": "increased vehicle load"},
}


def simulate_scenario(df: pd.DataFrame, route_id: str, scenario: str, intensity: float = 1.0,
                       duration_hours: int = 4):
    if scenario not in SCENARIO_FACTORS:
        raise ValueError(f"Unknown scenario '{scenario}'. Valid options: {list(SCENARIO_FACTORS)}")

    g = df[df["route_id"] == route_id]
    if g.empty:
        raise ValueError(f"No historical data for route '{route_id}'.")

    baseline_congestion = g["congestion_index"].mean() if g["congestion_index"].notna().any() else \
        float((g["vehicle_count"] / g["vehicle_count"].max()).mean())
    baseline_speed = g["avg_speed"].mean() if g["avg_speed"].notna().any() else 40.0

    factors = SCENARIO_FACTORS[scenario]
    intensity = max(0.1, min(intensity, 5.0))

    congestion_mult = 1 + (factors["congestion_mult"] - 1) * intensity
    speed_mult = max(0.05, 1 - (1 - factors["speed_mult"]) * intensity)

    projected_congestion = min(baseline_congestion * congestion_mult, 1.0)
    projected_speed = max(baseline_speed * speed_mult, 2.0)

    congestion_delta_pct = ((projected_congestion - baseline_congestion) / max(baseline_congestion, 1e-6)) * 100
    travel_time_change_pct = ((baseline_speed - projected_speed) / max(baseline_speed, 1e-6)) * 100

    base_trip_minutes = 20  # assumed reference trip length for delay estimate
    estimated_delay = base_trip_minutes * (travel_time_change_pct / 100)

    narrative = (
        f"Simulating {factors['label']} on {route_id} for {duration_hours}h at intensity {intensity:.1f}x: "
        f"congestion index projected to rise from {baseline_congestion:.2f} to {projected_congestion:.2f} "
        f"({congestion_delta_pct:+.0f}%), with an estimated {estimated_delay:.0f} extra minutes on a "
        f"reference {base_trip_minutes}-minute trip."
    )

    return {
        "route_id": route_id,
        "scenario": scenario,
        "baseline_congestion": round(float(baseline_congestion), 3),
        "projected_congestion": round(float(projected_congestion), 3),
        "congestion_delta_pct": round(float(congestion_delta_pct), 1),
        "estimated_delay_minutes": round(float(estimated_delay), 1),
        "travel_time_change_pct": round(float(travel_time_change_pct), 1),
        "narrative": narrative,
    }
