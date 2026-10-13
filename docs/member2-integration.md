# SafeGuard — Member 2: Maps, Routing & Safety Engine Integration Guide

This document details **Member 2's implementation**, architecture, routing provider integration, multi-criteria route ranking, and the clean API contract designed for the separate **React SafeGuard frontend**.

---

## 1. System Architecture & Component Diagram

```text
               React SafeGuard Frontend
            (Vite / Next.js / CRA @ :3000/:5173)
                         │
                         ▼ (HTTP POST with CORS)
     ┌────────────────────────────────────────────────────────┐
     │           SafeGuard HTTP API Server (Member 2)         │
     │                 (src/api/server.py)                    │
     └──────────────────────────┬─────────────────────────────┘
                                │
                                ▼
     ┌────────────────────────────────────────────────────────┐
     │              RoutingService (Orchestrator)             │
     │          (src/services/routing_service.py)             │
     └─────────────┬───────────────────────────┬──────────────┘
                   │                           │
                   ▼                           ▼
       ┌────────────────────────┐  ┌───────────────────────────┐
       │   OSRMProvider (Real)  │  │   SafetyEngineAdapter     │
       │ (src/providers/        │  │ (src/services/            │
       │   routing_provider.py) │  │  safety_engine_adapter.py)│
       └───────────┬────────────┘  └─────────────┬─────────────┘
                   │                             │
                   ▼ (HTTP GET)                  ▼ (Direct Python Call)
       Open Source Routing Machine       Member 1 SafetyEngine
       (https://router.project-osrm.org) (src/services/safety_engine.py)
                   │                             │
                   │                             ▼
                   │                     Raw Safety Datasets
                   │                     (data/raw/*.csv, *.json)
                   │                             │
                   └──────────────┬──────────────┘
                                  │
                                  ▼
                     ┌───────────────────────────┐
                     │    RouteRankingService    │
                     │ (src/services/            │
                     │    route_ranking.py)      │
                     └────────────┬──────────────┘
                                  │
                ┌─────────────────┼─────────────────┐
                ▼                 ▼                 ▼
          Fastest Rank       Safest Rank      Balanced Rank
                │                 │                 │
                └─────────────────┼─────────────────┘
                                  ▼
                   Enriched Multi-Route JSON Payload
                      with Polylines & Breakdowns
```

---

## 2. Strict File Ownership Compliance

Member 1's files and scoring logic remain **100% untouched**:
- `src/config/weights.py` (lighting: 0.25, crime: 0.25, emergency: 0.15, infrastructure: 0.15, community: 0.20) — **Preserved**
- `src/models/route.py` — **Preserved**
- `src/processing/*` (`validation.py`, `cleaning.py`, `normalization.py`, `route_processing.py`) — **Preserved**
- `src/scoring/*` (`lighting_score.py`, `crime_score.py`, `emergency_score.py`, `infrastructure_score.py`, `community_score.py`, `final_score.py`) — **Preserved**
- `src/services/safety_engine.py` — **Preserved**

All new Member 2 functionality is isolated in modular, testable components:
- `src/models/route_request.py`
- `src/providers/routing_provider.py`
- `src/services/safety_engine_adapter.py`
- `src/services/route_ranking.py`
- `src/services/routing_service.py`
- `src/api/server.py`
- `examples/run_member2_demo.py`

---

## 3. Real Routing Provider (OSRM)

### Overview
Route alternatives are calculated using the live Open Source Routing Machine (OSRM) public API. No API key is required, and custom self-hosted OSRM endpoints can be specified using `OSRM_BASE_URL`.

### Critical Coordinate Normalization
- OSRM GeoJSON geometry outputs coordinates in `[longitude, latitude]` format.
- Member 1's `Route` model strictly expects `{"latitude": lat, "longitude": lon}` (or `(lat, lon)` tuple).
- `OSRMProvider` normalizes each coordinate explicitly:
  ```python
  normalized_coords.append({"latitude": float(pt[1]), "longitude": float(pt[0])})
  ```
- Distance is converted from meters to **kilometers** (`km = meters / 1000.0`).
- Duration is converted from seconds to **minutes** (`minutes = seconds / 60.0`).

### Failure Behavior
In compliance with requirements, **no fake routes are fabricated** when external network calls fail. If the provider is unreachable, a `RoutingConnectionError` or `RoutingAPIError` is raised. A `MockRoutingProvider` is available for offline testing and deterministic test suites.

---

## 4. Safety Engine Adapter

The `SafetyEngineAdapter` (`src/services/safety_engine_adapter.py`):
1. Safely invokes Member 1's real `SafetyEngine(data_dir="data/raw")`.
2. Calls `engine.load_data()` with pre-flight file existence checks.
3. Pre-validates coordinates (`-90 <= lat <= 90`, `-180 <= lon <= 180`) using `validate_coordinates`.
4. Passes Member 1's `Route` model to `engine.analyze_route(route)`.
5. Validates Member 1's response schema (ensuring `safety_score` $\in [0, 100]$ and 5 factor breakdowns exist).
6. Raises explicit `SafetyEngineIntegrationError` if any underlying step fails.

---

## 5. Route Ranking Logic

Candidate routes are ranked according to three distinct user preferences:

### 1. Fastest Ranking
- Prioritizes lowest `duration_minutes`.
- Tie-breaker: shortest `distance_km`, then highest `safety_score`.

### 2. Safest Ranking
- Prioritizes highest `safety_score` (0–100) produced by Member 1's `SafetyEngine`.
- Tie-breaker: lowest `duration_minutes`.

