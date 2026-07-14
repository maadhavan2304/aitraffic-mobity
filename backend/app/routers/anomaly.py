from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from .. import data_service, anomaly, models
from ..database import get_db

router = APIRouter(prefix="/api/anomalies", tags=["anomalies"])


@router.get("")
def get_anomalies(route_id: str = Query(None), db: Session = Depends(get_db)):
    df = data_service.load_dataframe(db, route_id=route_id)
    if df.empty:
        raise HTTPException(404, "No data available.")
    result = anomaly.detect_anomalies(df)
    if result.empty:
        return {"count": 0, "anomalies": []}
    # persist for dashboard history / audit trail
    db.query(models.AnomalyRecord).delete()
    objs = [
        models.AnomalyRecord(
            timestamp=row.timestamp, route_id=row.route_id, vehicle_count=row.vehicle_count,
            method=row.method, score=row.score, severity=row.severity, description=row.description,
        )
        for row in result.itertuples()
    ]
    db.bulk_save_objects(objs)
    db.commit()
    return {
        "count": len(result),
        "anomalies": result.to_dict(orient="records"),
    }
