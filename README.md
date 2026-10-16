# SafeGuard — Safety Score & Data Processing Engine (by Ashutosh)

Welcome to **SafeGuard**, a smart contextual safety navigation system built for hackathons!

This repository contains **Ashutosh's module**: the **Safety Engine**. It ingests raw environmental, historical, and community safety data, validates and normalizes it, processes route coordinates against spatial data buffers, and calculates a transparent, explainable **Safety Score between 0 and 100**.

> ⚠️ **Important Disclaimer**: SafeGuard does **not** predict crime. The Safety Score represents a transparent, contextual safety signal derived directly from identifiable data sources (lighting quality, historical crime counts, emergency service proximity, infrastructure conditions, and community reports).

---

## 1. Ashutosh's Responsibilities

As **Ashutosh**, this module is responsible for:
- **Data Validation & Cleaning**: Ensuring raw dataset schemas are intact, handling missing values, and dropping duplicate entries.
- **Data Normalization**: Scaling disparate metrics (e.g., crime counts, rating scales, distance measurements) to a uniform `0–100` scale.
- **Route Data Processing**: Buffer-matching geographical route coordinates against nearby safety data points.
- **Individual Factor Scoring**: Computing 0–100 factor scores for Lighting, Crime, Emergency Access, Infrastructure, and Community Reports.
- **Weighted Aggregation**: Calculating an explainable weighted final score between 0 and 100.
- **Integration Interfaces**: Providing clean interfaces for **Anushka's** Routing Engine and **Abhinav's** Community Reporting System.
- **Security & Report Integrity**: Enforcing server-side report ID generation, preventing report overwrites, protecting admin endpoints with constant-time key checks.

---

## 2. Architecture & Data Processing Pipeline

```text
Raw Safety Data (CSV / JSON) & Route Coordinates (JSON)
                      │
                      ▼
              [ Data Validation ]
                      │
                      ▼
              [ Data Cleaning ]
                      │
                      ▼
            [ Spatial Buffer Filter ]
                      │
                      ▼
         [ Individual Factor Scorers ]
  ┌──────────┬───────────┼──────────────┬────────────┐
  │          │           │              │            │
Lighting   Crime     Emergency    Infrastructure  Community
(0-100)   (0-100)     Access        (0-100)        Reports
                      (0-100)                      (0-100)
  │          │           │              │            │
  └──────────┴───────────┼──────────────┴────────────┘
                         │
                         ▼
        [ Weighted Safety Aggregator ]
            (src/config/weights.py)
                         │
                         ▼
             Final Safety Score (0–100)
                         │
                         ▼
           Structured JSON Output for UI
```

---

## 3. Folder Structure