### 3. Balanced Ranking
- Evaluates trade-offs between travel duration and safety.
- **Normalized Time Score Calculation ($T_{\text{score}}$)**:
  Let candidate route duration be $T$, minimum duration across alternatives be $T_{\min}$, and maximum be $T_{\max}$:
  $$T_{\text{score}} = 100 \times \left(1 - \frac{T - T_{\min}}{T_{\max} - T_{\min}}\right) \quad (\text{if } T_{\max} > T_{\min}, \text{ else } 100.0)$$
- **Composite Balanced Score**:
  $$\text{BalancedScore} = (0.5 \times \text{SafetyScore}) + (0.5 \times T_{\text{score}})$$
- The top-ranking route in each category receives UI badges/tags (`"fastest"`, `"safest"`, `"balanced"`).

---

## 6. React SafeRoute Frontend API Contract

The API server (`src/api/server.py`) includes full **CORS support** (`Access-Control-Allow-Origin: *`) to allow direct browser `fetch()` requests from `http://localhost:3000` or `http://localhost:5173`.

### Endpoint 1: Health Check
- **Method**: `GET /api/health`
- **Response** `(200 OK)`:
  ```json
  {
    "status": "healthy",
    "service": "safeguard-routing-engine",
    "version": "1.0.0",
    "routing_provider": "OSRM"
  }
  ```

### Endpoint 2: Calculate & Rank Routes
- **Method**: `POST /api/routes/calculate`
- **Request Headers**: `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "origin": {
      "latitude": 12.9716,
      "longitude": 77.5946
    },
    "destination": {
      "latitude": 12.9850,
      "longitude": 77.6100
    },
    "profile": "driving",
    "alternatives": true,
    "preferred_ranking": "balanced"
  }
  ```
  *(Supported profiles: `"driving"`, `"walking"`, `"foot"`, `"cycling"`, `"bike"`)*  
  *(Supported preferred rankings: `"balanced"`, `"fastest"`, `"safest"`)*

- **Response Body** `(200 OK)`:
  ```json
  {
    "status": "success",
    "query": {
      "origin": {
        "latitude": 12.9716,
        "longitude": 77.5946
      },
      "destination": {
        "latitude": 12.9850,
        "longitude": 77.6100
      },
      "profile": "driving",
      "alternatives_requested": true,
      "preferred_ranking": "balanced"
    },
    "total_routes_found": 1,
    "recommendations": {
      "fastest_route_id": "route_1",
      "safest_route_id": "route_1",
      "balanced_route_id": "route_1"
    },
    "routes": [
      {
        "route_id": "route_1",
        "distance_km": 3.15,
        "duration_minutes": 4.95,
        "safety_score": 52.12,
        "breakdown": {
          "lighting": 50.0,
          "crime": 60.0,
          "emergency_access": 47.5,
          "infrastructure": 50.0,
          "community": 50.0
        },
        "weights": {
          "lighting": 0.25,
          "crime": 0.25,
          "emergency_access": 0.15,
          "infrastructure": 0.15,
          "community": 0.2
        },
        "coordinates": [
          {"latitude": 12.971848, "longitude": 77.594697},
          {"latitude": 12.972063, "longitude": 77.59416},
          {"latitude": 12.985021, "longitude": 77.610028}
        ],
        "rankings": {
          "fastest": 1,
          "safest": 1,
          "balanced": 1,
          "balanced_score": 52.12
        },
        "tags": [
          "fastest",
          "safest",
          "balanced"
        ],
        "status": "success",
        "message": "Safety score calculated contextually based on available route safety parameters."
      }
    ]
  }
  ```

### Frontend React Integration Example (Fetch Hook)

Here is a ready-to-use snippet for the React frontend:

```typescript
// useSafeRoute.ts
import { useState } from 'react';

interface Coordinate {
  latitude: number;
  longitude: number;
}

export function useSafeRoute() {
  const [routes, setRoutes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRoutes = async (origin: Coordinate, destination: Coordinate, preference = 'balanced') => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('http://127.0.0.1:8000/api/routes/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          origin,
          destination,
          profile: 'driving',
          alternatives: true,
          preferred_ranking: preference
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || 'Routing failed');
      }

      const data = await response.json();
      setRoutes(data.routes);
      return data;
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return { routes, loading, error, fetchRoutes };
}
```

---

## 7. How to Run and Test Member 2

### 1. Run Complete Test Suite (Pytest)
```bash
.\.venv\Scripts\pytest
```
*Executes all 48 tests (16 Member 1 tests + 32 Member 2 tests).*

### 2. Run Member 2 Interactive Demo
```bash
.\.venv\Scripts\python examples\run_member2_demo.py
```
*Queries OSRM, runs Member 1's engine, computes factors, and displays comparison table.*

### 3. Launch HTTP API Server
```bash
.\.venv\Scripts\python src\api\server.py 8000
```
*Starts server on `http://127.0.0.1:8000` with CORS enabled for the React frontend.*

---

## 8. Blockers & Collaboration Notes with Member 1

1. **Safety Dataset Coordinate Bounds**:
   - Member 1's current raw safety datasets in `data/raw/` cover central Bangalore (`lat ~ 12.97 to 12.985`, `lon ~ 77.59 to 77.61`).
   - If queries originate far outside Bangalore, Member 1's default spatial buffer filter (`1.0 km`) finds no nearby crime/lighting records, returning baseline neutral scores (~50).
   - *Recommendation for Member 1*: Expand `data/raw/` datasets for other geographical regions when testing multi-city routes.
2. **Coordinate Tuple Assumption**:
   - Member 1's `Route._clean_coordinates` assumes `(lat, lon)` order when provided as tuples or lists. Member 2 explicitly feeds `{"latitude": lat, "longitude": lon}` dictionaries to prevent coordinate inversion bugs.
