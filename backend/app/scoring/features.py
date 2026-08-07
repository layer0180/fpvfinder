"""
Computes the raw geometric data for EVERY candidate point
(distances, land use category, protected area membership).

Performance note: everything runs vectorised over shapely 2 STRtrees. For
30,000 points against ~100,000 geometries this takes a few seconds depending on
the area - looping over points would be orders of magnitude slower and should
be avoided here.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np
from shapely import STRtree
from shapely import points as shapely_points
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

from app.services.osm_layers import OsmLayers

# Large stand-in value for "this kind of object does not exist around here".
# Deliberately finite (not inf) so ramps and JSON serialisation can handle it.
FAR_AWAY_M = 50_000.0

# Categories counting as "built-up area" in the sense of EU category A3.
BUILT_UP_CATEGORIES = {
    "residential", "commercial", "retail", "industrial", "farmyard",
    "school_grounds", "religious", "railway_area",
}

# Categories counting as "recreational area" (also relevant for A3).
RECREATION_CATEGORIES = {
    "park", "garden", "allotments", "playground", "pitch", "sports_centre",
    "golf_course", "recreation_ground", "camp_site", "dog_park", "marina",
    "village_green", "cemetery", "beach",
}


# ---------------------------------------------------------------------------
# STRtree helpers
# ---------------------------------------------------------------------------
def _nearest_distance(geoms: list[BaseGeometry], query_points, n_points: int) -> tuple[np.ndarray, np.ndarray]:
    """
    Distance from each point to the nearest geometry (0 if the point is inside).

    Returns: (distances in metres, index of the nearest geometry or -1).
    """
    distances = np.full(n_points, FAR_AWAY_M, dtype=float)
    indices = np.full(n_points, -1, dtype=int)
    if not geoms:
        return distances, indices

    tree = STRtree(geoms)
    result = tree.query_nearest(query_points, all_matches=False, return_distance=True)
    idx, dist = result
    idx = np.asarray(idx)
    dist = np.asarray(dist, dtype=float)

    if idx.ndim == 2:
        # For array input shapely returns [[input indices], [tree indices]]
        input_idx, tree_idx = idx[0], idx[1]
    else:
        input_idx, tree_idx = np.arange(len(dist)), idx

    distances[input_idx] = dist
    indices[input_idx] = tree_idx
    return distances, indices


def _weighted_nearest(
    geoms: list[BaseGeometry],
    weights: list[float],
    query_points,
    n_points: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Distance to the nearest geometry - both raw AND weighted.

    The "effective distance" is ``distance / weight``: a motorway (weight 1.0)
    at 300 m then carries the same weight as a residential street (weight 0.25)
    at 75 m. This folds traffic volume into the score without computing per
    object - we group by weight instead (a handful of groups at most).

    Returns: (raw distance, effective distance, index of the raw nearest).
    """
    raw = np.full(n_points, FAR_AWAY_M, dtype=float)
    effective = np.full(n_points, FAR_AWAY_M, dtype=float)
    nearest_idx = np.full(n_points, -1, dtype=int)
    if not geoms:
        return raw, effective, nearest_idx

    groups: dict[float, list[int]] = defaultdict(list)
    for i, w in enumerate(weights):
        groups[round(float(w), 2)].append(i)

    for weight, member_indices in groups.items():
        subset = [geoms[i] for i in member_indices]
        dist, local_idx = _nearest_distance(subset, query_points, n_points)
        # Raw distance: simply the minimum across all groups.
        closer = dist < raw
        raw[closer] = dist[closer]
        global_idx = np.asarray(member_indices, dtype=int)
        valid = closer & (local_idx >= 0)
        nearest_idx[valid] = global_idx[local_idx[valid]]
        # Minimise the effective distance separately (different minimum than raw!).
        eff = dist / max(weight, 0.05)
        effective = np.minimum(effective, eff)

    return raw, np.clip(effective, 0.0, FAR_AWAY_M), nearest_idx


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def compute_features(layers: OsmLayers, px: np.ndarray, py: np.ndarray) -> dict[str, Any]:
    """
    Builds the feature dictionary for all candidate points.

    Every distance array has length len(px) and is measured in metres.
    """
    n = len(px)
    query_points = shapely_points(px, py)
    features: dict[str, Any] = {"n": n}

    # ---- Buildings (centroids) --------------------------------------------
    features["d_building"] = _nearest_point_distance(layers.building_xy, px, py)
    if layers.building_xy.shape[0] and layers.building_residential.any():
        residential_xy = layers.building_xy[layers.building_residential]
        features["d_building_res"] = _nearest_point_distance(residential_xy, px, py)
    else:
        features["d_building_res"] = np.full(n, FAR_AWAY_M)

    # ---- Roads -------------------------------------------------------------
    d_road, d_road_eff, road_idx = _weighted_nearest(layers.roads, layers.road_traffic, query_points, n)
    features["d_road"] = d_road
    features["d_road_eff"] = d_road_eff
    _, d_road_safety, _ = _weighted_nearest(layers.roads, layers.road_safety, query_points, n)
    features["d_road_safety_eff"] = d_road_safety
    features["road_name"] = [
        layers.road_names[i] if 0 <= i < len(layers.road_names) else "" for i in road_idx
    ]

    # ---- Paths (recreational traffic) --------------------------------------
    d_path, d_path_eff, _ = _weighted_nearest(layers.paths, layers.path_traffic, query_points, n)
    features["d_path"] = d_path
    features["d_path_eff"] = d_path_eff

    # ---- Railways and power lines ------------------------------------------
    features["d_railway"], _ = _nearest_distance(layers.railways, query_points, n)
    d_power_line, _ = _nearest_distance(layers.powerlines, query_points, n)
    d_power_tower, _ = _nearest_distance(layers.power_towers, query_points, n)
    features["d_power"] = np.minimum(d_power_line, d_power_tower)

    # ---- Crowd magnets -----------------------------------------------------
    attractor_geoms = shapely_points(
        np.asarray([p[0] for p in layers.attractor_xy] or [0.0]),
        np.asarray([p[1] for p in layers.attractor_xy] or [0.0]),
    )
    if layers.attractor_xy:
        d_attr, d_attr_eff, attr_idx = _weighted_nearest(
            list(attractor_geoms), layers.attractor_weight, query_points, n
        )
    else:
        d_attr = np.full(n, FAR_AWAY_M)
        d_attr_eff = np.full(n, FAR_AWAY_M)
        attr_idx = np.full(n, -1, dtype=int)
    features["d_attractor"] = d_attr
    features["d_attractor_eff"] = d_attr_eff
    features["attractor_kind"] = [
        layers.attractor_kind[i] if 0 <= i < len(layers.attractor_kind) else "" for i in attr_idx
    ]

    # ---- Land use: which area contains the point? --------------------------
    category, area_name = _classify_points(layers, query_points, n)
    features["category"] = category
    features["area_name"] = area_name

    # ---- Distance to built-up and recreational areas (EU A3) --------------
    built_up = [g for g, c in zip(layers.areas, layers.area_category) if c in BUILT_UP_CATEGORIES]
    recreation = [g for g, c in zip(layers.areas, layers.area_category) if c in RECREATION_CATEGORIES]
    features["d_builtup"], _ = _nearest_distance(built_up, query_points, n)
    features["d_recreation"], _ = _nearest_distance(recreation, query_points, n)
    features["d_settlement"] = np.minimum(features["d_builtup"], features["d_recreation"])

    # ---- Tree cover and water ----------------------------------------------
    features["d_tree"], _ = _nearest_distance(layers.trees, query_points, n)
    water = [g for g, c in zip(layers.areas, layers.area_category) if c == "water"]
    features["d_water"], _ = _nearest_distance(water, query_points, n)

    # ---- Protected areas ---------------------------------------------------
    in_protected, protected_name, protected_strict, d_protected = _protected_status(layers, query_points, n)
    features["in_protected"] = in_protected
    features["protected_name"] = protected_name
    features["protected_strict"] = protected_strict
    features["d_protected"] = d_protected

    # ---- Aerodromes --------------------------------------------------------
    aero_geoms = [a[0] for a in layers.aerodromes]
    d_aero, aero_idx = _nearest_distance(aero_geoms, query_points, n)
    features["d_aerodrome"] = d_aero
    features["aerodrome_kind"] = [
        layers.aerodromes[i][1] if 0 <= i < len(layers.aerodromes) else "" for i in aero_idx
    ]
    features["aerodrome_name"] = [
        layers.aerodromes[i][2] if 0 <= i < len(layers.aerodromes) else "" for i in aero_idx
    ]

    # ---- Placeholders for external sources (filled in later) --------------
    features["strava"] = np.zeros(n)        # 0 = no known activity
    features["d_strava"] = np.full(n, FAR_AWAY_M)   # no busy route nearby
    features["population"] = np.full(n, np.nan)

    return features