```text
safeguard-safety-engine/
│
├── README.md                    # Comprehensive project documentation
├── requirements.txt             # Python dependencies (pandas, numpy, pytest, python-dotenv)
├── .gitignore                   # Python & environment ignore file
├── .env.example                 # Sample environment configuration (SAFEGUARD_ADMIN_KEY)
│
├── data/
│   ├── raw/                     # Raw input datasets
│   │   ├── crime.csv
│   │   ├── lighting.csv
│   │   ├── emergency_services.csv
│   │   ├── infrastructure.csv
│   │   └── community_reports.json
│   │
│   └── processed/               # Directory for cleaned/processed outputs
│       └── .gitkeep
│
├── src/
│   ├── __init__.py
│   │
│   ├── api/                     # HTTP API server (Anushka's routing + Abhinav's reports)
│   │   ├── __init__.py
│   │   └── server.py            # ThreadingHTTPServer, CORS, admin key auth
│   │
│   ├── config/                  # Centralized factor weights & rules
│   │   ├── __init__.py
│   │   └── weights.py
│   │
│   ├── models/                  # Data structures
│   │   ├── __init__.py
│   │   ├── route.py             # Route model
│   │   ├── route_request.py     # RouteRequest / EvaluatedRoute models
│   │   └── community_report.py  # CommunityReport model, ReviewStatus enum
│   │
│   ├── processing/              # Data transformation layer
│   │   ├── __init__.py
│   │   ├── validation.py        # Schema & coordinate checks
│   │   ├── cleaning.py          # Missing values & duplicate handling
│   │   ├── normalization.py     # Reusable Min-Max 0-100 scaling
│   │   ├── route_processing.py  # Haversine distance & spatial filtering
│   │   └── report_validation.py # Community report field validation & sanitization
│   │
│   ├── providers/               # External routing provider wrappers
│   │   ├── __init__.py
│   │   └── routing_provider.py  # OSRM provider + error types
│   │
│   ├── scoring/                 # 0-100 Factor scoring logic
│   │   ├── __init__.py
│   │   ├── crime_score.py
│   │   ├── lighting_score.py
│   │   ├── emergency_score.py
│   │   ├── infrastructure_score.py
│   │   ├── community_score.py
│   │   └── final_score.py       # Weighted score calculator
│   │
│   ├── services/                # Business logic & orchestration
│   │   ├── __init__.py
│   │   ├── safety_engine.py     # Core scoring engine (supports live report provider)
│   │   ├── safety_engine_adapter.py  # Routing ↔ Safety bridge
│   │   ├── routing_service.py   # End-to-end route fetch + score + rank
│   │   ├── route_ranking.py     # Multi-criteria route ranking
│   │   ├── community_service.py # Report submit / review / export pipeline
│   │   ├── incident_classifier.py    # AI text classifier (6 safety categories)
│   │   └── report_analysis.py   # Duplicate detection & aggregation
│   │
│   └── storage/
│       ├── __init__.py
│       └── report_store.py      # Thread-safe in-memory + JSON persistence store
│
├── tests/                       # Unit & integration test suite (121 tests)
│   ├── __init__.py
│   ├── test_cleaning.py
│   ├── test_normalization.py
│   ├── test_scoring.py
│   ├── test_safety_engine.py    # Includes Bug 4 regression tests
│   ├── test_report_store.py     # Includes Bug 1 regression tests
│   ├── test_report_validation.py
│   └── test_api_server.py       # Includes Bug 5 admin key tests
│
└── examples/
    └── sample_route.json        # Sample input route file
```

---

## 4. Expected Data Sources

1. **`crime.csv`**: Contains `area`, `latitude`, `longitude`, `crime_type`, `crime_count`.
2. **`lighting.csv`**: Contains `area`, `latitude`, `longitude`, `lighting_quality` (scale 0–100).
3. **`emergency_services.csv`**: Contains `name`, `type` (`police` or `hospital`), `latitude`, `longitude`.
4. **`infrastructure.csv`**: Contains `area`, `latitude`, `longitude`, `road_condition`, `pedestrian_access`.
5. **`community_reports.json`**: Seed community reports — used only when no live provider is injected (see Bug 4 fix).

---

## 5. Safety Factors & Weighting System

The final score is computed as a weighted average of 5 contextual safety factors:

| Safety Factor | Weight | Configuration File | Direction Rule |
| :--- | :---: | :--- | :--- |
| **Lighting Quality** | **25%** | `src/config/weights.py` | Better lighting → Higher score |
| **Historical Crime** | **25%** | `src/config/weights.py` | Higher crime → Lower score |
| **Emergency Access** | **15%** | `src/config/weights.py` | Closer emergency services → Higher score |
| **Infrastructure** | **15%** | `src/config/weights.py` | Better road & pedestrian quality → Higher score |
| **Community Reports** | **20%** | `src/config/weights.py` | Higher report count & severity → Lower score |

All weights sum to **100% (1.0)** and are stored centrally in `src/config/weights.py`.

---

## 6. Scoring Methodology & Normalization

All raw inputs are transformed into a normalized **0–100 factor score**:
- **`100`** = Safest condition
- **`0`** = Least safe condition

### Min-Max Scaling Formula:
$$\text{Score} = \text{clamp}\left( \frac{\text{Value} - \text{Min}}{\text{Max} - \text{Min}} \times 100, \, 0, \, 100 \right)$$

For inverted metrics (Crime and Community Reports — higher values mean lower safety):
$$\text{Score}_{\text{inverted}} = 100 - \text{Score}$$

