from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from .database import Base


class TrafficRecord(Base):
    """Raw / uploaded traffic observations. One row = one route at one timestamp."""
    __tablename__ = "traffic_records"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, index=True, nullable=False)
    route_id = Column(String, index=True, nullable=False)
    vehicle_count = Column(Float, nullable=False)
    avg_speed = Column(Float, nullable=True)
    congestion_index = Column(Float, nullable=True)  # 0 (free flow) - 1 (gridlock)
    weather = Column(String, nullable=True)           # clear/rain/storm/fog
    is_interpolated = Column(Boolean, default=False)  # filled during preprocessing


class AnomalyRecord(Base):
    """Persisted anomaly detections so the dashboard doesn't need to recompute every load."""
    __tablename__ = "anomaly_records"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, index=True, nullable=False)
    route_id = Column(String, index=True, nullable=False)
    vehicle_count = Column(Float)
    method = Column(String)          # zscore / isolation_forest
    score = Column(Float)
    severity = Column(String)        # low/medium/high
    description = Column(String)
