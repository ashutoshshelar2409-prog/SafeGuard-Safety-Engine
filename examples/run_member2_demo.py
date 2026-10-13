"""
Member 2 Demonstration Script: Routing, Safety Engine Integration & Multi-Criteria Ranking.
Demonstrates:
1. Origin/Destination Coordinate validation.
2. Real routing calculation via OSRM.
3. Analysis through Member 1's SafetyEngine.
4. Fastest, Safest, and Balanced ranking output.
"""

import json
import os
import sys

# Ensure project root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models.route_request import Coordinate, RouteRequest
from src.providers.routing_provider import OSRMProvider, MockRoutingProvider, RoutingError
from src.services.safety_engine_adapter import SafetyEngineAdapter
from src.services.route_ranking import RouteRankingService
from src.services.routing_service import RoutingService


def run_demo():
    print("=" * 70)
    print("     SAFEGUARD - MEMBER 2 ROUTING & SAFETY ENGINE INTEGRATION       ")
    print("=" * 70)

    # Coordinates covering Bangalore test area with safety data
    # Origin: Downtown Bangalore (MG Road / Cubbon Park vicinity)
    origin = Coordinate(latitude=12.9716, longitude=77.5946)
    # Destination: Tech Corridor / Indiranagar
    destination = Coordinate(latitude=12.9850, longitude=77.6100)

    print(f"\n[1] Origin:      {origin.latitude}, {origin.longitude}")
    print(f"    Destination: {destination.latitude}, {destination.longitude}")

    # Build RouteRequest
    request = RouteRequest(
        origin=origin,
        destination=destination,
        alternatives=True,
        profile="driving"
    )

    print("\n[2] Connecting to real routing provider (OSRM)...")
    try:
        provider = OSRMProvider(timeout_seconds=5.0)
        # Test provider call
        routes = provider.get_routes(request)
        print(f"    [+] OSRM returned {len(routes)} route alternative(s).")
    except RoutingError as exc:
        print(f"    [!] Live OSRM provider unavailable ({exc}), falling back to deterministic mock provider for demo.")
        provider = MockRoutingProvider()
        routes = provider.get_routes(request)

    print("\n[3] Initializing SafetyEngineAdapter and loading Member 1 data...")
    adapter = SafetyEngineAdapter(data_dir="data/raw")
    adapter.ensure_data_loaded()
    print("    [+] Member 1 SafetyEngine loaded successfully.")

    print("\n[4] Initializing RoutingService and calculating rankings...")
    service = RoutingService(provider=provider, adapter=adapter)
    result = service.calculate_routes(request, preferred_ranking="balanced")

    print("\n" + "=" * 70)
    print("                   EVALUATED ROUTE COMPARISON                  ")
    print("=" * 70)

    print(f"\nTotal Routes Evaluated: {result['total_routes_found']}")
    print(f"Recommendations:")
    print(f"  * Fastest Route ID:  {result['recommendations']['fastest_route_id']}")
    print(f"  * Safest Route ID:   {result['recommendations']['safest_route_id']}")
    print(f"  * Balanced Route ID: {result['recommendations']['balanced_route_id']}\n")

    print(f"{'Route ID':<10} | {'Dist (km)':<10} | {'Time (min)':<10} | {'Safety Score':<13} | {'Balanced':<10} | {'Tags'}")
    print("-" * 75)
    for r in result["routes"]:
        tags_str = ", ".join(r["tags"])
        print(
            f"{r['route_id']:<10} | "
            f"{r['distance_km']:<10.2f} | "
            f"{r['duration_minutes']:<10.2f} | "
            f"{r['safety_score']:<13.2f} | "
            f"{r['rankings']['balanced_score']:<10.2f} | "
            f"{tags_str}"
        )

    print("\n" + "=" * 70)
    print("Sample Full Evaluated Route Payload (First Route):")
    print(json.dumps(result["routes"][0], indent=2))
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