### Route Length Bias Elimination (Per-Kilometre Density):
Crime and Community metrics are normalized per kilometre to prevent shorter routes being artificially favoured:
$$\text{route\_km} = \max(\text{route\_length\_km}(\text{coordinates}), \, 0.5)$$
$$\text{crime\_per\_km} = \frac{\text{total\_crime\_count}}{\text{route\_km}}$$
$$\text{severity\_per\_km} = \frac{\text{total\_community\_severity}}{\text{route\_km}}$$

Benchmarks:
- **Max Crime Benchmark**: `10.0 crimes/km`
- **Max Community Severity Benchmark**: `5.0 severity/km`

### Missing Data Policy:
Missing or unavailable factors default to **neutral 50.0** (not 100.0) to avoid falsely implying safety where data is absent.

### Final Weighted Aggregation Formula:
$$\text{Final Safety Score} = \sum_{i=1}^{5} \left( \text{Factor Score}_i \times \text{Weight}_i \right)$$

---

## 7. Installation & Setup

### Step 1: Create a Python Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\activate
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Configure the Admin Key

Copy the example env file and generate a secure key:

```powershell
Copy-Item .env.example .env
```

Generate a key and paste it into `.env`:
```powershell
.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

`.env` contents:
```ini
SAFEGUARD_ADMIN_KEY=your-generated-key-here
SAFEGUARD_ALLOW_INSECURE_ADMIN=0
```

> ⚠️ **Never commit `.env` to git.** Only `.env.example` (with a blank key) is tracked.

---

## 8. Running the Server

**Terminal 1 — Backend API:**
```powershell
.venv\Scripts\python.exe src/api/server.py
```
Server runs on: `http://127.0.0.1:8000`

