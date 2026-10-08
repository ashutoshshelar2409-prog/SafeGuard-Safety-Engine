"""
Main CLI Script for SafeGuard Safety Engine.
Demonstrates end-to-end data loading, cleaning, route processing, scoring, and output generation.
"""

import json
import os
import sys

# Ensure src package is importable when running script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.services.safety_engine import SafetyEngine


def main():
    print("=" * 60)
    print("        SAFEGUARD — SAFETY ENGINE (MEMBER 1)         ")
    print("=" * 60)

    data_dir = "data/raw"
    sample_route_path = "examples/sample_route.json"

    if not os.path.exists(sample_route_path):
        print(f"Error: Sample route file not found at '{sample_route_path}'")
        sys.exit(1)

    print(f"\n[1] Initializing Safety Engine with data directory: '{data_dir}'...")
    engine = SafetyEngine(data_dir=data_dir)

    print("[2] Loading and validating raw safety datasets...")
    engine.load_data()

    print(f"[3] Analyzing route safety for input file: '{sample_route_path}'...")
    result = engine.analyze_route(sample_route_path)

    print("\n" + "=" * 60)
    print("                  SAFETY SCORE RESULT                ")
    print("=" * 60)
    print(json.dumps(result, indent=2))
    print("=" * 60)
    print(f"\nFINAL SAFETY SCORE: {result['safety_score']} / 100")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
