"""Utilities for Leafmap notebooks and apps."""

from .data import filter_by_leaves, find_overlaps, load_leaf_metadata, load_usage_data
from .map import render_leaf_map


def __getattr__(name: str):
    if name == "build_map_app":
        from .widgets import build_map_app

        return build_map_app

    offline_map_exports = {
        "boundary_match_summary",
        "ensure_natural_earth_admin1",
        "ensure_natural_earth_countries",
        "load_admin1_boundaries",
        "load_country_boundaries",
        "render_offline_vector_map",
    }
    if name in offline_map_exports:
        from . import offline_map

        return getattr(offline_map, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "build_map_app",
    "filter_by_leaves",
    "find_overlaps",
    "boundary_match_summary",
    "ensure_natural_earth_admin1",
    "ensure_natural_earth_countries",
    "load_admin1_boundaries",
    "load_country_boundaries",
    "load_leaf_metadata",
    "load_usage_data",
    "render_offline_vector_map",
    "render_leaf_map",
]
