# SafeGuard — Contextual Safety Score & Data Processing Engine

**SafeGuard** is a smart contextual safety navigation system that provides real-time, explainable safety scores for geographical routes. The engine ingests raw environmental, historical, and community safety data, validates and normalizes it, then produces a transparent **Safety Score between 0 and 100** to help users make informed navigation decisions.

> **Disclaimer:** SafeGuard does **not** predict crime. The Safety Score is a transparent, contextual signal derived from identifiable data sources — lighting quality, historical crime counts, emergency service proximity, infrastructure conditions, and community reports.

---

## Table of Contents

1. [Architecture & Pipeline](#architecture--pipeline)
2. [Folder Structure](#folder-structure)
3. [Data Sources](#data-sources)
4. [Safety Factors & Weighting](#safety-factors--weighting)
5. [Scoring Methodology](#scoring-methodology)
6. [Installation & Setup](#installation--setup)
7. [Running the Server](#running-the-server)
8. [API Reference](#api-reference)
9. [Running Tests](#running-tests)
10. [Example Input & Output](#example-input--output)
11. [Integration Guide](#integration-guide)

---

## Architecture & Pipeline

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
           Structured JSON Output for UI / Routing Engine
```

**Core Capabilities:**
- **Data Validation & Cleaning** — Enforces raw dataset schemas, handles missing values, and removes duplicate entries.
- **Data Normalization** — Scales disparate metrics (crime counts, rating scales, distances) to a uniform `0–100` scale.
- **Route Data Processing** — Buffer-matches geographical route coordinates against nearby safety data points using Haversine distance.
- **Individual Factor Scoring** — Computes 0–100 factor scores for Lighting, Crime, Emergency Access, Infrastructure, and Community Reports.
- **Weighted Aggregation** — Calculates an explainable weighted final score between 0 and 100.
- **HTTP API** — Serves REST endpoints for route calculation, comparison, and community report management.
- **Security** — Server-side report ID generation, protection against report overwrites, and constant-time admin key validation.

---

## Folder Structure

```text
safeguard-safety-engine/
│
├── README.md                    # Project documentation
├── requirements.txt             # Python dependencies
├── .gitignore
├── .env.example                 # Sample environment configuration
│
├── data/
│   ├── raw/                     # Raw input datasets
│   │   ├── crime.csv
│   │   ├── lighting.csv
│   │   ├── emergency_services.csv
│   │   ├── infrastructure.csv
│   │   └── community_reports.json
│   └── processed/               # Output directory for cleaned data
│
├── src/
│   ├── api/
│   │   └── server.py            # ThreadingHTTPServer with CORS & admin key auth
│   │
│   ├── config/
│   │   └── weights.py           # Centralized factor weights & scoring rules
│   │
│   ├── models/
│   │   ├── route.py             # Route model
│   │   ├── route_request.py     # RouteRequest / EvaluatedRoute models
│   │   └── community_report.py  # CommunityReport model, ReviewStatus enum
│   │
│   ├── processing/
│   │   ├── validation.py        # Schema & coordinate checks
│   │   ├── cleaning.py          # Missing values & duplicate handling
│   │   ├── normalization.py     # Reusable Min-Max 0–100 scaling
│   │   ├── route_processing.py  # Haversine distance & spatial filtering
│   │   └── report_validation.py # Community report field validation & sanitization
│   │
│   ├── providers/
│   │   └── routing_provider.py  # OSRM routing provider & error types
│   │
│   ├── scoring/
│   │   ├── crime_score.py
│   │   ├── lighting_score.py
│   │   ├── emergency_score.py
│   │   ├── infrastructure_score.py
│   │   ├── community_score.py
│   │   └── final_score.py       # Weighted score calculator
│   │
│   ├── services/
│   │   ├── safety_engine.py          # Core scoring engine
│   │   ├── safety_engine_adapter.py  # Routing ↔ Safety bridge
│   │   ├── routing_service.py        # End-to-end route fetch, score & rank
│   │   ├── route_ranking.py          # Multi-criteria route ranking
│   │   ├── community_service.py      # Report submit / review / export pipeline
│   │   ├── incident_classifier.py    # AI text classifier (6 safety categories)
│   │   └── report_analysis.py        # Duplicate detection & aggregation
│   │
│   └── storage/
│       └── report_store.py      # Thread-safe in-memory + JSON persistence store
│
├── tests/                       # Unit & integration test suite (121 tests)
│   ├── test_cleaning.py
│   ├── test_normalization.py
│   ├── test_scoring.py
│   ├── test_safety_engine.py
│   ├── test_report_store.py
│   ├── test_report_validation.py
│   └── test_api_server.py
│
└── examples/
    └── sample_route.json        # Sample input route file
```

---

## Data Sources

The engine expects the following input datasets in `data/raw/`:

| File | Required Fields |
|:---|:---|
| `crime.csv` | `area`, `latitude`, `longitude`, `crime_type`, `crime_count` |
| `lighting.csv` | `area`, `latitude`, `longitude`, `lighting_quality` (0–100 scale) |
| `emergency_services.csv` | `name`, `type` (`police` or `hospital`), `latitude`, `longitude` |
| `infrastructure.csv` | `area`, `latitude`, `longitude`, `road_condition`, `pedestrian_access` |
| `community_reports.json` | Seed community reports — used when no live provider is injected |

---

## Safety Factors & Weighting

The final score is a weighted average of five contextual safety factors, all configurable in `src/config/weights.py`:

| Safety Factor | Weight | Scoring Direction |
|:---|:---:|:---|
| **Lighting Quality** | **25%** | Better lighting → Higher score |
| **Historical Crime** | **25%** | Higher crime → Lower score |
| **Emergency Access** | **15%** | Closer services → Higher score |
| **Infrastructure** | **15%** | Better road & pedestrian quality → Higher score |
| **Community Reports** | **20%** | Higher severity & count → Lower score |

All weights sum to **100%**.

---

## Scoring Methodology

All raw inputs are normalized to a **0–100 factor score**, where **100 = Safest** and **0 = Least Safe**.

### Min-Max Scaling

$$\text{Score} = \text{clamp}\left( \frac{\text{Value} - \text{Min}}{\text{Max} - \text{Min}} \times 100,\; 0,\; 100 \right)$$

For inverted metrics (Crime and Community Reports — where higher values mean lower safety):

$$\text{Score}_{\text{inverted}} = 100 - \text{Score}$$

### Route Length Bias Elimination

Crime and Community metrics are normalized per kilometre to prevent shorter routes from being artificially favoured:

$$\text{route\_km} = \max(\text{route\_length\_km}(\text{coordinates}),\; 0.5)$$

$$\text{crime\_per\_km} = \frac{\text{total\_crime\_count}}{\text{route\_km}}$$

Benchmarks used for normalization:
- **Max Crime Benchmark**: `10.0 crimes/km`
- **Max Community Severity Benchmark**: `5.0 severity/km`

### Missing Data Policy

Missing or unavailable factors default to a **neutral 50.0** (not 100.0), avoiding false implications of safety where data is absent.

### Final Aggregation

$$\text{Final Safety Score} = \sum_{i=1}^{5} \left( \text{Factor Score}_i \times \text{Weight}_i \right)$$

---

## Installation & Setup

### Step 1: Create a Virtual Environment

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

Copy the example environment file:
```powershell
Copy-Item .env.example .env
```

Generate a secure key and add it to `.env`:
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

## Running the Server

**Start the backend API:**
```powershell
.venv\Scripts\python.exe src/api/server.py
```

The server runs on: `http://127.0.0.1:8000`

**Optional — Start the frontend dev server:**
```bash
cd frontend
npm install
npm run dev
```

Vite app opens at: `http://localhost:5173`

---

## API Reference

### Route Endpoints

| Method | Endpoint | Description |
|:---:|:---|:---|
| `GET` | `/api/health` | System health & provider status |
| `POST` | `/api/routes/calculate` | Fetch real routes, compute safety scores & rank |
| `POST` | `/api/routes/compare` | Compare and rank pre-computed or custom routes |

### Community Report Endpoints

| Method | Endpoint | Description |
|:---:|:---|:---|
| `POST` | `/api/reports` | Submit a community incident report with AI classification |
| `GET` | `/api/reports` | List public reports with spatial/status filters |
| `GET` | `/api/reports/summary` | Aggregate stats, category counts, verified breakdown |
| `GET` | `/api/reports/{id}` | Individual public report details |
| `POST / PATCH` | `/api/reports/{id}/review` | Admin review workflow — `X-Admin-Key` header required |

### Admin Review Example

```bash
curl -X PATCH http://127.0.0.1:8000/api/reports/{id}/review \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: your-key-here" \
  -d '{"status": "verified"}'
```

---

## Running Tests

```bash
pytest tests/
```

**121 tests — all passing.** Coverage breakdown:

| Test File | Tests | Covers |
|:---|:---:|:---|
| `test_cleaning.py` | ~10 | Data cleaning & deduplication |
| `test_normalization.py` | ~8 | Min-max scaling edge cases |
| `test_scoring.py` | ~20 | All 5 factor scorers |
| `test_safety_engine.py` | 6 | Engine end-to-end & regression |
| `test_report_store.py` | 8 | Store CRUD & regression |
| `test_report_validation.py` | 8 | Report field validation |
| `test_api_server.py` | 30 | HTTP routes & admin key auth |

---

## Example Input & Output

### Input (`examples/sample_route.json`)

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

### Output

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
    "community": 0.20
  },
  "data_quality": "sufficient_data",
  "data_coverage": "supported",
  "status": "success",
  "message": "Safety score calculated contextually based on available route safety parameters."
}
```

---

## Integration Guide

### Using the Safety Engine Programmatically

```python
from src.services.safety_engine import SafetyEngine
from src.models.route import Route

engine = SafetyEngine()
engine.load_data()

route_data = Route(
    route_id="route_001",
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

### Submitting & Verifying Community Reports

Verified community reports are picked up automatically on the next `analyze_route()` call — no server restart required.

```python
from src.services.community_service import CommunityReportService

report_svc = CommunityReportService()

# Submit a report
report, meta = report_svc.submit_report({
    "description": "Broken streetlight near junction",
    "category": "poor_lighting",
    "latitude": 12.9716,
    "longitude": 77.5946,
    "severity": 3
})

# Verify the report — immediately affects safety scores
report_svc.update_review_status(report.report_id, "verified")
```

### AI Incident Classification

The engine includes a lightweight NLP classifier that auto-categorizes submitted reports into 6 safety categories:

| Category | Description |
|:---|:---|
| `poor_lighting` | Broken lamps, dark alleys, unlit zones |
| `road_hazard` | Potholes, road damage, debris, oil spills |
| `harassment` | Verbal abuse, stalking, intimidation |
| `suspicious_activity` | Loitering, prowling, casing properties |
| `infrastructure_problem` | Open manholes, waterlogging, broken sidewalks |
| `other` | Ambiguous reports flagged for human review |

### Duplicate Detection

Incoming reports are automatically screened for duplicates using:
- **Spatial proximity**: Haversine distance < 200 m
- **Time window**: Submission within 12 hours of an existing report
- **Text similarity**: Jaccard overlap ≥ 0.35

---

*SafeGuard is designed to complement human judgement, not replace it. All safety scores are contextual signals and should be interpreted alongside local knowledge and common sense.*
