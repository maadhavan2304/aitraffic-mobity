# AI-Based Traffic & Mobility Forecasting System

A full-stack platform that forecasts traffic volume, detects anomalies, generates
mobility optimization recommendations, and simulates what-if scenarios (road closures,
weather, events) using historical traffic data.

**Stack:** FastAPI (Python 3.14) · React + Vite + Recharts · SQLite (swappable to PostgreSQL) ·
Statsmodels / Scikit-learn (+ optional Prophet)

---

## 1. System Architecture

```
┌─────────────────────┐       REST/JSON        ┌──────────────────────────────┐
│   React Frontend     │ ──────────────────────▶│        FastAPI Backend        │
│ (Analytics Dashboard)│◀────────────────────── │                                │
└─────────────────────┘                         │  routers/                     │
                                                 │   ├─ data.py      (ingestion) │
                                                 │   ├─ forecast.py  (forecasts) │
                                                 │   ├─ anomaly.py   (detection) │
                                                 │   ├─ optimize.py  (recs)      │
                                                 │   └─ simulate.py  (what-if)   │
                                                 │                                │
                                                 │  services/ (business logic)   │
                                                 │   ├─ data_service.py          │
                                                 │   ├─ forecasting.py           │
                                                 │   ├─ anomaly.py               │
                                                 │   ├─ optimization.py          │
                                                 │   └─ simulation.py            │
                                                 │                                │
                                                 │  models.py / database.py      │
                                                 │        (SQLAlchemy ORM)       │
                                                 └───────────────┬────────────────┘
                                                                 │
                                                          ┌──────▼──────┐
                                                          │  SQLite /   │
                                                          │  PostgreSQL │
                                                          └─────────────┘
```

Each ML capability (forecasting, anomaly detection, optimization, simulation) is an
**independent, stateless module** that takes a pandas DataFrame in and returns
structured results — they don't depend on each other or on FastAPI, so they're
directly unit-testable and reusable (e.g. from a notebook or a batch job).

### Non-blocking execution
Per-route forecasting/anomaly runs are fast (sub-2s on typical demo data), so they're
served synchronously today. The architecture is intentionally job-friendly: `services/`
functions take a DataFrame and return a DataFrame/dict with no FastAPI or request-scoped
state, so wrapping `generate_forecast()` or `detect_anomalies()` in a Celery task /
`BackgroundTasks` call for large multi-route batch training is a drop-in change, not a
rewrite.

---

## 2. Dataset

### Expected schema (CSV upload)
| column             | required | description                                  |
|---------------------|----------|-----------------------------------------------|
| `timestamp`          | ✅       | ISO-8601 or parseable datetime                |
| `route_id`            | ✅       | Route/location identifier (e.g. "Route A")    |
| `vehicle_count`        | ✅       | Vehicle volume for that timestamp/route       |
| `avg_speed`             | optional | Average speed (km/h)                         |
| `congestion_index`       | optional | 0 (free flow) – 1 (gridlock)                |
| `weather`                 | optional | clear / rain / storm / fog                  |

### Synthetic demo dataset
`POST /api/data/generate-synthetic?days=30` generates a realistic hourly dataset per
route with:
- Daily seasonality (morning + evening rush-hour peaks)
- Weekly seasonality (lighter weekend traffic)
- Weather-driven volume multipliers
- Randomly injected spikes and drops (to exercise anomaly detection)
- Randomly dropped rows (to exercise missing-timestamp handling)

### Edge case handling (in `data_service.py`)
- **Missing timestamps** — data is resampled to a regular hourly grid per route; gaps
  are filled via time-based interpolation (capped at 6 consecutive hours) then a
  rolling-mean fallback for longer gaps.
- **Sparse route data** — same resample/interpolate pipeline; routes with too little
  data automatically fall back to simpler models (see Forecasting Methodology).
- **Sudden spikes** — preserved (not clipped) for anomaly detection, since spikes are
  the signal of interest there; forecasting models handle them via their own outlier
  robustness (Prophet) or seasonal averaging (fallback models).
- **Invalid uploads** — CSVs missing required columns, unparseable timestamps, or with
  no valid rows after cleaning are rejected with a `422` and a specific error message.

---

## 3. Forecasting Methodology

`forecasting.py` implements a **cascading fallback strategy** so the API always returns
a forecast regardless of data volume or environment:

1. **Prophet** (primary) — used when ≥48 data points are available. Handles daily +
   weekly seasonality automatically, returns 85% confidence intervals.
2. **Holt-Winters Exponential Smoothing** (statsmodels) — used if Prophet fails to
   import/fit (e.g. not installed, or too little data for Prophet's changepoint
   detection). Additive trend + seasonal component (24h or 7-day cycle).
3. **Seasonal-naive regression** (pure pandas/numpy) — last-resort fallback for very
   small datasets. Averages historical volume by hour-of-day (for 24h forecasts) or
   day-of-week (for 7-day forecasts) with a Gaussian-based confidence band from
   historical std deviation. Always succeeds.

Supported horizons: **next 24 hours** (hourly resolution) and **next 7 days** (daily
resolution, aggregated by summing hourly volume per day).

Peak-hour forecasting: after generating the forecast curve, hours/days in the top
quartile of predicted volume are flagged as `peak_hours`. Alerts are generated by
comparing predicted average volume to the trailing 7-day historical average and
surfacing the top-3 highest-predicted windows, e.g.:
> "High congestion expected around Monday 08:00 (~742 vehicles)."

---

## 4. Anomaly Detection Approach

`anomaly.py` combines two complementary methods and merges/deduplicates results:

- **Z-score thresholding** — per-route statistical outlier detection on raw volume
  (|z| ≥ 3 = flagged, ≥4.5 = high severity). Fast, interpretable, catches univariate
  spikes/drops.