**Terminal 2 — Frontend Dev Server (Atharav's module):**
```bash
cd frontend
npm install
npm run dev
```
Vite app opens at: `http://localhost:5173`

---

## 9. Running Tests

```bash
pytest tests/
```

**121 tests — all passing.** Breakdown:

| Test File | Tests | Covers |
|---|:---:|---|
| `test_cleaning.py` | ~10 | Data cleaning & deduplication |
| `test_normalization.py` | ~8 | Min-max scaling edge cases |
| `test_scoring.py` | ~20 | All 5 factor scorers |
| `test_safety_engine.py` | 6 | Engine end-to-end + Bug 4 regression |
| `test_report_store.py` | 8 | Store CRUD + Bug 1 regression |
| `test_report_validation.py` | 8 | Report field validation |
| `test_api_server.py` | 30 | HTTP routes + Bug 5 admin key |

---

## 10. Example Input & Output

### Example Input (`examples/sample_route.json`):
```json
{
  "route_id": "route_101",
  "distance_km": 4.2,
  "duration_minutes": 18,
  "coordinates": [
    { "latitude": 12.9716, "longitude": 77.5946 },
    { "latitude": 12.9730, "longitude": 77.5960 },
    { "latitude": 12.9750, "longitude": 77.5980 }
  ]
}
```

### Example Output:
```json
{
  "route_id": "route_101",
  "safety_score": 79.75,
  "breakdown": {
    "lighting": 80.0,
    "crime": 73.33,
    "emergency_access": 82.5,
    "infrastructure": 80.0,
    "community": 86.67
  },
  "weights": {
    "lighting": 0.25,
    "crime": 0.25,
    "emergency_access": 0.15,
    "infrastructure": 0.15,
    "community": 0.2
  },
  "data_quality": "sufficient_data",
  "data_coverage": "supported",
  "status": "success",
  "message": "Safety score calculated contextually based on available route safety parameters."
}
```

---

## 11. Team Integration Interfaces

### How Anushka Integrates Route Data:
Anushka's Routing Engine uses `SafetyEngineAdapter` (which is pre-wired to the live report store in production via `create_server`):

```python
from src.services.safety_engine import SafetyEngine
from src.models.route import Route

engine = SafetyEngine()
engine.load_data()

# Anushka passes route information dynamically:
route_data = Route(
    route_id="route_m2_001",
    distance_km=3.5,
    duration_minutes=14,
    coordinates=[
        {"latitude": 12.9716, "longitude": 77.5946},
        {"latitude": 12.9750, "longitude": 77.5980}
    ]
)

result = engine.analyze_route(route_data)
print(result["safety_score"])
```

### How Abhinav Integrates Community Reports:
Abhinav's service submits and verifies reports — the Safety Engine picks them up automatically on the next `analyze_route()` call (no restart needed):

```python
# Abhinav submits a report:
report, meta = report_svc.submit_report({
    "description": "Broken streetlight near junction",
    "category": "poor_lighting",
    "latitude": 12.9716,
    "longitude": 77.5946,
    "severity": 3
})

# Admin verifies it — immediately affects safety scores:
report_svc.update_review_status(report.report_id, "verified")
```

### Admin Review Endpoints (X-Admin-Key required):

```bash
# Verify a report
curl -X PATCH http://127.0.0.1:8000/api/reports/{id}/review \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: your-key-here" \
  -d '{"status": "verified"}'
```

---

## 12. Abhinav's Module: AI & Community Incident Reports

Abhinav provides the community intelligence and crowdsourced incident reporting system:
- **Incident Validation**: Coordinates (-90 to 90, -180 to 180), text length (5–1000 chars), ISO 8601 timestamps, category normalization.
- **AI Text Classification**: Lightweight, rule- and lexical-assisted NLP classifier matching 6 safety categories:
  - `poor_lighting` — Broken lamps, dark alleys, unlit zones.
  - `road_hazard` — Potholes, road damage, debris, oil spills.
  - `harassment` — Catcalling, verbal abuse, stalking, intimidation.
  - `suspicious_activity` — Loitering, casing cars/property, prowling.
  - `infrastructure_problem` — Open manholes, severe waterlogging, broken sidewalks.
  - `other` — Ambiguous or unclassified reports flagged for human review.
- **Duplicate Detection**: Spatio-temporal + text similarity (Haversine < 200 m, time window < 12 h, Jaccard overlap ≥ 0.35).
- **Report Aggregation & Analytics**: Area filtering by radius, category breakdowns, verified vs. unverified separation.
- **Privacy & Protection**: Automatic PII exclusion; sanitized `to_public_dict()` responses.
- **Integration with Ashutosh & Atharav**:
  - Ashutosh's Safety Engine consumes only human-verified reports via `export_verified_reports_for_safety_engine()`.
  - Atharav's frontend gets dedicated REST endpoints with full CORS for map pins, submission dialogs, and summary analytics.

### Abhinav's REST Endpoints:
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/reports` | Submit community incident report with AI classification |
| GET | `/api/reports` | List public community reports with spatial/status filters |
| GET | `/api/reports/summary` | Aggregate stats, category counts, verified breakdown |
| GET | `/api/reports/{id}` | Individual public report details by ID |
| POST / PATCH | `/api/reports/{id}/review` | Admin review workflow (verified / rejected / duplicate) |

---

## 13. Atharav's Module: Modern Frontend / UI

Atharav delivers an interactive React + Vite frontend for hackathon demonstrations:
- **Interactive Leaflet Map**: Draws exact route geometries with OpenStreetMap tiles, origin/destination pins, and alternate routes.
- **Contextual Safety Analytics**: Real-time visualization of all 5 safety factors.
- **Data Coverage Transparency**: Clearly distinguishes supported coverage (Bangalore sensor buffer) from sparse coverage (fallback baseline).
- **Route Recommendations**: Visual winner badges for Fastest, Safest, and Balanced routes.
- **Configurable API Endpoint**: Seamless connection to Anushka's HTTP server (`http://127.0.0.1:8000`).

---

## 👥 Team Credits

| Role | Name | Responsibility |
|:---:|:---:|:---|
| **Member 1** | **Ashutosh** | Safety Engine — Data validation, normalization, factor scoring, weighted aggregation, security fixes |
| **Member 2** | **Anushka** | Routing Engine — Route calculation, safety adapter, HTTP API server |
| **Member 3** | **Atharav** | Frontend UI — React + Vite map interface, route visualization, safety analytics dashboard |
| **Member 4** | **Abhinav** | Community Reports — Incident submission, AI classification, duplicate detection, review workflow |
