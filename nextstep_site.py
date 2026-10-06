"""Compatibility hook: replace the retired NextStep planner with MarginRadar."""
from marginradar_site import attach_marginradar


def attach_nextstep(app):
    """Keep the existing startup hook; only the served product changes."""
    return attach_marginradar(app)
