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
from app.services.osm_layers import STRICT_KINDS

# Severity levels used by the frontend.
LEVEL_DANGER = "danger"
LEVEL_WARNING = "warning"
LEVEL_INFO = "info"

# Warning code per kind of strictly protected area. "protected_strict" keeps
# its old meaning (nature reserve), so stored results still read right.
PROTECTED_CODES = {
    "nature_reserve": "protected_strict",
    "national_park": "protected_national_park",
    "bird": "protected_bird",
    "ffh": "protected_ffh",
    "natura2000": "protected_natura2000",
}
STRICT_PROTECTED_CODES = frozenset(PROTECTED_CODES.values())


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
    warnings: list[dict[str, Any]] = []

    def add(level: str, code: str, text: str, **params: Any) -> None:
        # ``code`` + ``params`` are what the frontend translates; ``text`` is
        # the English fallback for API users. Distances are rounded metres.
        clean = {k: (round(v) if isinstance(v, float) else v) for k, v in params.items()}
        warnings.append({"level": level, "code": code, "params": clean, "text": text})

    # --- Legal and safety critical ------------------------------------------
    d_settlement = float(features["d_settlement"][i])
    if d_settlement < float(rules["min_dist_residential_m"]):
        add(
            LEVEL_DANGER,
            "residential_too_close",
            f"Only {_fmt(d_settlement)} to the nearest residential or recreational area - "
            f"EU category A3 generally requires {rules['min_dist_residential_m']:.0f} m.",
            distance_m=d_settlement,
            limit_m=float(rules["min_dist_residential_m"]),
        )
    elif d_settlement < 300:
        add(LEVEL_WARNING, "residential_near", f"Residential or recreational area {_fmt(d_settlement)} away.", distance_m=d_settlement)

    # One warning per kind of area, so a point in a nature reserve that is
    # also a bird protection area names both. Names are empty when OSM has
    # none; the translated texts have a variant for that.
    landscape_named = False
    for kind, name in features["protected_hits"][i]:
        label = name or "protected area"
        if kind in STRICT_KINDS:
            add(
                LEVEL_DANGER,
                PROTECTED_CODES[kind],
                f"Inside “{label}” ({kind.replace('_', ' ')}) - leisure drone flights are prohibited there.",
                name=name,
            )
        elif not landscape_named:
            landscape_named = True
            add(LEVEL_WARNING, "protected_landscape", f"Inside “{label}” (landscape protection) - check the local rules.", name=name)

    d_aero = float(features["d_aerodrome"][i])
    kind = features["aerodrome_kind"][i]
    aero_limit = float(rules["heliport_radius_m"] if kind == "heliport" else rules["airport_radius_m"])
    if d_aero < aero_limit:
        name = features["aerodrome_name"][i]
        add(LEVEL_DANGER, "aerodrome_too_close", f"Only {_fmt(d_aero)} to “{name or 'an aerodrome'}” - check the control zone!", name=name, distance_m=d_aero)
    elif d_aero < aero_limit * 2:
        add(
            LEVEL_INFO,
            "aerodrome_near",
            f"Aerodrome “{features['aerodrome_name'][i] or '?'}” {_fmt(d_aero)} away.",
            name=features["aerodrome_name"][i],
            distance_m=d_aero,
        )

    zone_names = features.get("zone_names")
    if zone_names is not None and zone_names[i]:
        severity = features["zone_severity"][i]
        level = LEVEL_DANGER if severity == "block" else (LEVEL_WARNING if severity == "warn" else LEVEL_INFO)
        add(level, "custom_zone", f"Custom no-fly zone: {zone_names[i]}", name=zone_names[i])

    # --- Obstacles and flight operations ------------------------------------
    d_power = float(features["d_power"][i])
    if d_power < 100:
        add(LEVEL_DANGER, "power_too_close", f"Power line or pylon {_fmt(d_power)} away - wires are barely visible in FPV.", distance_m=d_power)
    elif d_power < 250:
        add(LEVEL_WARNING, "power_near", f"Power line {_fmt(d_power)} away.", distance_m=d_power)

    d_rail = float(features["d_railway"][i])
    if d_rail < float(rules["min_dist_railway_m"]):
        add(LEVEL_DANGER, "railway_too_close", f"Railway line {_fmt(d_rail)} away.", distance_m=d_rail)
    elif d_rail < 200:
        add(LEVEL_WARNING, "railway_near", f"Railway line {_fmt(d_rail)} away.", distance_m=d_rail)

    d_road = float(features["d_road"][i])
    if d_road < float(rules["min_dist_road_m"]):
        add(LEVEL_DANGER, "road_too_close", f"Road {_fmt(d_road)} away - too close for safe operation.", distance_m=d_road)
    elif d_road < 80:
        add(LEVEL_WARNING, "road_near", f"Road {_fmt(d_road)} away.", distance_m=d_road)

    d_building = float(features["d_building"][i])
    if d_building < float(rules["min_dist_building_m"]):
        add(LEVEL_DANGER, "building_too_close", f"Building {_fmt(d_building)} away.", distance_m=d_building)

    # --- Practical notes ----------------------------------------------------
    d_tree = float(features["d_tree"][i])
    if d_tree < 20:
        add(LEVEL_WARNING, "under_trees", "Right at or under tree cover - poor launch spot, check your video link.")
    elif d_tree < 200:
        add(
            LEVEL_INFO,
            "tree_line_near",
            f"Tree line {_fmt(d_tree)} away - good structure to fly around, but mind the obstacles.",
            distance_m=d_tree,
        )

    d_path = float(features["d_path"][i])
    if d_path < 40:
        add(LEVEL_WARNING, "path_near", f"Path {_fmt(d_path)} away - expect walkers and cyclists.", distance_m=d_path)

    strava = float(np.asarray(features.get("strava", np.zeros(features["n"])))[i])
    if strava >= 0.6:
        add(LEVEL_WARNING, "strava_busy", "The Strava heatmap shows a heavily used route here.")
    elif strava >= 0.3:
        add(LEVEL_INFO, "strava_moderate", "The Strava heatmap shows moderate activity nearby.")

    category = features["category"][i]
    if category == "farmland":
        add(
            LEVEL_INFO,
            "farmland",
            "Arable field: mind right of way and standing crops (harmless outside the growing season).",
        )
    elif category == "water":
        add(LEVEL_DANGER, "on_water", "This point sits on water - no launch spot.")
    elif category == "military":
        add(LEVEL_DANGER, "military", "Military area.")

    d_water = float(features["d_water"][i])
    if 0 < d_water < 50 and category != "water":
        add(LEVEL_INFO, "water_near", f"Water {_fmt(d_water)} away - nice to fly along, but a crash risk.", distance_m=d_water)

    return warnings


