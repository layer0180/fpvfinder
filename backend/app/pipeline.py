"""
Orchestration of a complete search.

Flow:
    starting point + radius
      -> bounding box
      -> Overpass (tile by tile, cached)
      -> geometry layers
      -> candidate grid
      -> features (distances, land use, protected areas)
      -> external layers (no-fly zones, Strava, population)
      -> scores (solitude, flyability, hard rules)
      -> selection of the best points plus warning texts
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import numpy as np

from app.config import SETTINGS, get_config
from app.models import SearchRequest
from app.scoring.aggregate import apply_hard_rules, build_warnings, category_label, combine_scores
from app.scoring.defaults import deep_merge
from app.scoring.features import FAR_AWAY_M, compute_features
from app.scoring.flyability import score_flyability
from app.scoring.solitude import score_solitude
from app.services.airspace import AirspaceZones
from app.services.grid import adaptive_spacing, build_grid
from app.services.jobs import Job
from app.services.osm_layers import build_layers
from app.services.overpass import OverpassClient
from app.services.population import PopulationRaster
from app.services.spatial import LocalProjection
from app.services.strava import StravaHeatmap, recommended_zoom

# Distances shown in the detail panel: feature key -> output name
EXPORTED_DISTANCES = {
    "d_building": "building",
    "d_building_res": "building_res",
    "d_settlement": "settlement",
    "d_road": "road",
    "d_path": "path",
    "d_railway": "railway",
    "d_power": "power",
    "d_attractor": "attractor",
    "d_tree": "tree",
    "d_water": "water",
    "d_aerodrome": "aerodrome",
    "d_protected": "protected",
    "d_strava": "strava_route",
}


async def run_search(request: SearchRequest, job: Job | None = None) -> dict[str, Any]:
    """Runs a complete search and returns the result as a dictionary."""
    started = time.perf_counter()
    notes: list[str] = []

    # ---- 1. Assemble the configuration -------------------------------------
    config = get_config()
    if request.weights:
        # For this request only - never persisted.
        config = deep_merge(config, request.weights)

    profile_key = request.time_profile or config.get("default_time_profile", "weekend_afternoon")
    profiles = config["time_profiles"]
    if profile_key not in profiles:
        notes.append(f"Unknown time profile '{profile_key}' - falling back to the default.")
        profile_key = config.get("default_time_profile", "weekend_afternoon")
    profile = profiles[profile_key]
    recreation = float(profile.get("recreation", 1.0))
    agriculture = float(profile.get("agriculture", 1.0))

    async def report(fraction: float, message: str) -> None:
        if job is not None:
            job.progress = max(0.0, min(1.0, fraction))
            job.message = message
            job.updated_at = time.time()
        await asyncio.sleep(0)  # yield briefly so status polls get through

    await report(0.02, "Preparing the search area ...")

    # ---- 2. Projection and grid --------------------------------------------
    radius_m = float(request.radius_km) * 1000.0
    proj = LocalProjection(request.lat, request.lon)

    grid_cfg = config["grid"]
    spacing = float(request.spacing_m or grid_cfg["spacing_m"])
    spacing = max(float(grid_cfg["min_spacing_m"]), min(spacing, float(grid_cfg["max_spacing_m"])))
    effective_spacing = adaptive_spacing(radius_m, spacing, int(grid_cfg["max_points"]))
    if effective_spacing > spacing * 1.01:
        notes.append(
            f"Grid spacing raised automatically from {spacing:.0f} m to {effective_spacing:.0f} m "
            f"(point limit {grid_cfg['max_points']})."
        )
    px, py = build_grid(radius_m, effective_spacing)
    n_points = len(px)

    # ---- 3. Fetch the OSM data ---------------------------------------------
    south, west, north, east = proj.bbox_for_radius(radius_m)

    async def overpass_progress(done: int, total: int, message: str) -> None:
        await report(0.05 + 0.50 * (done / max(total, 1)), message)

    client = OverpassClient()
    elements, osm_stats = await client.fetch_area(south, west, north, east, progress=overpass_progress)

    # ---- 4. Build the geometries -------------------------------------------
    await report(0.58, f"Processing {len(elements):,} OSM objects ...")
    layers = await asyncio.to_thread(build_layers, elements, proj, config)

    # ---- 5. Geometric features ---------------------------------------------
    await report(0.66, f"Scoring {n_points:,} candidate points ...")
    features = await asyncio.to_thread(compute_features, layers, px, py)

    # ---- 6. Custom no-fly zones --------------------------------------------
    # Disabled by default. When off the zone_* keys are simply absent, and both
    # apply_hard_rules() and build_warnings() already skip them in that case.
    if SETTINGS.airspace_enabled:
        zones = AirspaceZones(proj)
        features.update(zones.evaluate(px, py))

    # ---- 7. Strava heatmap ---------------------------------------------------
    lat_arr, lon_arr = proj.to_latlon(px, py)
    strava_cfg = dict(config.get("strava", {}))
    if request.use_strava is False:
        strava_cfg["enabled"] = False
    heatmap = StravaHeatmap({**config, "strava": strava_cfg})
    if heatmap.enabled:
        # Match the zoom level to the radius, otherwise the tile count explodes.
        # resolve_zoom() then clamps further to whatever is actually reachable
        # with or without authentication.
        heatmap.zoom = recommended_zoom(radius_m, heatmap.zoom)
        await report(0.74, "Evaluating the Strava heatmap ...")
        strava_sample = await heatmap.sample(lat_arr, lon_arr)
        features["strava"] = strava_sample.intensity
        features["d_strava"] = strava_sample.distance_m
        notes.extend(heatmap.notes)
        if heatmap.last_error:
            notes.append(heatmap.last_error)

    # ---- 8. Population raster ------------------------------------------------
    raster = PopulationRaster(config)
    if raster.available:
        await report(0.80, "Sampling population density ...")
        features["population"] = await asyncio.to_thread(raster.sample, lat_arr, lon_arr)
        raster.close()
    elif raster.error:
        notes.append(f"Population raster: {raster.error}")

    # ---- 9. Scoring ----------------------------------------------------------
    await report(0.86, "Computing scores ...")
    solitude, solitude_components = score_solitude(features, config, recreation, agriculture)
    flyability, flyability_components = score_flyability(features, config)
    blocked = apply_hard_rules(features, config)
    total = combine_scores(solitude, flyability, blocked, config)

    # ---- 10. Select the points to return ------------------------------------
    await report(0.93, "Selecting the best locations ...")
    max_results = int(request.max_results or grid_cfg["max_results"])
    selected = _select_points(px, py, total, effective_spacing, max_results)

    points = _serialize_points(
        selected, lat_arr, lon_arr, total, solitude, flyability, blocked,
        solitude_components, flyability_components, features, config,
    )

    duration = time.perf_counter() - started
    await report(1.0, "Done")

    return {
        "center": {"lat": request.lat, "lon": request.lon},
        "radius_km": request.radius_km,
        "time_profile": profile_key,
        "time_profile_label": profile.get("label", profile_key),
        "points": points,
        "notes": notes,
        "stats": {
            "grid_points": n_points,
            "returned_points": len(points),
            "spacing_m": round(effective_spacing, 1),
            "radius_km": request.radius_km,
            "tiles_total": osm_stats["tiles_total"],
            "tiles_cached": osm_stats["tiles_cached"],
            "tiles_fetched": osm_stats["tiles_fetched"],
            "osm_elements": len(elements),
            "layers": layers.summary(),
            "duration_s": round(duration, 2),
            "score_min": float(np.min(total)) if n_points else 0.0,
            "score_max": float(np.max(total)) if n_points else 0.0,
            "score_mean": float(np.mean(total)) if n_points else 0.0,
            "blocked_share": float(np.mean(blocked)) if n_points else 0.0,
        },
    }


def _select_points(
    px: np.ndarray, py: np.ndarray, score: np.ndarray, spacing: float, max_results: int
) -> np.ndarray:
    """
    Selects the points to return, spread evenly across the area.

    Plain "top N by score" would cause two problems:
      1. All hits cluster inside the single largest contiguous field.
      2. The map would be uniformly green, because the poor areas never get
         returned in the first place - which would render the colour scale and
         the heatmap view meaningless.

    So instead: divide the search area into coarse cells and keep the best point
    from EVERY cell. The cell size is chosen so the cell count lands near
    ``max_results``. The result is even coverage across the whole radius and the
    full score range.
    """
    n = len(score)
    order = np.argsort(-score)
    if n <= max_results:
        return order

    factor = max(1, int(np.ceil(np.sqrt(n / max(max_results, 1)))))
    cell = spacing * factor
    keys = np.floor(px / cell).astype(np.int64) * 1_000_003 + np.floor(py / cell).astype(np.int64)

    # Walk in descending score order -> the first hit per cell wins.
    seen: set[int] = set()
    kept: list[int] = []
    for idx in order:
        key = int(keys[idx])
        if key in seen:
            continue
        seen.add(key)
        kept.append(int(idx))
    return np.asarray(kept[:max_results], dtype=int)


def _serialize_points(
    selected: np.ndarray,
    lat_arr: np.ndarray,
    lon_arr: np.ndarray,
    total: np.ndarray,
    solitude: np.ndarray,
    flyability: np.ndarray,
    blocked: np.ndarray,
    solitude_components: dict[str, np.ndarray],
    flyability_components: dict[str, np.ndarray],
    features: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Builds the JSON structure for the selected points."""
    points: list[dict[str, Any]] = []
    population = np.asarray(features.get("population", np.full(features["n"], np.nan)), dtype=float)
    strava = np.asarray(features.get("strava", np.zeros(features["n"])), dtype=float)

    for idx in selected:
        i = int(idx)
        distances = {
            out_key: round(float(min(features[feat_key][i], FAR_AWAY_M)), 1)
            for feat_key, out_key in EXPORTED_DISTANCES.items()
        }
        pop_value = float(population[i]) if not np.isnan(population[i]) else None
        category = features["category"][i]

        points.append(
            {
                "id": i,
                "lat": round(float(lat_arr[i]), 6),
                "lon": round(float(lon_arr[i]), 6),
                "score": round(float(total[i]), 4),
                "solitude": round(float(solitude[i]), 4),
                "flyability": round(float(flyability[i]), 4),
                "blocked": bool(blocked[i]),
                "category": category,
                "category_label": category_label(category),
                "area_name": features["area_name"][i],
                "distances": distances,
                "components": {
                    "solitude": {k: round(float(v[i]), 3) for k, v in solitude_components.items()},
                    "flyability": {k: round(float(v[i]), 3) for k, v in flyability_components.items()},
                },
                "warnings": build_warnings(features, i, config),
                "strava": round(float(strava[i]), 3),
                "population": round(pop_value, 1) if pop_value is not None else None,
            }
        )
    return points
