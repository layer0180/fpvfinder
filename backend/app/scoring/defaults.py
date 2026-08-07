"""
Default scoring configuration.

IMPORTANT: This file is only the *fallback*. The values actually in use live in
``backend/config/weights.json`` and are deep-merged on top of these defaults
(see ``app/config.py``). Any key missing from the JSON automatically falls back
to the value defined here.

All distances are in metres, all scores and weights are normalised to 0..1.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Land use table
# ---------------------------------------------------------------------------
# Three values per OSM category (see services/osm_layers.py -> classify_area):
#   solitude : How deserted is this kind of area, typically? (1 = empty)
#   openness : How unobstructed is the airspace above it?    (1 = wide open)
#   takeoff  : How well can you take off and land there?     (1 = ideal)
#
# This table is the single most effective knob for tuning the app to your area.
LANDUSE_TABLE: dict[str, dict[str, float]] = {
    # --- Agriculture: usually empty, very open ----------------------------
    "farmland":         {"solitude": 0.90, "openness": 0.95, "takeoff": 0.70},
    "farmyard":         {"solitude": 0.35, "openness": 0.55, "takeoff": 0.40},
    "meadow":           {"solitude": 0.88, "openness": 0.95, "takeoff": 0.90},
    "grass":            {"solitude": 0.70, "openness": 0.92, "takeoff": 0.90},
    "grassland":        {"solitude": 0.88, "openness": 0.95, "takeoff": 0.85},
    "orchard":          {"solitude": 0.80, "openness": 0.45, "takeoff": 0.45},
    "vineyard":         {"solitude": 0.72, "openness": 0.60, "takeoff": 0.45},
    "greenhouse":       {"solitude": 0.40, "openness": 0.30, "takeoff": 0.20},
    "plant_nursery":    {"solitude": 0.55, "openness": 0.60, "takeoff": 0.45},

    # --- Woodland: deserted, but full of obstacles ------------------------
    "forest":           {"solitude": 0.85, "openness": 0.15, "takeoff": 0.20},
    "scrub":            {"solitude": 0.85, "openness": 0.55, "takeoff": 0.40},
    "heath":            {"solitude": 0.85, "openness": 0.90, "takeoff": 0.70},
    "wetland":          {"solitude": 0.85, "openness": 0.80, "takeoff": 0.15},
    "moor":             {"solitude": 0.88, "openness": 0.85, "takeoff": 0.20},

    # --- Water: no launch spot, a crash means total loss -------------------
    "water":            {"solitude": 0.70, "openness": 0.95, "takeoff": 0.00},
    "beach":            {"solitude": 0.35, "openness": 0.90, "takeoff": 0.70},

    # --- Derelict and industrial land -------------------------------------
    "brownfield":       {"solitude": 0.75, "openness": 0.80, "takeoff": 0.65},
    "greenfield":       {"solitude": 0.80, "openness": 0.90, "takeoff": 0.75},
    "construction":     {"solitude": 0.45, "openness": 0.70, "takeoff": 0.35},
    "quarry":           {"solitude": 0.60, "openness": 0.85, "takeoff": 0.55},
    "landfill":         {"solitude": 0.65, "openness": 0.85, "takeoff": 0.50},
    "industrial":       {"solitude": 0.30, "openness": 0.45, "takeoff": 0.30},
    "commercial":       {"solitude": 0.12, "openness": 0.45, "takeoff": 0.25},
    "retail":           {"solitude": 0.08, "openness": 0.40, "takeoff": 0.20},
    "railway_area":     {"solitude": 0.30, "openness": 0.55, "takeoff": 0.10},
    "military":         {"solitude": 0.50, "openness": 0.70, "takeoff": 0.10},

    # --- Built-up areas: effectively disqualifying -------------------------
    "residential":      {"solitude": 0.03, "openness": 0.30, "takeoff": 0.10},
    "village_green":    {"solitude": 0.20, "openness": 0.80, "takeoff": 0.70},
    "school_grounds":   {"solitude": 0.10, "openness": 0.55, "takeoff": 0.20},
    "cemetery":         {"solitude": 0.25, "openness": 0.55, "takeoff": 0.15},
    "religious":        {"solitude": 0.20, "openness": 0.50, "takeoff": 0.15},

    # --- Recreation: busy during the day and at weekends -------------------
    "park":             {"solitude": 0.10, "openness": 0.70, "takeoff": 0.55},
    "garden":           {"solitude": 0.20, "openness": 0.55, "takeoff": 0.30},
    "allotments":       {"solitude": 0.15, "openness": 0.60, "takeoff": 0.25},
    "playground":       {"solitude": 0.02, "openness": 0.70, "takeoff": 0.30},
    "pitch":            {"solitude": 0.15, "openness": 0.85, "takeoff": 0.80},
    "sports_centre":    {"solitude": 0.10, "openness": 0.70, "takeoff": 0.50},
    "golf_course":      {"solitude": 0.18, "openness": 0.85, "takeoff": 0.75},
    "recreation_ground": {"solitude": 0.20, "openness": 0.85, "takeoff": 0.80},
    "camp_site":        {"solitude": 0.08, "openness": 0.60, "takeoff": 0.35},
    "dog_park":         {"solitude": 0.05, "openness": 0.75, "takeoff": 0.50},
    "marina":           {"solitude": 0.15, "openness": 0.70, "takeoff": 0.10},

    # --- Protected areas: legally sensitive (see hard_rules) ---------------
    "nature_reserve":   {"solitude": 0.60, "openness": 0.60, "takeoff": 0.35},
    "protected_area":   {"solitude": 0.65, "openness": 0.65, "takeoff": 0.40},
    "national_park":    {"solitude": 0.60, "openness": 0.60, "takeoff": 0.30},

    # --- Aviation ----------------------------------------------------------
    "aerodrome":        {"solitude": 0.30, "openness": 0.95, "takeoff": 0.60},

    # --- Fallback when no area was found -----------------------------------
    # (Usually unmapped countryside, so a mildly positive default.)
    "unknown":          {"solitude": 0.65, "openness": 0.70, "takeoff": 0.55},
}


# ---------------------------------------------------------------------------
# Road classes
# ---------------------------------------------------------------------------
# "weight" = how strongly this road should push the solitude score down (1 = max).
# "safety" = how relevant it is for safety clearance (crashing onto a carriageway).
ROAD_CLASSES: dict[str, dict[str, float]] = {
    "motorway":      {"weight": 1.00, "safety": 1.00},
    "trunk":         {"weight": 0.95, "safety": 1.00},
    "primary":       {"weight": 0.85, "safety": 0.95},
    "secondary":     {"weight": 0.70, "safety": 0.85},
    "tertiary":      {"weight": 0.55, "safety": 0.70},
    "unclassified":  {"weight": 0.35, "safety": 0.50},
    "residential":   {"weight": 0.60, "safety": 0.60},
    "living_street": {"weight": 0.60, "safety": 0.50},
    "service":       {"weight": 0.25, "safety": 0.35},
}

# Ways without meaningful motor traffic -> these indicate recreational use.
PATH_CLASSES: dict[str, float] = {
    "track":     0.45,   # farm track: farmers, the occasional walker
    "path":      0.75,
    "footway":   0.90,
    "cycleway":  0.85,
    "bridleway": 0.55,
    "steps":     0.60,
    "pedestrian": 1.00,
}

# Point POIs that draw people in. The value is the strength of attraction.
ATTRACTOR_WEIGHTS: dict[str, float] = {
    "playground":      1.00,
    "picnic_site":     0.85,
    "picnic_table":    0.70,
    "viewpoint":       0.90,
    "camp_site":       0.85,
    "attraction":      0.95,
    "bench":           0.35,
    "shelter":         0.55,
    "firepit":         0.70,
    "fitness_station": 0.70,
    "restaurant":      0.85,
    "cafe":            0.80,
    "biergarten":      0.95,
    "fast_food":       0.70,
    "parking":         0.80,   # car park = starting point for walkers
    "school":          0.90,
    "kindergarten":    0.90,
    "hospital":        0.85,
    "marketplace":     0.85,
    "bus_stop":        0.45,
    "information":     0.60,
    "hunting_stand":   0.30,   # hunters: rare, but a source of conflict
}


# ---------------------------------------------------------------------------
# Time profiles
# ---------------------------------------------------------------------------
# These modulate the "leisure driven" score components (paths, POIs, Strava,
# recreational land use). 1.0 = full penalty, 0.0 = no penalty at all.
# ``agriculture`` additionally modulates farmland (tractors, field work).
TIME_PROFILES: dict[str, dict[str, Any]] = {
    "weekday_morning":   {"label": "Weekday morning", "recreation": 0.45, "agriculture": 1.00},
    "weekday_afternoon": {"label": "Weekday afternoon", "recreation": 0.70, "agriculture": 1.00},
    "weekday_evening":   {"label": "Weekday evening (golden hour)", "recreation": 0.85, "agriculture": 0.70},
    "weekend_morning":   {"label": "Weekend morning", "recreation": 0.90, "agriculture": 0.40},
    "weekend_afternoon": {"label": "Weekend afternoon", "recreation": 1.00, "agriculture": 0.35},
    "weekend_evening":   {"label": "Weekend evening", "recreation": 0.80, "agriculture": 0.30},
    "early_morning":     {"label": "Very early / sunrise", "recreation": 0.25, "agriculture": 0.60},
}


# ---------------------------------------------------------------------------
# Complete default configuration
# ---------------------------------------------------------------------------
DEFAULT_CONFIG: dict[str, Any] = {
    "version": 1,

    # --- Grid generation ---------------------------------------------------
    "grid": {
        "spacing_m": 150,        # grid spacing (100-200 m is a sensible range)
        "min_spacing_m": 50,
        "max_spacing_m": 500,
        "max_points": 30000,     # cap; beyond this the spacing is widened automatically
        "max_results": 600,      # this many points are sent to the frontend
    },

    # --- Search parameters -------------------------------------------------
    "search": {
        "default_radius_km": 5.0,
        "max_radius_km": 20.0,
    },

    # --- Balance between the two main scores -------------------------------
    "total": {
        "solitude_weight": 0.55,
        "flyability_weight": 0.45,
    },

    # --- "Few people" score ------------------------------------------------
    # Every component yields 0..1 (1 = good, i.e. deserted).
    # ``critical_m``: at or below this the score is 0.
    # ``ideal_m``: at or above this the score is 1.
    # ``recreational``: gets modulated by the time profile factor.
    "solitude": {
        "components": {
            "buildings":   {"weight": 0.20, "critical_m": 80,  "ideal_m": 500, "recreational": False},
            "residential": {"weight": 0.20, "critical_m": 150, "ideal_m": 900, "recreational": False},
            "roads":       {"weight": 0.12, "critical_m": 40,  "ideal_m": 350, "recreational": False},
            "paths":       {"weight": 0.16, "critical_m": 30,  "ideal_m": 250, "recreational": True},
            "attractors":  {"weight": 0.12, "critical_m": 150, "ideal_m": 800, "recreational": True},
            "landuse":     {"weight": 0.10, "recreational": True},
            "strava":      {"weight": 0.08, "recreational": True},
            # Distance to the nearest route people actually use. Separate
            # from the reading above: standing ON a busy trail and standing
            # 200 m from one are different problems, and only this one can
            # tell 200 m apart from 300 m.
            "strava_distance": {"weight": 0.10, "critical_m": 100, "ideal_m": 500,
                                "recreational": True},
            "population":  {"weight": 0.00, "recreational": False},
        },
    },

    # --- Flyability score --------------------------------------------------
    "flyability": {
        "components": {
            # Open terrain (from land use plus distance to tree cover)
            "openness":     {"weight": 0.26},
            # Suitability as a take-off and landing spot
            "takeoff":      {"weight": 0.16},
            # Safety clearance from roads (weighted by class)
            "roads_safety": {"weight": 0.14, "critical_m": 30, "ideal_m": 150},
            # Safety clearance from railway lines
            "railway":      {"weight": 0.10, "critical_m": 50, "ideal_m": 250},
            # Power lines: the single most dangerous obstacle in FPV
            "powerlines":   {"weight": 0.16, "critical_m": 60, "ideal_m": 250},
            # Distance to buildings (crash risk, other people's property)
            "buildings":    {"weight": 0.10, "critical_m": 50, "ideal_m": 250},
            # Bonus for structure nearby to fly around: a tree line or shoreline
            "structure":    {"weight": 0.08, "peak_near_m": 30, "peak_far_m": 200, "fade_m": 600},
        },
    },

    # --- Land use and class tables ----------------------------------------
    "landuse_table": LANDUSE_TABLE,
    "road_classes": ROAD_CLASSES,
    "path_classes": PATH_CLASSES,
    "attractor_weights": ATTRACTOR_WEIGHTS,
    "time_profiles": TIME_PROFILES,
    "default_time_profile": "weekend_afternoon",

    # --- Hard rules --------------------------------------------------------
    # Points violating these are flagged as ``blocked`` and their total score is
    # multiplied by ``penalty_factor``. They are deliberately not removed, so
    # that the map still shows *why* an area is unusable.
    #
    # NOTE: The 150 m figure follows EU category A3 (clearance from residential,
    # commercial, industrial and recreational areas). This does NOT replace your
    # own legal check - see the disclaimer in the UI.
    "hard_rules": {
        "min_dist_residential_m": 150,
        "min_dist_building_m": 50,
        "min_dist_road_m": 25,
        "min_dist_railway_m": 50,
        "block_in_protected_area": True,
        "block_in_airport_zone": True,
        "airport_radius_m": 1500,
        "heliport_radius_m": 1000,
        "penalty_factor": 0.15,
    },

    # --- Strava heatmap ----------------------------------------------------
    "strava": {
        # Requires NO login: the public endpoint serves tiles up to zoom 12
        # (~25 m/pixel at 48 degrees north).
        "enabled": True,
        # Zoom 12 is the maximum without a login. With valid cookies in
        # STRAVA_HEATMAP_COOKIES you can raise this to 13 or 14 - if the
        # authentication fails, the backend clamps back to 12 automatically.
        "zoom": 12,
        # Radius in pixels over which the maximum is taken.
        # At zoom 12 one pixel is ~25 m, so 1 gives a 75 m window.
        "sample_radius_px": 1,
        # Anything below this opacity counts as noise and is set to 0; the rest
        # is rescaled to 0..1. Strava already draws a SINGLE activity at an
        # alpha of ~0.2-0.4, and in rural tiles about a third of all pixels sit
        # on exactly that plateau. Without this floor virtually every point
        # would be penalised (measured: only 10 % stayed at 0, with a floor of
        # 0.35 it is 56 %).
        "noise_floor": 0.35,
        "intensity_gamma": 1.0,    # <1 lifts faint traces, >1 damps them
        # From this intensity upwards a pixel counts as "a route people use"
        # for the distance measurement. Measured against the palette: ~0.4
        # is the dark red that means regular use, rather than the faint
        # trace left by a single passage.
        "activity_threshold": 0.4,
        # How far to look for one. Keep it at or above the ideal_m of the
        # strava_distance component - searching further only costs tiles.
        "search_radius_m": 800.0,
        "activity": "all",         # all | ride | run | winter | water
        "color": "hot",            # hot | blue | purple | gray | bluered | mobileblue
    },

    # --- Population density raster (optional) ------------------------------
    "population": {
        "enabled": False,          # switched on automatically if the file and rasterio exist
        "raster_path": "data/population.tif",
        # Inhabitants per km^2 at which the score reaches 0 (evaluated on a log scale)
        "max_density": 1500.0,
        # Area of one raster cell in km^2 - needed because GHS-POP reports
        # inhabitants PER CELL, not per km^2 (100 m grid = 0.01, 1 km grid = 1.0).
        "cell_area_km2": 0.01,
    },

    # --- Map display (defaults for the frontend) ---------------------------
    "display": {
        "score_good": 0.70,        # >= renders green
        "score_medium": 0.50,      # >= renders yellow
        "hide_blocked_default": True,
    },
}


def deep_merge(base: dict, override: dict) -> dict:
    """Recursive merge: ``override`` wins, missing keys come from ``base``."""
    out = dict(base)
    for key, value in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out
