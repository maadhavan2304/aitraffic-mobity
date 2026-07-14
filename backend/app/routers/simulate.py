from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import data_service, simulation
from ..database import get_db
from ..schemas import SimulationRequest, SimulationResponse

router = APIRouter(prefix="/api/simulate", tags=["simulate"])


@router.post("", response_model=SimulationResponse)
def run_simulation(req: SimulationRequest, db: Session = Depends(get_db)):
    df = data_service.load_dataframe(db, route_id=req.route_id)
    if df.empty:
        raise HTTPException(404, f"No data found for route '{req.route_id}'.")
    try:
        result = simulation.simulate_scenario(
            df, route_id=req.route_id, scenario=req.scenario,
            intensity=req.intensity, duration_hours=req.duration_hours,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return SimulationResponse(**result)


@router.get("/scenarios")
def list_scenarios():
    from ..simulation import SCENARIO_FACTORS
    return {"scenarios": list(SCENARIO_FACTORS.keys())}
