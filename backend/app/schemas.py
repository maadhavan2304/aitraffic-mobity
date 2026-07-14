from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class TrafficRecordIn(BaseModel):
    timestamp: datetime
    route_id: str
    vehicle_count: float
    avg_speed: Optional[float] = None
    congestion_index: Optional[float] = None
    weather: Optional[str] = None


class ForecastPoint(BaseModel):
    timestamp: datetime
    predicted_volume: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None


class ForecastResponse(BaseModel):
    route_id: str
    horizon: str
    model_used: str
    points: List[ForecastPoint]
    peak_hours: List[str]
    alerts: List[str]


class AnomalyPoint(BaseModel):
    timestamp: datetime
    route_id: str
    vehicle_count: float
    method: str
    score: float
    severity: str
    description: str


class RecommendationOut(BaseModel):
    route_id: str
    recommendation_type: str
    message: str
    estimated_benefit: Optional[str] = None


class SimulationRequest(BaseModel):
    route_id: str
    scenario: str  # road_closure | heavy_rain | event_surge | vehicle_load_increase
    intensity: float = 1.0  # multiplier 0.1 - 5.0
    duration_hours: int = 4


class SimulationResponse(BaseModel):
    route_id: str
    scenario: str
    baseline_congestion: float
    projected_congestion: float
    congestion_delta_pct: float
    estimated_delay_minutes: float
    travel_time_change_pct: float
    narrative: str
