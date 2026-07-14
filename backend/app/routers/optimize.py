from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from .. import data_service, optimization
from ..database import get_db

router = APIRouter(prefix="/api/optimize", tags=["optimize"])


@router.get("/recommendations")
def get_recommendations(route_id: str = Query(None), db: Session = Depends(get_db)):
    df = data_service.load_dataframe(db, route_id=route_id)
    if df.empty:
        raise HTTPException(404, "No data available.")
    recs = optimization.generate_recommendations(df, route_id=route_id)
    return {"count": len(recs), "recommendations": recs}