def _nearest_point_distance(xy: np.ndarray, px: np.ndarray, py: np.ndarray) -> np.ndarray:
    """
    Nearest neighbour within a pure point cloud.

    This is the common case for building centroids and is fastest via an
    STRtree built from point geometries.
    """
    n = len(px)
    if xy.shape[0] == 0:
        return np.full(n, FAR_AWAY_M)
    geoms = shapely_points(xy[:, 0], xy[:, 1])
    distances, _ = _nearest_distance(list(geoms), shapely_points(px, py), n)
    return distances


def _classify_points(layers: OsmLayers, query_points, n: int) -> tuple[list[str], list[str]]:
    """
    Assigns each point the category of the *smallest* area containing it.

    "Smallest wins" is the pragmatic way to resolve overlaps: a playground
    inside a park inside a forest should count as a playground, not a forest.
    """
    category = ["unknown"] * n
    area_name = [""] * n

    polygons = [(i, g) for i, g in enumerate(layers.areas) if isinstance(g, Polygon)]
    if not polygons:
        return category, area_name

    poly_idx = np.asarray([i for i, _ in polygons])
    geoms = [g for _, g in polygons]
    sizes = np.asarray([g.area for g in geoms])

    tree = STRtree(geoms)
    pairs = tree.query(query_points, predicate="within")
    if pairs.size == 0:
        return category, area_name

    point_ids, tree_ids = pairs[0], pairs[1]
    # Sort by descending area so small areas overwrite large ones.
    order = np.argsort(-sizes[tree_ids])
    point_ids, tree_ids = point_ids[order], tree_ids[order]

    assigned = np.full(n, -1, dtype=int)
    assigned[point_ids] = poly_idx[tree_ids]

    for i in range(n):
        a = assigned[i]
        if a >= 0:
            category[i] = layers.area_category[a]
            area_name[i] = layers.area_name[a]
    return category, area_name