def category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, category)


# (component group, component, reason code, distance feature or None)
# Each line turns a strong score component into a plain statement the user can
# check on the ground - "nearest path 420 m away" says more than "solitude 83".
_REASONS: list[tuple[str, str, str, str | None]] = [
    ("solitude", "residential", "far_from_settlement", "d_settlement"),
    ("solitude", "buildings", "far_from_buildings", "d_building"),
    ("solitude", "roads", "far_from_roads", "d_road"),
    ("solitude", "paths", "far_from_paths", "d_path"),
    ("solitude", "attractors", "no_crowd_magnets", "d_attractor"),
    ("solitude", "landuse", "quiet_landuse", None),
    ("solitude", "routes", "off_popular_routes", "d_route"),
    ("solitude", "strava", "little_strava_activity", None),
    ("flyability", "openness", "open_terrain", "d_tree"),
    ("flyability", "takeoff", "good_takeoff", None),
    ("flyability", "structure", "structure_nearby", None),
    ("flyability", "powerlines", "no_power_lines", "d_power"),
]

REASON_MIN_VALUE = 0.8
MAX_REASONS = 3


def build_reasons(
    features: dict[str, Any],
    i: int,
    components: dict[str, dict[str, np.ndarray]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    The strongest arguments FOR one point: components scoring at least
    ``REASON_MIN_VALUE``, ranked by how much they actually weigh in the total.
    """
    group_weight = {
        "solitude": float(config["total"]["solitude_weight"]),
        "flyability": float(config["total"]["flyability_weight"]),
    }
    candidates: list[tuple[float, dict[str, Any]]] = []
    for group, name, code, distance_key in _REASONS:
        values = components.get(group, {}).get(name)
        if values is None:
            continue
        value = float(values[i])
        weight = float(config[group]["components"].get(name, {}).get("weight", 0.0))
        if value < REASON_MIN_VALUE or weight <= 0.0:
            continue
        params: dict[str, Any] = {}
        if distance_key and distance_key in features:
            distance = float(features[distance_key][i])
            # "No power line within 50 km" is noise; only quote real distances.
            if distance < FAR_AWAY_M * 0.9:
                params["distance_m"] = round(distance)
        if name in ("landuse", "takeoff"):
            params["category"] = features["category"][i]
        if name == "structure":
            tree, water = float(features["d_tree"][i]), float(features["d_water"][i])
            params["kind"] = "water" if water < tree else "trees"
            params["distance_m"] = round(min(tree, water))
        candidates.append((value * weight * group_weight[group], {"code": code, "params": params}))

    candidates.sort(key=lambda c: -c[0])
    return [reason for _, reason in candidates[:MAX_REASONS]]
