"""
Combines the partial scores, applies the hard rules and builds the warnings.

LEGAL NOTE: The "hard rules" are a heuristic based on OSM data and the broad
requirements of the EU drone regulation (category A3). They do not replace an
airspace check. Points are therefore never silently dropped - they are flagged
as ``blocked`` and returned with a reason.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from app.scoring.features import FAR_AWAY_M
from app.scoring.labels import CATEGORY_LABELS

# Severity levels used by the frontend.
LEVEL_DANGER = "danger"
LEVEL_WARNING = "warning"
LEVEL_INFO = "info"


def apply_hard_rules(features: dict[str, Any], config: dict[str, Any]) -> np.ndarray:
    """
    Boolean mask: which points violate a hard rule?

    Vectorised, because this has to run for every grid point.
    """
    rules = config["hard_rules"]
    n = features["n"]
    blocked = np.zeros(n, dtype=bool)

    blocked |= features["d_settlement"] < float(rules["min_dist_residential_m"])
    blocked |= features["d_building"] < float(rules["min_dist_building_m"])
    blocked |= features["d_road"] < float(rules["min_dist_road_m"])
    blocked |= features["d_railway"] < float(rules["min_dist_railway_m"])

    if rules.get("block_in_protected_area", True):
        blocked |= np.asarray(features["in_protected"]) & np.asarray(features["protected_strict"])

    if rules.get("block_in_airport_zone", True):
        kinds = features["aerodrome_kind"]
        radius = np.array(
            [
                float(rules.get("heliport_radius_m", 1000)) if k == "heliport"
                else float(rules.get("airport_radius_m", 1500))
                for k in kinds
            ]
        )
        blocked |= features["d_aerodrome"] < radius

    # Manually maintained no-fly zones (data/airspace.geojson)
    zone_severity = features.get("zone_severity")
    if zone_severity is not None:
        blocked |= np.asarray([s == "block" for s in zone_severity], dtype=bool)

    return blocked


def combine_scores(
    solitude: np.ndarray,
    flyability: np.ndarray,
    blocked: np.ndarray,
    config: dict[str, Any],
) -> np.ndarray:
    """Total score, including the markdown applied to blocked points."""
    w_sol = float(config["total"]["solitude_weight"])
    w_fly = float(config["total"]["flyability_weight"])
    total_weight = max(w_sol + w_fly, 1e-9)
    total = (w_sol * solitude + w_fly * flyability) / total_weight
    penalty = float(config["hard_rules"].get("penalty_factor", 0.15))
    return np.clip(np.where(blocked, total * penalty, total), 0.0, 1.0)


def _fmt(distance: float) -> str:
    """Human-readable distance ('820 m' / '1.4 km' / 'not nearby')."""
    if distance >= FAR_AWAY_M * 0.9:
        return "not nearby"
    if distance >= 1000:
        return f"{distance / 1000:.1f} km"
    return f"{distance:.0f} m"


def build_warnings(features: dict[str, Any], i: int, config: dict[str, Any]) -> list[dict[str, str]]:
    """
    Builds the warning list for ONE point.

    Only called for the points actually returned - doing this for 30,000 grid
    points would be needlessly expensive.
    """
    rules = config["hard_rules"]
    warnings: list[dict[str, str]] = []

    def add(level: str, text: str) -> None:
        warnings.append({"level": level, "text": text})

    # --- Legal and safety critical ------------------------------------------
    d_settlement = float(features["d_settlement"][i])
    if d_settlement < float(rules["min_dist_residential_m"]):
        add(
            LEVEL_DANGER,
            f"Only {_fmt(d_settlement)} to the nearest residential or recreational area - "
            f"EU category A3 generally requires {rules['min_dist_residential_m']:.0f} m.",
        )
    elif d_settlement < 300:
        add(LEVEL_WARNING, f"Residential or recreational area {_fmt(d_settlement)} away.")

    if bool(features["in_protected"][i]):
        name = features["protected_name"][i] or "protected area"
        if bool(features["protected_strict"][i]):
            add(
                LEVEL_DANGER,
                f"Inside “{name}” (nature reserve) - taking off there is usually prohibited.",
            )
        else:
            add(LEVEL_WARNING, f"Inside “{name}” (landscape protection) - check the local rules.")

    d_aero = float(features["d_aerodrome"][i])
    kind = features["aerodrome_kind"][i]
    aero_limit = float(rules["heliport_radius_m"] if kind == "heliport" else rules["airport_radius_m"])
    if d_aero < aero_limit:
        name = features["aerodrome_name"][i] or "aerodrome"
        add(LEVEL_DANGER, f"Only {_fmt(d_aero)} to “{name}” - check the control zone!")
    elif d_aero < aero_limit * 2:
        add(LEVEL_INFO, f"Aerodrome “{features['aerodrome_name'][i]}” {_fmt(d_aero)} away.")

    zone_names = features.get("zone_names")
    if zone_names is not None and zone_names[i]:
        severity = features["zone_severity"][i]
        level = LEVEL_DANGER if severity == "block" else (LEVEL_WARNING if severity == "warn" else LEVEL_INFO)
        add(level, f"Custom no-fly zone: {zone_names[i]}")

    # --- Obstacles and flight operations ------------------------------------
    d_power = float(features["d_power"][i])
    if d_power < 100:
        add(LEVEL_DANGER, f"Power line or pylon {_fmt(d_power)} away - wires are barely visible in FPV.")
    elif d_power < 250:
        add(LEVEL_WARNING, f"Power line {_fmt(d_power)} away.")

    d_rail = float(features["d_railway"][i])
    if d_rail < float(rules["min_dist_railway_m"]):
        add(LEVEL_DANGER, f"Railway line {_fmt(d_rail)} away.")
    elif d_rail < 200:
        add(LEVEL_WARNING, f"Railway line {_fmt(d_rail)} away.")

    d_road = float(features["d_road"][i])
    if d_road < float(rules["min_dist_road_m"]):
        add(LEVEL_DANGER, f"Road {_fmt(d_road)} away - too close for safe operation.")
    elif d_road < 80:
        add(LEVEL_WARNING, f"Road {_fmt(d_road)} away.")

    d_building = float(features["d_building"][i])
    if d_building < float(rules["min_dist_building_m"]):
        add(LEVEL_DANGER, f"Building {_fmt(d_building)} away.")

    # --- Practical notes ----------------------------------------------------
    d_tree = float(features["d_tree"][i])
    if d_tree < 20:
        add(LEVEL_WARNING, "Right at or under tree cover - poor launch spot, check your video link.")
    elif d_tree < 200:
        add(LEVEL_INFO, f"Tree line {_fmt(d_tree)} away - good structure to fly around, but mind the obstacles.")

    d_path = float(features["d_path"][i])
    if d_path < 40:
        add(LEVEL_WARNING, f"Path {_fmt(d_path)} away - expect walkers and cyclists.")

    strava = float(np.asarray(features.get("strava", np.zeros(features["n"])))[i])
    if strava >= 0.6:
        add(LEVEL_WARNING, "The Strava heatmap shows a heavily used route here.")
    elif strava >= 0.3:
        add(LEVEL_INFO, "The Strava heatmap shows moderate activity nearby.")

    category = features["category"][i]
    if category == "farmland":
        add(LEVEL_INFO, "Arable field: mind right of way and standing crops (harmless outside the growing season).")
    elif category == "water":
        add(LEVEL_DANGER, "This point sits on water - no launch spot.")
    elif category == "military":
        add(LEVEL_DANGER, "Military area.")

    d_water = float(features["d_water"][i])
    if 0 < d_water < 50 and category != "water":
        add(LEVEL_INFO, f"Water {_fmt(d_water)} away - nice to fly along, but a crash risk.")

    return warnings


def category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, category)
