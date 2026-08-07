"""
The "few people" score.

Every sub-component yields 0..1 (1 = you are probably alone). The time profile
modulates exactly those components that depend on leisure behaviour - a farm
track at 7am on a Tuesday is something entirely different from 3pm on a Sunday.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from app.scoring.curves import log_density_score, ramp, weighted_mean

# Land uses whose busyness depends strongly on the day and time.
RECREATION_CATEGORIES = {
    "park", "garden", "playground", "pitch", "sports_centre", "golf_course",
    "recreation_ground", "camp_site", "dog_park", "village_green", "beach",
    "marina", "allotments", "forest",  # forest: Sunday strollers
}

# Land uses with active farming (tractors, field work).
AGRICULTURE_CATEGORIES = {"farmland", "meadow", "orchard", "vineyard", "farmyard", "plant_nursery"}

# How much farming activity depresses the score (at factor 1.0).
AGRICULTURE_PENALTY = 0.12


def _apply_recreation_factor(score: np.ndarray, factor: float) -> np.ndarray:
    """
    Scales the *penalty* (not the score) with the time profile.

    factor = 1.0 -> full effect, factor = 0.0 -> component is neutral (1.0).
    """
    return np.clip(1.0 - factor * (1.0 - np.asarray(score, dtype=float)), 0.0, 1.0)


def landuse_solitude(categories: list[str], config: dict[str, Any], recreation: float, agriculture: float) -> np.ndarray:
    """Rates the land use at the point itself, modulated by the time profile."""
    table = config["landuse_table"]
    fallback = table.get("unknown", {"solitude": 0.6})
    values = np.empty(len(categories), dtype=float)

    for i, category in enumerate(categories):
        entry = table.get(category, fallback)
        value = float(entry.get("solitude", fallback.get("solitude", 0.6)))
        if category in RECREATION_CATEGORIES:
            value = 1.0 - recreation * (1.0 - value)
        if category in AGRICULTURE_CATEGORIES:
            value -= AGRICULTURE_PENALTY * agriculture
        values[i] = value
    return np.clip(values, 0.0, 1.0)


def score_solitude(
    features: dict[str, Any],
    config: dict[str, Any],
    recreation: float,
    agriculture: float,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """
    Computes the overall solitude score and returns the individual components
    alongside it (the detail panel in the frontend needs those).
    """
    comp_cfg: dict[str, dict[str, Any]] = config["solitude"]["components"]
    n = features["n"]
    components: dict[str, np.ndarray] = {}

    def cfg(name: str, key: str, default: float) -> float:
        return float(comp_cfg.get(name, {}).get(key, default))

    # --- Distance based components -----------------------------------------
    components["buildings"] = ramp(
        features["d_building"], cfg("buildings", "critical_m", 80), cfg("buildings", "ideal_m", 500)
    )
    components["residential"] = ramp(
        features["d_settlement"], cfg("residential", "critical_m", 150), cfg("residential", "ideal_m", 900)
    )
    components["roads"] = ramp(
        features["d_road_eff"], cfg("roads", "critical_m", 40), cfg("roads", "ideal_m", 350)
    )
    components["paths"] = ramp(
        features["d_path_eff"], cfg("paths", "critical_m", 30), cfg("paths", "ideal_m", 250)
    )
    components["attractors"] = ramp(
        features["d_attractor_eff"], cfg("attractors", "critical_m", 150), cfg("attractors", "ideal_m", 800)
    )

    # --- Land use -----------------------------------------------------------
    components["landuse"] = landuse_solitude(features["category"], config, recreation, agriculture)

    # --- Strava heatmap -----------------------------------------------------
    # ``features["strava"]`` is 0..1 (1 = heavily ridden or walked trail).
    # This is the core of the requirement: a farm track in the middle of an
    # "empty" field can look unremarkable in OSM while being the local
    # after-work route for every road cyclist around.
    strava_intensity = np.asarray(features.get("strava", np.zeros(n)), dtype=float)
    components["strava"] = np.clip(1.0 - strava_intensity, 0.0, 1.0)

    # ...and how far away the nearest busy route is. The reading above is 0 both
    # at 200 m and at 300 m from a trail; this one separates them.
    components["strava_distance"] = ramp(
        features.get("d_strava", np.full(n, 50_000.0)),
        cfg("strava_distance", "critical_m", 100),
        cfg("strava_distance", "ideal_m", 500),
    )

    # --- Population density (optional) --------------------------------------
    density = np.asarray(features.get("population", np.full(n, np.nan)), dtype=float)
    if np.all(np.isnan(density)):
        components["population"] = np.ones(n)  # neutral, the weight is 0 anyway
    else:
        components["population"] = log_density_score(
            np.nan_to_num(density, nan=0.0), config["population"]["max_density"]
        )

    # --- Apply the time profile to the leisure components -------------------
    for name, spec in comp_cfg.items():
        if spec.get("recreational") and name in components and name != "landuse":
            # landuse was already modulated above, per category.
            components[name] = _apply_recreation_factor(components[name], recreation)

    weights = {name: float(spec.get("weight", 0.0)) for name, spec in comp_cfg.items()}
    total = weighted_mean(components, weights)
    return total, components
