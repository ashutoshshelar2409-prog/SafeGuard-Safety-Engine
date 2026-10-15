# SafeGuard — Member 4: AI & Community Incident Reports Integration Guide

This document provides complete technical documentation for **Member 4's implementation**: community incident reporting, explainable AI text classification, spatio-temporal duplicate detection, report aggregation, and REST API integration with the existing SafeGuard backend.

---

## 1. System Architecture & Component Diagram

```text
               React SafeRoute Frontend (Member 3)
           (Map UI, Incident Submission Form, Summary Cards)
                                │
                                ▼ (HTTP with CORS)
    ┌───────────────────────────────────────────────────────────────┐
    │              SafeGuard HTTP API Server (src/api/server.py)    │
    │   GET /api/health            POST /api/reports                │
    │   POST /api/routes/calculate GET  /api/reports                │
    │   POST /api/routes/compare   GET  /api/reports/summary        │
    │                              PATCH /api/reports/{id}/review   │
    └───────────────────────┬───────────────────────────────────────┘
                            │
                            ▼
    ┌───────────────────────────────────────────────────────────────┐
    │            CommunityReportService (Member 4 Coordinator)      │
    │                (src/services/community_service.py)           │
    └───────┬───────────────────────┬───────────────────────┬───────┘
            │                       │                       │
            ▼                       ▼                       ▼
┌───────────────────────┐ ┌───────────────────┐ ┌───────────────────────┐
│   Report Validation   │ │IncidentClassifier │ │   DuplicateDetector   │
│(src/processing/       │ │(src/services/     │ │(src/services/         │
│ report_validation.py) │ │ incident_         │ │ report_analysis.py)   │
│ • Coordinate bounds   │ │ classifier.py)    │ │ • Haversine proximity │
│ • Text length (5-1000)│ │ • Explainable NLP │ │ • Temporal window     │
│ • ISO 8601 timestamps │ │ • 6 categories    │ │ • Jaccard vocabulary  │
│ • Strict schema checks│ │ • Review flagging │ │   similarity          │
└───────────────────────┘ └───────────────────┘ └───────────────────────┘
            │                       │                       │
            └───────────────────────┼───────────────────────┘
                                    │
                                    ▼
    ┌───────────────────────────────────────────────────────────────┐
    │               Thread-Safe Storage & Privacy                   │
    │               (src/storage/report_store.py)                   │
    │ • In-memory store with optional JSON file persistence         │
    │ • PII masking & sanitized public dictionary generation        │
    │ • Separation of verified vs unverified reports                │
    └───────────────────────┬───────────────────────────────────────┘
                            │
                            ▼
              Member 1 SafetyEngine Integration
           (src/services/community_service.py -> export)
     (Allows SafetyEngine to consume verified reports safely)
```

---

## 2. Core Modules Implemented

| Module | File Path | Responsibilities |
|---|---|---|
| **Data Models** | `src/models/community_report.py` | `CommunityReport`, `ReviewStatus`, `IncidentCategory`, `ClassificationResult`, `to_public_dict()`. |
| **Validation** | `src/processing/report_validation.py` | Coordinate checks, description bounds (5-1000 chars), ISO timestamps, category normalization. |
| **AI Classifier** | `src/services/incident_classifier.py` | Explainable NLP keyword and phrase matching, confidence scoring, ambiguity and review flagging. |
| **Analysis & Duplicates** | `src/services/report_analysis.py` | Spatio-temporal duplicate detection (Haversine + Jaccard), spatial radius filtering, aggregate statistics. |
| **Storage & Privacy** | `src/storage/report_store.py` | Thread-safe persistence, seed data loading, sanitized public views with PII exclusion. |
| **Service Coordinator** | `src/services/community_service.py` | Orchestrates ingestion, classification, duplicate linking, review workflows, and Member 1 export. |
| **HTTP Server** | `src/api/server.py` | Preserves Member 2 routing endpoints and adds `/api/reports*` endpoints with full CORS. |

---

## 3. Data Schema & Privacy Safeguards

### Report Model (`CommunityReport`)
- `report_id`: Unique string identifier (`rep_...`).
- `description`: Free-text description of the incident (5 to 1000 characters).
- `category`: Canonical category key (e.g. `poor_lighting`, `road_hazard`, `harassment`, `suspicious_activity`, `infrastructure_problem`, `other`).
- `category_label`: Human-readable display label (e.g. "Poor lighting", "Road hazard").
- `latitude`: Float between `-90.0` and `90.0`.
- `longitude`: Float between `-180.0` and `180.0`.
- `incident_time`: Optional ISO 8601 string (cannot be in the future).
- `submission_timestamp`: ISO 8601 string recorded at submission.
- `review_status`: Lifecycle state (`pending`, `verified`, `rejected`, `duplicate`).
- `severity`: Integer between 1 and 5.
- `classification_result`: Explainable classification metadata (`suggested_category`, `confidence`, `keywords_matched`, `needs_review`, `explanation`).
- `possible_duplicate_of`: Optional reference to earlier incident `report_id`.

