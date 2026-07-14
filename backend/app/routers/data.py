from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from .. import data_service, models
from ..database import get_db

router = APIRouter(prefix="/api/data", tags=["data"])


@router.post("/upload")
async def upload_dataset(file: UploadFile = File(...), db: Session = Depends(get_db),
                          replace_existing: bool = Query(False)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Only CSV uploads are supported. Expected columns: "
                                  "timestamp, route_id, vehicle_count[, avg_speed, congestion_index, weather]")
    content = await file.read()
    try:
        df = data_service.parse_uploaded_csv(content)
        df = data_service.preprocess(df)
    except data_service.InvalidDatasetError as e:
        raise HTTPException(422, str(e))
    n = data_service.save_records(db, df, replace=replace_existing)
    return {"status": "ok", "rows_ingested": n, "routes": sorted(df["route_id"].unique().tolist())}


@router.post("/generate-synthetic")
def generate_synthetic(days: int = Query(30, ge=7, le=180), db: Session = Depends(get_db)):
    """Generates a realistic demo dataset (useful for testing the whole pipeline without a real upload)."""
    df = data_service.generate_synthetic_dataset(days=days)
    df = data_service.preprocess(df)
    n = data_service.save_records(db, df, replace=True)
    return {"status": "ok", "rows_ingested": n, "routes": sorted(df["route_id"].unique().tolist()), "days": days}


@router.get("/routes")
def list_routes(db: Session = Depends(get_db)):
    routes = db.query(models.TrafficRecord.route_id).distinct().all()
    return {"routes": sorted([r[0] for r in routes])}


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    total = db.query(func.count(models.TrafficRecord.id)).scalar()
    routes = db.query(models.TrafficRecord.route_id).distinct().count()
    date_range = db.query(func.min(models.TrafficRecord.timestamp), func.max(models.TrafficRecord.timestamp)).first()
    return {
        "total_records": total,
        "route_count": routes,
        "start_date": date_range[0],
        "end_date": date_range[1],
    }


@router.get("/history")
def history(route_id: str = Query(...), limit: int = Query(500, le=5000), db: Session = Depends(get_db)):
    rows = (
        db.query(models.TrafficRecord)
        .filter(models.TrafficRecord.route_id == route_id)
        .order_by(models.TrafficRecord.timestamp.desc())
        .limit(limit)
        .all()
    )
    rows = list(reversed(rows))
    return [
        {
            "timestamp": r.timestamp, "route_id": r.route_id, "vehicle_count": r.vehicle_count,
            "avg_speed": r.avg_speed, "congestion_index": r.congestion_index, "weather": r.weather,
        }
        for r in rows
    ]
