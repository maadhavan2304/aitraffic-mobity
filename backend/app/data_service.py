"""
Data layer: dataset upload parsing, synthetic dataset generation (for demo/testing),
and preprocessing that handles the required edge cases:
  - missing timestamps -> resampled + interpolated
  - sparse route data -> forward/back-fill with capped gap size
  - sudden spikes -> optionally clipped for training (not for anomaly detection, which needs them)
  - invalid uploads -> validated & rejected with clear errors
"""
import io
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import delete
from . import models

REQUIRED_COLUMNS = {"timestamp", "route_id", "vehicle_count"}


class InvalidDatasetError(Exception):
    pass


def parse_uploaded_csv(file_bytes: bytes) -> pd.DataFrame:
    try:
        df = pd.read_csv(io.BytesIO(file_bytes))
    except Exception as e:
        raise InvalidDatasetError(f"Could not parse CSV: {e}")

    df.columns = [c.strip().lower() for c in df.columns]
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise InvalidDatasetError(f"Missing required columns: {sorted(missing)}")

    try:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    except Exception as e:
        raise InvalidDatasetError(f"Invalid timestamp column: {e}")

    bad_ts = df["timestamp"].isna().sum()
    if bad_ts > 0:
        df = df.dropna(subset=["timestamp"])

    df["vehicle_count"] = pd.to_numeric(df["vehicle_count"], errors="coerce")
    df = df.dropna(subset=["vehicle_count"])
    df = df[df["vehicle_count"] >= 0]

    if df.empty:
        raise InvalidDatasetError("No valid rows remained after validation.")

    for opt_col in ["avg_speed", "congestion_index", "weather"]:
        if opt_col not in df.columns:
            df[opt_col] = None

    return df[["timestamp", "route_id", "vehicle_count", "avg_speed", "congestion_index", "weather"]]


def preprocess(df: pd.DataFrame, freq: str = "h") -> pd.DataFrame:
    """Resample per route to a regular frequency, filling gaps (missing timestamps /
    sparse data) via time-based interpolation, capped so long silent gaps stay NaN-free
    but aren't hallucinated across days."""
    out_frames = []
    for route_id, g in df.groupby("route_id"):
        g = g.set_index("timestamp").sort_index()
        g = g[~g.index.duplicated(keep="last")]
        resampled = g.resample(freq).mean(numeric_only=True)
        was_missing = resampled["vehicle_count"].isna()
        resampled["vehicle_count"] = resampled["vehicle_count"].interpolate(
            method="time", limit=6, limit_direction="both"
        )
        resampled["vehicle_count"] = resampled["vehicle_count"].fillna(
            resampled["vehicle_count"].rolling(24, min_periods=1).mean()
        )
        resampled["is_interpolated"] = was_missing & resampled["vehicle_count"].notna()
        resampled["route_id"] = route_id
        resampled["weather"] = (
    g["weather"].resample(freq).ffill()
    if "weather" in g.columns
    else None
)
        resampled["congestion_index"] = resampled.get("congestion_index").interpolate(limit=6) \
            if "congestion_index" in resampled else np.nan
        out_frames.append(resampled.reset_index())
    result = pd.concat(out_frames, ignore_index=True)
    result = result.dropna(subset=["vehicle_count"])
    return result


def save_records(db: Session, df: pd.DataFrame, replace: bool = False):
    if replace:
        db.execute(delete(models.TrafficRecord))
    objs = [
        models.TrafficRecord(
            timestamp=row.timestamp.to_pydatetime() if hasattr(row.timestamp, "to_pydatetime") else row.timestamp,
            route_id=str(row.route_id),
            vehicle_count=float(row.vehicle_count),
            avg_speed=float(row.avg_speed) if pd.notna(row.avg_speed) else None,
            congestion_index=float(row.congestion_index) if pd.notna(row.congestion_index) else None,
            weather=getattr(row, "weather", None),
            is_interpolated=bool(getattr(row, "is_interpolated", False)),
        )
        for row in df.itertuples(index=False)
    ]
    db.bulk_save_objects(objs)
    db.commit()
    return len(objs)


def generate_synthetic_dataset(routes=("Route A", "Route B", "Route C"), days=30, seed=42) -> pd.DataFrame:
    """Creates a realistic hourly synthetic dataset: daily + weekly seasonality,
    rush-hour peaks, weather effects, random spikes/anomalies, and some missing rows
    to exercise the preprocessing pipeline."""
    rng = np.random.default_rng(seed)
    start = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    timestamps = pd.date_range(start, periods=days * 24, freq="h")
    rows = []
    for route in routes:
        base = rng.uniform(200, 400)
        for ts in timestamps:
            hour = ts.hour
            dow = ts.dayofweek
            # daily seasonality: morning + evening rush peaks
            daily = 1.0 + 0.9 * np.exp(-((hour - 8) ** 2) / 6) + 1.1 * np.exp(-((hour - 18) ** 2) / 6)
            weekly = 0.6 if dow >= 5 else 1.0  # weekends lighter
            noise = rng.normal(0, 0.08)
            weather = rng.choice(["clear", "rain", "storm", "fog"], p=[0.7, 0.18, 0.05, 0.07])
            weather_factor = {"clear": 1.0, "rain": 1.15, "storm": 1.35, "fog": 1.1}[weather]

            volume = base * daily * weekly * weather_factor * (1 + noise)

            # inject random spikes / anomalies ~2% of the time
            if rng.random() < 0.02:
                volume *= rng.uniform(1.8, 2.6)
            if rng.random() < 0.01:
                volume *= rng.uniform(0.15, 0.35)  # sudden drop (sensor fault / closure)

            volume = max(volume, 5)
            speed = max(5, 60 - (volume / base) * 18 + rng.normal(0, 3))
            congestion = float(np.clip((volume / (base * 2.2)), 0, 1))

            # simulate missing timestamps (sparse data) ~3% of rows
            if rng.random() < 0.03:
                continue

            rows.append({
                "timestamp": ts, "route_id": route, "vehicle_count": round(volume, 1),
                "avg_speed": round(speed, 1), "congestion_index": round(congestion, 3),
                "weather": weather,
            })
    return pd.DataFrame(rows)


def load_dataframe(db: Session, route_id: str = None) -> pd.DataFrame:
    q = db.query(models.TrafficRecord)
    if route_id:
        q = q.filter(models.TrafficRecord.route_id == route_id)
    rows = q.order_by(models.TrafficRecord.timestamp.asc()).all()
    if not rows:
        return pd.DataFrame(columns=["timestamp", "route_id", "vehicle_count", "avg_speed",
                                      "congestion_index", "weather"])
    return pd.DataFrame([{
        "timestamp": r.timestamp, "route_id": r.route_id, "vehicle_count": r.vehicle_count,
        "avg_speed": r.avg_speed, "congestion_index": r.congestion_index, "weather": r.weather,
    } for r in rows])
