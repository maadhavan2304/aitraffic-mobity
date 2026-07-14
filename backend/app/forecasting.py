"""
Forecasting layer.

Strategy: try Prophet first (handles daily+weekly seasonality well with little tuning).
If Prophet isn't installed/importable in the environment, fall back to a
Holt-Winters exponential smoothing model (statsmodels), and if that also fails
(e.g. too little data), fall back to a simple seasonal-naive regression.
This keeps the API resilient regardless of which optional ML deps are present.
"""
import numpy as np
import pandas as pd
from datetime import timedelta

MODEL_PROPHET = "prophet"
MODEL_HOLTWINTERS = "holt_winters"
MODEL_SEASONAL_NAIVE = "seasonal_naive_regression"


def _prep_series(df: pd.DataFrame) -> pd.DataFrame:
    s = df[["timestamp", "vehicle_count"]].dropna().sort_values("timestamp")
    s = s.rename(columns={"timestamp": "ds", "vehicle_count": "y"})
    return s


def forecast_prophet(series: pd.DataFrame, periods: int, freq: str):
    from prophet import Prophet
    m = Prophet(daily_seasonality=True, weekly_seasonality=True, yearly_seasonality=False,
                interval_width=0.85)
    m.fit(series)
    future = m.make_future_dataframe(periods=periods, freq=freq)
    fcst = m.predict(future)
    result = fcst.tail(periods)[["ds", "yhat", "yhat_lower", "yhat_upper"]]
    return result.rename(columns={"ds": "timestamp", "yhat": "predicted_volume",
                                   "yhat_lower": "lower_bound", "yhat_upper": "upper_bound"})


def forecast_holt_winters(series: pd.DataFrame, periods: int, freq: str):
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    y = series.set_index("ds")["y"].asfreq(freq).interpolate()
    seasonal_periods = 24 if freq == "h" else 7
    model = ExponentialSmoothing(
        y, trend="add", seasonal="add", seasonal_periods=seasonal_periods,
        initialization_method="estimated",
    ).fit()
    preds = model.forecast(periods)
    resid_std = float(np.std(model.resid)) if hasattr(model, "resid") else float(y.std() * 0.1)
    last_ts = y.index[-1]
    future_idx = pd.date_range(last_ts + pd.tseries.frequencies.to_offset(freq), periods=periods, freq=freq)
    return pd.DataFrame({
        "timestamp": future_idx,
        "predicted_volume": preds.values,
        "lower_bound": preds.values - 1.28 * resid_std,
        "upper_bound": preds.values + 1.28 * resid_std,
    })


def forecast_seasonal_naive(series: pd.DataFrame, periods: int, freq: str):
    """Fallback for very small datasets: average by hour-of-day (or day-of-week) with
    a linear trend adjustment. Always works, no fitting required."""
    y = series.set_index("ds")["y"]
    last_ts = y.index[-1]
    future_idx = pd.date_range(last_ts + pd.Timedelta(hours=1 if freq == "h" else 24), periods=periods, freq=freq)

    if freq == "h":
        seasonal_avg = y.groupby(y.index.hour).mean()
        preds = [seasonal_avg.get(ts.hour, y.mean()) for ts in future_idx]
    else:
        seasonal_avg = y.groupby(y.index.dayofweek).mean()
        preds = [seasonal_avg.get(ts.dayofweek, y.mean()) for ts in future_idx]

    preds = np.array(preds, dtype=float)
    std = float(y.std()) if len(y) > 1 else preds.mean() * 0.1
    return pd.DataFrame({
        "timestamp": future_idx,
        "predicted_volume": preds,
        "lower_bound": preds - 1.28 * std,
        "upper_bound": preds + 1.28 * std,
    })


def generate_forecast(df: pd.DataFrame, horizon: str = "24h"):
    """horizon: '24h' (hourly, next 24h) or '7d' (daily, next 7 days)."""
    if df.empty:
        raise ValueError("No data available for this route.")

    series = _prep_series(df)
    if horizon == "7d":
        periods, freq = 7, "D"
        daily = series.set_index("ds")["y"].resample("D").sum().reset_index().rename(columns={"ds": "ds", 0: "y"})
        daily.columns = ["ds", "y"]
        series = daily
    else:
        periods, freq = 24, "h"

    model_used = MODEL_PROPHET
    try:
        if len(series) < 48:
            raise RuntimeError("insufficient data for Prophet, using fallback")
        result = forecast_prophet(series, periods, freq)
    except Exception:
        try:
            model_used = MODEL_HOLTWINTERS
            if len(series) < (2 * (24 if freq == "h" else 7)):
                raise RuntimeError("insufficient data for Holt-Winters")
            result = forecast_holt_winters(series, periods, freq)
        except Exception:
            model_used = MODEL_SEASONAL_NAIVE
            result = forecast_seasonal_naive(series, periods, freq)

    result["predicted_volume"] = result["predicted_volume"].clip(lower=0)
    result["lower_bound"] = result["lower_bound"].clip(lower=0)

    peak_hours = _identify_peak_hours(result, freq)
    alerts = _generate_alerts(df, result, freq)

    return result, model_used, peak_hours, alerts


def _identify_peak_hours(result: pd.DataFrame, freq: str):
    threshold = result["predicted_volume"].quantile(0.75)
    peaks = result[result["predicted_volume"] >= threshold]
    if freq == "h":
        return [ts.strftime("%Y-%m-%d %H:00") for ts in peaks["timestamp"]]
    return [ts.strftime("%Y-%m-%d") for ts in peaks["timestamp"]]


def _generate_alerts(history: pd.DataFrame, result: pd.DataFrame, freq: str):
    alerts = []
    recent_avg = history["vehicle_count"].tail(24 * 7 if freq == "h" else 30).mean()
    predicted_avg = result["predicted_volume"].mean()
    if recent_avg and recent_avg > 0:
        pct_change = ((predicted_avg - recent_avg) / recent_avg) * 100
        if pct_change > 15:
            alerts.append(f"Traffic volume expected to increase by {pct_change:.0f}% versus recent average.")
        elif pct_change < -15:
            alerts.append(f"Traffic volume expected to decrease by {abs(pct_change):.0f}% versus recent average.")

    if freq == "h":
        top = result.nlargest(3, "predicted_volume")
        for _, row in top.iterrows():
            alerts.append(
                f"High congestion expected around {row['timestamp'].strftime('%A %H:00')} "
                f"(~{row['predicted_volume']:.0f} vehicles)."
            )
    else:
        top_day = result.loc[result["predicted_volume"].idxmax()]
        alerts.append(
            f"Highest daily volume expected on {top_day['timestamp'].strftime('%A, %b %d')} "
            f"(~{top_day['predicted_volume']:.0f} vehicles)."
        )
    return alerts
