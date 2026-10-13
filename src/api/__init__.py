"""
SafeGuard API Package (Member 2).
Exposes HTTP endpoints for route calculation, safety scoring, and multi-criteria route ranking.
"""

from src.api.server import create_server, SafeGuardRequestHandler

__all__ = ["create_server", "SafeGuardRequestHandler"]