### Privacy Safeguards
- **Zero Unnecessary PII**: The service collects no user emails, phone numbers, real names, or device identifiers.
- **Sanitized Public Responses**: The endpoint calls `report.to_public_dict()`, ensuring internal administrative fields or submitter metadata are never exposed over the wire.
- **Explicit Disclaimers**: All responses clearly declare crowdsourced origin and explicitly state reports do not represent confirmed crime statistics.

---

## 4. Explainable AI Text Classification

### Methodology
The classifier uses a **lightweight, explainable rule- and lexical-assisted NLP architecture**:
1. **Multi-Word Phrase Matching**: Compiled regex patterns detect high-specificity phrases (e.g., `"broken street lamp"`, `"catcalling reported"`, `"open manhole"`, `"casing cars"`).
2. **Domain Token Density**: Weighted keyword tokens score candidate categories (e.g., `"unlit"`, `"pothole"`, `"stalking"`, `"waterlogging"`).
3. **Non-Linear Confidence Scaling**: Scaled via $C = \frac{S}{S + 2.2} \in [0, 1.0]$.
4. **Ambiguity and Review Flagging**:
   - If confidence is $< 0.40$, categorized as `other` and flagged `needs_review = True`.
   - If two categories compete with close scores (relative ratio $\ge 0.50$ or difference $\le 1.5$), flagged `needs_review = True`.
5. **Transparency Disclaimer**: We do not claim unverified machine learning benchmark accuracy. This lightweight classifier serves as a fast first-stage triage layer.

---

## 5. Duplicate Detection & Aggregation

### Duplicate Detection Heuristics
When a new report arrives, `DuplicateDetector` compares it against active existing reports:
- **Spatial Distance**: Haversine distance $d \le 200\text{ meters}$.
- **Temporal Proximity**: Incident or submission time difference $\le 12\text{ hours}$.
- **Lexical Overlap**: Jaccard similarity index on word tokens:
  $$\text{Jaccard}(A, B) = \frac{|A \cap B|}{|A \cup B|} \ge 0.35$$
- **High-Confidence Match ($d \le 60\text{m}$ & same category)**: Automatically flagged as `possible_duplicate_of` with review status set to `duplicate`.

### Aggregation & Summaries
`ReportAggregator` computes:
- Total reports count.
- **Separation between verified and unverified reports** (`verified_count`, `unverified_count`, `verified_percentage`).
- Category-level distribution with verified/unverified breakdown.
- Temporal recency counts (past 24 hours, past 7 days, all-time).
- Spatial radius filtering (`lat`, `lon`, `radius_km`).

---

## 6. HTTP API Endpoints

### 1. Submit Community Report
- **URL**: `POST /api/reports` (or `/reports`)
- **Headers**: `Content-Type: application/json`
- **Request Body**:
```json
{
  "description": "Flickering street lamp makes the bus stop unsafe at night",
  "category": "poor_lighting",
  "latitude": 12.9716,
  "longitude": 77.5946,
  "incident_time": "2026-10-15T20:30:00Z",
  "severity": 3
}
```
- **Response (201 Created)**:
```json
{
  "status": "success",
  "message": "Community incident report submitted successfully.",
  "report": {
    "report_id": "rep_940c3101d248",
    "description": "Flickering street lamp makes the bus stop unsafe at night",
    "category": "poor_lighting",
    "category_label": "Poor lighting",
    "latitude": 12.9716,
    "longitude": 77.5946,
    "incident_time": "2026-10-15T20:30:00Z",
    "submission_timestamp": "2026-10-15T11:45:00+00:00",
    "review_status": "pending",
    "is_verified": false,
    "severity": 3,
    "classification": {
      "suggested_category": "poor_lighting",
      "confidence": 0.636,
      "needs_review": false
    },
    "possible_duplicate_of": null,
    "source": "community_crowdsourced",
    "disclaimer": "Community reports are crowdsourced user observations and do not represent confirmed crime statistics."
  },
  "metadata": {
    "duplicate_detected": false,
    "possible_duplicate_of": null,
    "duplicate_confidence": 0.0,
    "duplicate_reason": "",
    "classification": {
      "suggested_category": "poor_lighting",
      "confidence": 0.636,
      "method": "rule_based_lexical_nlp",
      "keywords_matched": ["flickering light", "lighting"],
      "needs_review": false,
      "explanation": "Matched Poor lighting based on keywords: 'flickering light', 'lighting'."
    }
  }
}
```

### 2. List Community Reports
- **URL**: `GET /api/reports`
- **Query Parameters**:
  - `status`: `pending`, `verified`, `rejected`, `duplicate`, or `all` (default: `all`).
  - `category`: Filter by category (e.g. `poor_lighting`, `harassment`).
  - `lat`, `lon`, `radius_km`: Spatial radius filter in kilometers.
  - `time_window`: `24h`, `7d`, `30d`, or `all`.
- **Response (200 OK)**:
```json
{
  "status": "success",
  "count": 4,
  "reports": [
    {
      "report_id": "rep_001",
      "description": "Broken street lamp near bus stand",
      "category": "poor_lighting",
      "category_label": "Poor lighting",
      "latitude": 12.9720,
      "longitude": 77.5950,
      "review_status": "verified",
      "is_verified": true,
      "severity": 2,
      "source": "community_crowdsourced",
      "disclaimer": "Community reports are crowdsourced user observations and do not represent confirmed crime statistics."
    }
  ],
  "disclaimer": "Community reports are crowdsourced user observations and do not represent confirmed crime statistics."
}
```