def _protected_status(layers: OsmLayers, query_points, n: int):
    """Is the point inside a protected area - and how strict is that protection?"""
    in_protected = np.zeros(n, dtype=bool)
    strict = np.zeros(n, dtype=bool)
    names = [""] * n
    d_protected = np.full(n, FAR_AWAY_M)

    if not layers.protected:
        return in_protected, names, strict, d_protected

    d_protected, _ = _nearest_distance(layers.protected, query_points, n)

    polygons = [(i, g) for i, g in enumerate(layers.protected) if isinstance(g, Polygon)]
    if not polygons:
        return in_protected, names, strict, d_protected

    idx_map = np.asarray([i for i, _ in polygons])
    tree = STRtree([g for _, g in polygons])
    pairs = tree.query(query_points, predicate="within")
    if pairs.size == 0:
        return in_protected, names, strict, d_protected

    for point_id, tree_id in zip(pairs[0], pairs[1]):
        original = int(idx_map[tree_id])
        in_protected[point_id] = True
        is_strict = layers.protected_class[original] == "strict"
        # When in doubt the strictest status wins.
        if is_strict or not names[point_id]:
            names[point_id] = layers.protected_name[original]
        strict[point_id] = strict[point_id] or is_strict
    return in_protected, names, strict, d_protected