- **Isolation Forest** (scikit-learn) — multivariate/contextual anomaly detection using
  `vehicle_count`, `avg_speed`, `hour`, and `day-of-week` jointly. Catches anomalies
  that aren't extreme in volume alone but are unusual *for that time of day* (e.g.
  normal volume at 3 AM).

Each detected anomaly is tagged with severity (`low`/`medium`/`high`), the detecting
method, and a human-readable description, then persisted to the `anomaly_records` table
for dashboard history.

---

## 5. Mobility Optimization Logic

`optimization.py` is a deliberately **rule-based, explainable** layer (not a black-box
model) since these are operational recommendations a traffic planner needs to trust:

- **Best travel windows** — ranks hours of day by historical average volume; recommends
  the lowest-traffic hours with an estimated % congestion reduction vs. peak hour.
- **Congestion reduction tips** — flags routes with sustained high congestion index and
  suggests demand-flattening measures (staggered hours, carpool incentives); also
  detects large day/night volume gaps and recommends off-peak travel with an estimated
  time-savings percentage.
- **Route load balancing** — compares average load across all routes at the same hour;
  when one route carries >30% more load than another, recommends redirecting traffic to
  the less-loaded route.

---

## 6. Scenario Simulation

`simulation.py` applies scenario-specific multipliers to a route's historical baseline
congestion/speed to estimate impact, scaled by a user-supplied intensity (0.1x–5x) and
duration. Supported scenarios: `road_closure`, `heavy_rain`, `event_surge`,
`vehicle_load_increase`. Output includes projected congestion index, % delta, and an
estimated delay (minutes) on a reference trip. This is a fast, explainable estimator —
not a full road-network micro-simulation (which would require SUMO + graph topology).

---

## 7. API Documentation

Interactive OpenAPI docs are auto-generated at **`/docs`** once the backend is running.

| Method | Endpoint                         | Description                              |
|--------|-----------------------------------|--------------------------------------------|
| POST   | `/api/data/upload`                 | Upload a CSV dataset                       |
| POST   | `/api/data/generate-synthetic`       | Generate a synthetic demo dataset         |
| GET    | `/api/data/routes`                    | List available route IDs                |
| GET    | `/api/data/summary`                    | Dataset summary stats                   |
| GET    | `/api/data/history?route_id=`           | Historical records for a route         |
| GET    | `/api/forecast?route_id=&horizon=`       | Forecast (24h or 7d) for a route      |
| GET    | `/api/anomalies?route_id=`                | Detected anomalies for a route       |
| GET    | `/api/optimize/recommendations?route_id=`  | Mobility recommendations            |
| POST   | `/api/simulate`                             | Run a scenario simulation           |
| GET    | `/api/simulate/scenarios`                    | List available simulation scenarios|

---

## 8. Running Locally

**Supported / tested Python version: 3.14** (also works on 3.10+).

### Backend
```bash
cd backend
python3.14 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

`requirements.txt` intentionally does **not** include Prophet, because Prophet's
`cmdstanpy` dependency compiles a Stan binary at install/first-use time — a build step
that can be flaky on very new Python releases before upstream wheels catch up. The app
is fully functional without it: `forecasting.py` detects Prophet's absence and falls
back to Holt-Winters (statsmodels) or, if that's unavailable too, a seasonal-naive
regression — verified end-to-end with no errors.

If you specifically want Prophet as the primary model:
```bash
pip install -r requirements-optional.txt
```
(requires a C/C++ toolchain; on Debian/Ubuntu: `apt-get install build-essential`). If
it fails, just skip it — nothing else in the app depends on it.

Verify the install worked:
```bash
python -c "import fastapi, sqlalchemy, pandas, numpy, sklearn, statsmodels; print('OK')"
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Visit `http://localhost:5173`. The Vite dev server proxies `/api` to
`http://localhost:8000`.

### Docker (full stack)
```bash
docker compose up --build
```
Frontend: `http://localhost:3000` · Backend docs: `http://localhost:8000/docs`

### Quick start (no CSV needed)
Click **"Generate Demo Data"** in the dashboard header, or:
```bash
curl -X POST "http://localhost:8000/api/data/generate-synthetic?days=30"
```

---

## 9. Project Structure

```
traffic-ai/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app + router registration
│   │   ├── database.py        # SQLAlchemy engine/session
│   │   ├── models.py          # ORM models
│   │   ├── schemas.py         # Pydantic request/response models
│   │   ├── data_service.py    # Upload parsing, synthetic gen, preprocessing
│   │   ├── forecasting.py     # Prophet / Holt-Winters / seasonal-naive
│   │   ├── anomaly.py         # Z-score + Isolation Forest
│   │   ├── optimization.py    # Rule-based mobility recommendations
│   │   ├── simulation.py      # Scenario what-if engine
│   │   └── routers/           # API route handlers (one per feature)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx            # Dashboard shell, route selector, data upload
│   │   ├── api.js             # Axios API client
│   │   ├── components/
│   │   │   ├── ForecastChart.jsx
│   │   │   ├── AnomalyChart.jsx
│   │   │   ├── Recommendations.jsx
│   │   │   ├── Simulation.jsx
│   │   │   └── RouteComparison.jsx
│   │   └── styles.css
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

## 10. Known Limitations / Next Steps
- Simulation is a heuristic multiplier model, not a network-graph traffic simulator.
- No authentication layer (add JWT/OAuth before any multi-tenant deployment).
- Model training is synchronous; for large-scale multi-route retraining, wrap
  `forecasting.generate_forecast` in a background task queue (Celery/RQ) as noted above.
- No live/streaming data ingestion yet (bonus feature) — current pipeline is
  batch-upload or synthetic-generation based.