### 3. Report Summaries & Aggregation
- **URL**: `GET /api/reports/summary`
- **Query Parameters**: `lat`, `lon`, `radius_km` (optional).
- **Response (200 OK)**:
```json
{
  "status": "success",
  "summary": {
    "total_reports": 4,
    "verification_summary": {
      "verified_count": 3,
      "unverified_count": 1,
      "rejected_count": 0,
      "duplicate_count": 0,
      "verified_percentage": 75.0
    },
    "status_breakdown": {
      "pending": 1,
      "verified": 3,
      "rejected": 0,
      "duplicate": 0
    },
    "time_window_breakdown": {
      "past_24_hours": 1,
      "past_7_days": 3,
      "all_time": 4
    },
    "categories": [
      {
        "category": "poor_lighting",
        "label": "Poor lighting",
        "total_count": 1,
        "verified_count": 1,
        "unverified_count": 0
      },
      {
        "category": "harassment",
        "label": "Harassment",
        "total_count": 1,
        "verified_count": 1,
        "unverified_count": 0
      }
    ],
    "source_type": "community_crowdsourced",
    "disclaimer": "Community reports are crowdsourced user observations and do not represent confirmed crime statistics or verified municipal records."
  }
}
```

### 4. Moderator Review
- **URL**: `POST /api/reports/{id}/review` or `PATCH /api/reports/{id}/review`
- **Request Body**:
```json
{
  "status": "verified"
}
```
- **Response (200 OK)**:
```json
{
  "status": "success",
  "message": "Report 'rep_001' review status updated to 'verified'.",
  "report": {
    "report_id": "rep_001",
    "review_status": "verified",
    "is_verified": true
  }
}
```

---

## 7. Storage Architecture & Limitations

### Prototype Storage
- Reports are stored in-memory in `ReportStore` protected by a re-entrant mutex lock (`threading.RLock`).
- Default seed reports load automatically from `data/raw/community_reports.json`.
- Optional local JSON file persistence is supported via `persistence_file`.

### Limitations & Production Upgrade
- File-based / in-memory storage is intended for prototypes, local evaluation, and pairing with frontend developers.
- It does not support distributed multi-node synchronization or geospatial indexing (e.g. R-Tree).
- For production, replace `ReportStore` with PostgreSQL + PostGIS (`GEOMETRY(Point, 4326)`), utilizing spatial indexing (`ST_DWithin`, `ST_Distance`).

---

## 8. Integration Instructions for Team Members

### For Member 1 (Safety Score Engine)
- **Neutrality Guarantee**: Member 4 does **NOT** modify Member 1's `calculate_community_score` weights (`FACTOR_WEIGHTS`) or scoring formula.
- **Consuming Verified Reports**:
  Member 1's `SafetyEngine` can ingest only human-verified reports via `CommunityReportService`:
  ```python
  from src.services.community_service import CommunityReportService

  service = CommunityReportService()
  verified_reports = service.export_verified_reports_for_safety_engine()
  # Pass verified_reports to SafetyEngine
  ```
  This ensures unverified or malicious crowd submissions do not artificially distort route safety ratings.

### For Member 3 (React SafeRoute Frontend)
- **Submit Dialog**: Send `POST /api/reports` with `description`, `latitude`, `longitude`, and optional `category`.
- **Map Pins**: Call `GET /api/reports?status=verified` or `GET /api/reports` to plot markers on Leaflet/Mapbox:
  - Verified marker: Green check badge (`is_verified: true`).
  - Pending marker: Orange badge (`is_verified: false`).
- **Dashboard Stats**: Query `GET /api/reports/summary` to populate summary cards (verified vs unverified count, category breakdowns).
- **CORS Support**: Full CORS headers are active (`Access-Control-Allow-Origin: *`).

---

## 9. Verification & Test Execution

Run the complete test suite:
```bash
.venv\Scripts\python -m pytest
```
Output:
```text
collected 112 items

tests\test_api_server.py .........................                       [ 22%]
tests\test_cleaning.py ......                                            [ 27%]
tests\test_incident_classifier.py ........                               [ 34%]
tests\test_normalization.py ....                                         [ 38%]
tests\test_report_analysis.py ......                                     [ 43%]
tests\test_report_api.py ........                                        [ 50%]
tests\test_report_store.py ......                                        [ 56%]
tests\test_report_validation.py ........                                 [ 63%]
tests\test_route_ranking.py .....                                        [ 67%]
tests\test_route_request.py .......                                      [ 74%]
tests\test_routing_provider.py .......                                   [ 80%]
tests\test_routing_service.py ...                                        [ 83%]
tests\test_safety_adapter.py ......                                      [ 88%]
tests\test_safety_engine.py ....                                         [ 91%]
tests\test_scoring.py .........                                          [100%]

============================= 112 passed in 2.51s =============================
```
