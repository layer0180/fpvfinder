"""
Flyability score.

Guiding ideas:
  * Open terrain is the baseline (line of sight, video link, emergency landing).
  * Trees are a feature, not a bug: a tree line 30-200 m away gives you
    something to fly around. Standing INSIDE the forest is bad though - no
    launch spot, no signal, no overview.
  * Power lines are the single most dangerous obstacle: thin wires are almost
    impossible to see in flight.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from app.scoring.curves import bump, ramp, weighted_mean

# Split inside the openness component:
# 60 % land use type, 40 % actual distance to tree cover.
OPENNESS_LANDUSE_SHARE = 0.6

# Launch spot: taking off directly under trees is unpleasant -> penalty.
TAKEOFF_TREE_CRITICAL_M = 25.0


def _landuse_values(categories: list[str], config: dict[str, Any], key: str, default: float) -> np.ndarray:
    """Reads one column (``openness`` or ``takeoff``) from the land use table."""
    table = config["landuse_table"]
    fallback = table.get("unknown", {})
    values = np.empty(len(categories), dtype=float)
    for i, category in enumerate(categories):
        entry = table.get(category, fallback)
        values[i] = float(entry.get(key, fallback.get(key, default)))
    return np.clip(values, 0.0, 1.0)


def score_flyability(
    features: dict[str, Any],
    config: dict[str, Any],
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Overall score plus the individual flyability components."""
    comp_cfg: dict[str, dict[str, Any]] = config["flyability"]["components"]
    components: dict[str, np.ndarray] = {}

    def cfg(name: str, key: str, default: float) -> float:
        return float(comp_cfg.get(name, {}).get(key, default))

    d_tree = np.asarray(features["d_tree"], dtype=float)

    # --- Openness -----------------------------------------------------------
    landuse_openness = _landuse_values(features["category"], config, "openness", 0.7)
    tree_clearance = ramp(d_tree, 10.0, 120.0)
    components["openness"] = np.clip(
        OPENNESS_LANDUSE_SHARE * landuse_openness + (1.0 - OPENNESS_LANDUSE_SHARE) * tree_clearance,
        0.0,
        1.0,
    )

    # --- Take-off and landing spot ------------------------------------------
    takeoff_base = _landuse_values(features["category"], config, "takeoff", 0.55)
    # Under dense tree cover: at most 50 % of the base suitability.
    takeoff_clearance = 0.5 + 0.5 * ramp(d_tree, 0.0, TAKEOFF_TREE_CRITICAL_M)
    components["takeoff"] = np.clip(takeoff_base * takeoff_clearance, 0.0, 1.0)

    # --- Safety clearances --------------------------------------------------
    components["roads_safety"] = ramp(
        features["d_road_safety_eff"], cfg("roads_safety", "critical_m", 30), cfg("roads_safety", "ideal_m", 150)
    )
    components["railway"] = ramp(
        features["d_railway"], cfg("railway", "critical_m", 50), cfg("railway", "ideal_m", 250)
    )
    components["powerlines"] = ramp(
        features["d_power"], cfg("powerlines", "critical_m", 60), cfg("powerlines", "ideal_m", 250)
    )
    components["buildings"] = ramp(
        features["d_building"], cfg("buildings", "critical_m", 50), cfg("buildings", "ideal_m", 250)
    )

    # --- Nearby structure ----------------------------------------------------
    # Something to fly around within range: a tree line OR a shoreline.
    tree_bonus = bump(
        d_tree,
        cfg("structure", "peak_near_m", 30),
        cfg("structure", "peak_far_m", 200),
        cfg("structure", "fade_m", 600),
    )
    water_bonus = 0.8 * bump(
        np.asarray(features["d_water"], dtype=float),
        cfg("structure", "peak_near_m", 30),
        cfg("structure", "peak_far_m", 200),
        cfg("structure", "fade_m", 600),
    )
    components["structure"] = np.maximum(tree_bonus, water_bonus)

    weights = {name: float(spec.get("weight", 0.0)) for name, spec in comp_cfg.items()}
    total = weighted_mean(components, weights)
    return total, components
