from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import Base, engine
from .routers import data, forecast, anomaly, optimize, simulate

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI Traffic & Mobility Forecasting System",
    description="Modular ML backend for traffic forecasting, anomaly detection, "
                "mobility optimization and scenario simulation.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(data.router)
app.include_router(forecast.router)
app.include_router(anomaly.router)
app.include_router(optimize.router)
app.include_router(simulate.router)


@app.get("/")
def root():
    return {
        "service": "AI Traffic & Mobility Forecasting System",
        "docs": "/docs",
        "endpoints": [
            "/api/data/upload", "/api/data/generate-synthetic", "/api/data/routes",
            "/api/data/summary", "/api/data/history",
            "/api/forecast", "/api/anomalies", "/api/optimize/recommendations",
            "/api/simulate", "/api/simulate/scenarios",
        ],
    }


@app.get("/health")
def health():
    return {"status": "healthy"}
