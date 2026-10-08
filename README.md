# SafeGuard — Safety Score & Data Processing Engine (Member 1)

Welcome to **SafeGuard**, a smart contextual safety navigation system built for hackathons!

This repository contains **Member 1's module**: the **Safety Engine**. The Safety Engine ingests raw environmental, historical, and community safety data, validates and normalizes it, processes route coordinates against spatial data buffers, and calculates a transparent, explainable **Safety Score between 0 and 100**.

> ⚠️ **Important Disclaimer**: SafeGuard does **not** predict crime. The Safety Score represents a transparent, contextual safety signal derived directly from identifiable data sources (lighting quality, historical crime counts, emergency service proximity, infrastructure conditions, and community reports).

---

## 1. Member 1 Responsibilities

As **Member 1**, this module is responsible for:
- **Data Validation & Cleaning**: Ensuring raw dataset schemas are intact, handling missing values, and dropping duplicate entries.
- **Data Normalization**: Scaling disparate metrics (e.g., crime counts, rating scales, distance measurements) to a uniform `0–100` scale.
- **Route Data Processing**: Buffer-matching geographical route coordinates against nearby safety data points.
- **Individual Factor Scoring**: Computing 0–100 factor scores for Lighting, Crime, Emergency Access, Infrastructure, and Community Reports.
- **Weighted Aggregation**: Calculating an explainable weighted final score between 0 and 100.
- **Integration Interfaces**: Providing clean interfaces for **Member 2** (Routing Engine) and **Member 4** (Community Reporting System).

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
├── README.md                  # Comprehensive project documentation
├── requirements.txt           # Minimal Python dependencies (pandas, numpy, pytest)
├── .gitignore                 # Python & environment ignore file
├── .env.example               # Sample environment configuration
│
├── data/
│   ├── raw/                   # Raw input datasets
│   │   ├── crime.csv
│   │   ├── lighting.csv
│   │   ├── emergency_services.csv
│   │   ├── infrastructure.csv
│   │   └── community_reports.json
│   │
│   └── processed/             # Directory for cleaned/processed outputs
│       └── .gitkeep
│
├── src/
│   ├── __init__.py
│   │
│   ├── config/                # Centralized factor weights & rules
│   │   ├── __init__.py
│   │   └── weights.py
│   │
│   ├── processing/            # Data transformation layer
│   │   ├── __init__.py
│   │   ├── validation.py      # Schema & coordinate checks
│   │   ├── cleaning.py        # Missing values & duplicate handling
│   │   ├── normalization.py   # Reusable Min-Max 0-100 scaling
│   │   └── route_processing.py# Haversine distance & spatial filtering
│   │
│   ├── scoring/               # 0-100 Factor scoring logic
│   │   ├── __init__.py
│   │   ├── crime_score.py
│   │   ├── lighting_score.py
│   │   ├── emergency_score.py
│   │   ├── infrastructure_score.py
│   │   ├── community_score.py
│   │   └── final_score.py     # Weighted score calculator
│   │
│   ├── models/                # Data structures
│   │   ├── __init__.py
│   │   └── route.py           # Route model representation
│   │
│   ├── services/              # Pipeline orchestrator
│   │   ├── __init__.py
│   │   └── safety_engine.py   # Main engine service interface
│   │
│   └── main.py                # Runnable CLI entry point
│
├── tests/                     # Unit test suite
│   ├── __init__.py
│   ├── test_cleaning.py
│   ├── test_normalization.py
│   ├── test_scoring.py
│   └── test_safety_engine.py
│
└── examples/
    └── sample_route.json      # Sample input route file
```

---

## 4. Expected Data Sources

1. **`crime.csv`**: Contains `area`, `latitude`, `longitude`, `crime_type`, `crime_count`.
2. **`lighting.csv`**: Contains `area`, `latitude`, `longitude`, `lighting_quality` (scale 0–100).
3. **`emergency_services.csv`**: Contains `name`, `type` (`police` or `hospital`), `latitude`, `longitude`.
4. **`infrastructure.csv`**: Contains `area`, `latitude`, `longitude`, `road_condition`, `pedestrian_access`.
5. **`community_reports.json`**: Contains `report_id`, `report_type`, `latitude`, `longitude`, `severity` (1–5), `timestamp`, `description`.

---

## 5. Safety Factors & Weighting System

The final score is computed as a weighted average of 5 contextual safety factors:

| Safety Factor | Weight | Configuration File | Direction Rule |
| :--- | :---: | :--- | :--- |
| **Lighting Quality** | **25%** | `src/config/weights.py` | Better lighting $\rightarrow$ Higher score |
| **Historical Crime** | **25%** | `src/config/weights.py` | Higher crime $\rightarrow$ Lower score |
| **Emergency Access** | **15%** | `src/config/weights.py` | Closer emergency services $\rightarrow$ Higher score |
| **Infrastructure** | **15%** | `src/config/weights.py` | Better road & pedestrian quality $\rightarrow$ Higher score |
| **Community Reports** | **20%** | `src/config/weights.py` | Higher report count & severity $\rightarrow$ Lower score |

All weights sum to **100% (1.0)** and are stored centrally in `src/config/weights.py`.

---

## 6. Scoring Methodology & Normalization

All raw inputs are transformed into a normalized **0–100 factor score**:
- **`100`** = Safest condition
- **`0`** = Least safe condition

### Min-Max Scaling Formula:
$$\text{Score} = \text{clamp}\left( \frac{\text{Value} - \text{Min}}{\text{Max} - \text{Min}} \times 100, \, 0, \, 100 \right)$$

For inverted metrics (such as Crime and Community Reports where higher raw values mean lower safety):
$$\text{Score}_{\text{inverted}} = 100 - \text{Score}$$

### Final Weighted Aggregation Formula:
$$\text{Final Safety Score} = \sum_{i=1}^{5} \left( \text{Factor Score}_i \times \text{Weight}_i \right)$$

---

## 7. Installation & Setup Instructions

### Step 1: Create a Python Virtual Environment
Open your terminal inside the `safeguard-safety-engine/` directory:

#### On Windows (PowerShell / Command Prompt):
```bash
python -m venv .venv
.venv\Scripts\activate
```

#### On macOS / Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 8. Running the Engine

To run the first working version using the sample route:

```bash
python src/main.py
```

---

## 9. Running Tests

To run the complete test suite:

```bash
pytest
```

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
  "status": "success",
  "message": "Safety score calculated contextually based on available route safety parameters."
}
```

---

## 11. Team Integration Interfaces

### How Member 2 Integrates Route Data:
Member 2 (Routing Engine) can pass route details directly to the engine in Python:

```python
from src.services.safety_engine import SafetyEngine
from src.models.route import Route

engine = SafetyEngine()
engine.load_data()

# Member 2 passes route information dynamically:
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

### How Member 4 Integrates Community Reports:
Member 4 (Community Reports System) can update or append new user reports to `data/raw/community_reports.json` or update `engine.community_reports` dynamically:

```python
# Member 4 appends new community reports:
new_report = {
    "report_id": "rep_105",
    "report_type": "street_light_out",
    "latitude": 12.9718,
    "longitude": 77.5948,
    "severity": 3,
    "timestamp": "2026-10-08T12:00:00Z",
    "description": "Streetlight flickers near main corner"
}

engine.community_reports.append(new_report)
```
