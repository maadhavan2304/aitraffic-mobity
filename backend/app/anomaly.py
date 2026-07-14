"""
Anomaly detection layer.
Combines statistical z-score thresholding (fast, interpretable, good for spikes/dips)
with Isolation Forest (catches multivariate/contextual anomalies using volume + speed +
hour-of-day jointly). Results from both methods are merged and de-duplicated.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest


def zscore_anomalies(df: pd.DataFrame, threshold: float = 3.0) -> pd.DataFrame:
    out = []
    for route_id, g in df.groupby("route_id"):
        g = g.sort_values("timestamp").copy()
        mean, std = g["vehicle_count"].mean(), g["vehicle_count"].std()
        if std == 0 or np.isnan(std):
            continue
        g["zscore"] = (g["vehicle_count"] - mean) / std
        flagged = g[g["zscore"].abs() >= threshold]
        for _, row in flagged.iterrows():
            direction = "spike" if row["zscore"] > 0 else "drop"
            severity = "high" if abs(row["zscore"]) >= 4.5 else "medium"
            out.append({
                "timestamp": row["timestamp"], "route_id": route_id,
                "vehicle_count": row["vehicle_count"], "method": "zscore",
                "score": round(float(row["zscore"]), 2), "severity": severity,
                "description": f"Sudden traffic {direction} on {route_id}: "
                                f"{row['vehicle_count']:.0f} vehicles (z={row['zscore']:.2f})",
            })
    return pd.DataFrame(out)


def isolation_forest_anomalies(df: pd.DataFrame, contamination: float = 0.03) -> pd.DataFrame:
    out = []
    for route_id, g in df.groupby("route_id"):
        g = g.sort_values("timestamp").copy()
        if len(g) < 20:
            continue
        g["hour"] = pd.to_datetime(g["timestamp"]).dt.hour
        g["dow"] = pd.to_datetime(g["timestamp"]).dt.dayofweek
        features = g[["vehicle_count", "hour", "dow"]].copy()
        features["avg_speed"] = g["avg_speed"].fillna(g["avg_speed"].mean() if g["avg_speed"].notna().any() else 40)

        model = IsolationForest(contamination=contamination, random_state=42, n_estimators=150)
        preds = model.fit_predict(features)
        scores = model.decision_function(features)
        g["if_pred"] = preds
        g["if_score"] = scores
        flagged = g[g["if_pred"] == -1]
        for _, row in flagged.iterrows():
            severity = "high" if row["if_score"] < -0.15 else "medium"
            out.append({
                "timestamp": row["timestamp"], "route_id": route_id,
                "vehicle_count": row["vehicle_count"], "method": "isolation_forest",
                "score": round(float(row["if_score"]), 3), "severity": severity,
                "description": f"Unusual traffic pattern detected on {route_id} "
                                f"(volume/speed/time combination deviates from norm).",
            })
    return pd.DataFrame(out)


def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    z = zscore_anomalies(df)
    iso = isolation_forest_anomalies(df)
    combined = pd.concat([z, iso], ignore_index=True) if not iso.empty else z
    if combined.empty:
        return combined
    combined = combined.sort_values("timestamp").drop_duplicates(
        subset=["timestamp", "route_id", "method"]
    )
    return combined
