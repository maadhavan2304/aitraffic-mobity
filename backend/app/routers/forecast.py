from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from .. import data_service, forecasting
from ..database import get_db
from ..schemas import ForecastResponse, ForecastPoint

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


@router.get("", response_model=ForecastResponse)
def get_forecast(route_id: str = Query(...), horizon: str = Query("24h", pattern="^(24h|7d)$"),
                  db: Session = Depends(get_db)):
    """Non-blocking-friendly: forecast fitting for a single route on demand data is fast
    (<2s typical). For heavier multi-route batch training, POST /api/forecast/train-all
    is intended to be run as a background job / Celery task in production."""
    df = data_service.load_dataframe(db, route_id=route_id)
    if df.empty:
        raise HTTPException(404, f"No data found for route '{route_id}'. Upload data or generate synthetic data first.")
    try:
        result, model_used, peak_hours, alerts = forecasting.generate_forecast(df, horizon=horizon)
    except Exception as e:
        raise HTTPException(500, f"Forecasting failed: {e}")

    points = [
        ForecastPoint(timestamp=row.timestamp, predicted_volume=round(row.predicted_volume, 1),
                       lower_bound=round(row.lower_bound, 1) if row.lower_bound is not None else None,
                       upper_bound=round(row.upper_bound, 1) if row.upper_bound is not None else None)
        for row in result.itertuples()
    ]
    return ForecastResponse(route_id=route_id, horizon=horizon, model_used=model_used,
                             points=points, peak_hours=peak_hours, alerts=alerts)
