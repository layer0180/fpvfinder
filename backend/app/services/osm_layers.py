"""
Translates raw Overpass elements into thematic geometry layers.

Everything is converted into the local metre projection immediately, so that
all distances later come out directly in metres.

The classification tables (which tag maps to which category) live here; the
*rating* of those categories lives in ``config/weights.json``. That keeps the
data model separate from personal taste.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry

from app.services.spatial import LocalProjection

# Simplification tolerance in metres. Cuts the vertex count considerably
# without distorting distances at the 10 m scale we care about.
SIMPLIFY_TOLERANCE_M = 2.0


# ---------------------------------------------------------------------------
# Tag classification
# ---------------------------------------------------------------------------

# Building types where people are likely to be present.
# ``yes`` is included on purpose: unspecified buildings are usually dwellings,
# and when in doubt we want the larger safety clearance.
RESIDENTIAL_BUILDINGS = {
    "yes", "house", "residential", "apartments", "detached", "semidetached_house",
    "terrace", "bungalow", "dormitory", "farm", "hut", "cabin", "static_caravan",
    "hotel", "school", "kindergarten", "hospital", "church", "cathedral", "chapel",
    "civic", "public", "commercial", "retail", "office", "sports_hall",
}

# Buildings without a permanent human presence -> obstacle only, not a people indicator.
NONRESIDENTIAL_BUILDINGS = {
    "barn", "shed", "farm_auxiliary", "greenhouse", "garage", "garages", "carport",
    "industrial", "warehouse", "service", "roof", "ruins", "silo", "stable",
    "hangar", "transformer_tower", "water_tower", "bunker", "container", "cowshed",
}

# landuse=* -> internal category
LANDUSE_MAP = {
    "farmland": "farmland", "farmyard": "farmyard", "meadow": "meadow",
    "grass": "grass", "orchard": "orchard", "vineyard": "vineyard",
    "greenhouse_horticulture": "greenhouse", "plant_nursery": "plant_nursery",
    "forest": "forest", "allotments": "allotments", "residential": "residential",
    "industrial": "industrial", "commercial": "commercial", "retail": "retail",
    "military": "military", "cemetery": "cemetery", "religious": "religious",
    "quarry": "quarry", "landfill": "landfill", "brownfield": "brownfield",
    "greenfield": "greenfield", "construction": "construction",
    "village_green": "village_green", "recreation_ground": "recreation_ground",
    "railway": "railway_area", "basin": "water", "reservoir": "water",
    "salt_pond": "water", "aquaculture": "water", "flowerbed": "garden",
    "garages": "industrial", "port": "industrial", "depot": "industrial",
}

# natural=* -> internal category
NATURAL_MAP = {
    "wood": "forest", "scrub": "scrub", "heath": "heath", "grassland": "grassland",
    "water": "water", "wetland": "wetland", "beach": "beach", "sand": "beach",
    "bare_rock": "quarry", "scree": "quarry", "tree_row": "forest",
    "mud": "wetland", "shingle": "beach",
}

# leisure=* -> internal category
LEISURE_MAP = {
    "park": "park", "garden": "garden", "playground": "playground",
    "pitch": "pitch", "sports_centre": "sports_centre", "stadium": "sports_centre",
    "golf_course": "golf_course", "nature_reserve": "nature_reserve",
    "recreation_ground": "recreation_ground", "dog_park": "dog_park",
    "marina": "marina", "track": "sports_centre", "swimming_pool": "water",
    "water_park": "sports_centre", "fitness_centre": "sports_centre",
    "horse_riding": "recreation_ground", "common": "village_green",
}

AMENITY_AREA_MAP = {
    "school": "school_grounds", "kindergarten": "school_grounds",
    "university": "school_grounds", "college": "school_grounds",
    "hospital": "school_grounds", "parking": "commercial",
    "marketplace": "commercial", "place_of_worship": "religious",
}

TOURISM_AREA_MAP = {
    "camp_site": "camp_site", "caravan_site": "camp_site",
    "theme_park": "sports_centre", "zoo": "sports_centre",
    "attraction": "park", "picnic_site": "park",
}

# Areas counting as tree cover / obstacles (structure bonus plus obstacle warning)
TREE_CATEGORIES = {"forest", "scrub", "orchard"}


def classify_area(tags: dict[str, str]) -> str | None:
    """
    Assigns exactly one category to an area.

    Order equals priority: specific leisure use beats general land use (a park
    inside a forest is, practically speaking, a park).
    """
    if not tags:
        return None
    if tags.get("aeroway") in ("aerodrome", "heliport", "airstrip", "runway", "taxiway", "apron"):
        return "aerodrome"
    if tags.get("military"):
        return "military"
    leisure = tags.get("leisure")
    if leisure in LEISURE_MAP:
        return LEISURE_MAP[leisure]
    tourism = tags.get("tourism")
    if tourism in TOURISM_AREA_MAP:
        return TOURISM_AREA_MAP[tourism]
    amenity = tags.get("amenity")
    if amenity in AMENITY_AREA_MAP:
        return AMENITY_AREA_MAP[amenity]
    landuse = tags.get("landuse")
    if landuse in LANDUSE_MAP:
        return LANDUSE_MAP[landuse]
    natural = tags.get("natural")
    if natural in NATURAL_MAP:
        return NATURAL_MAP[natural]
    boundary = tags.get("boundary")
    if boundary == "national_park":
        return "national_park"
    if boundary == "protected_area":
        return "protected_area"
    return None


def is_protected(tags: dict[str, str]) -> bool:
    """
    Is this a protected area in the nature conservation sense?

    Deliberately broad: better one warning too many than one too few.
    Landscape protection areas (protect_class 5) are legally different from
    strict nature reserves, so the protection class is carried along and
    treated differently during scoring.
    """
    if tags.get("leisure") == "nature_reserve":
        return True
    if tags.get("boundary") in ("protected_area", "national_park"):
        return True
    return False


def protect_class(tags: dict[str, str]) -> str:
    """
    Rough classification of the protection status.

    ``strict``    -> nature reserve / national park: taking off is usually banned.
    ``landscape`` -> landscape protection / Natura 2000: often allowed, but check.
    """
    pc = tags.get("protect_class", "")
    if tags.get("boundary") == "national_park" or pc in ("1", "1a", "1b", "2", "3", "4"):
        return "strict"
    if tags.get("leisure") == "nature_reserve" and pc not in ("5", "6", "7"):
        return "strict"
    return "landscape"


def is_area_geometry(coords: list[tuple[float, float]], tags: dict[str, str]) -> bool:
    """Closed ring with enough points -> an area (unless explicitly ``area=no``)."""
    if tags.get("area") == "no":
        return False
    return len(coords) >= 4 and coords[0] == coords[-1]


# ---------------------------------------------------------------------------
# Layer container
# ---------------------------------------------------------------------------
@dataclass
class OsmLayers:
    """All prepared geometries in local metres."""

    proj: LocalProjection

    # Buildings as centroids (x, y) plus a "probably inhabited" mask
    building_xy: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))
    building_residential: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=bool))

    # Roads carrying motor traffic
    roads: list[BaseGeometry] = field(default_factory=list)
    road_traffic: list[float] = field(default_factory=list)   # "people" weight
    road_safety: list[float] = field(default_factory=list)    # "safety clearance" weight
    road_names: list[str] = field(default_factory=list)

    # Ways without motor traffic (recreational use)
    paths: list[BaseGeometry] = field(default_factory=list)
    path_traffic: list[float] = field(default_factory=list)

    railways: list[BaseGeometry] = field(default_factory=list)
    powerlines: list[BaseGeometry] = field(default_factory=list)
    power_towers: list[BaseGeometry] = field(default_factory=list)

    # Areas with their category
    areas: list[BaseGeometry] = field(default_factory=list)
    area_category: list[str] = field(default_factory=list)
    area_name: list[str] = field(default_factory=list)

    # Tree cover (a subset of the areas, plus tree rows)
    trees: list[BaseGeometry] = field(default_factory=list)

    # Protected areas
    protected: list[BaseGeometry] = field(default_factory=list)
    protected_name: list[str] = field(default_factory=list)
    protected_class: list[str] = field(default_factory=list)

    # Crowd magnets
    attractor_xy: list[tuple[float, float]] = field(default_factory=list)
    attractor_weight: list[float] = field(default_factory=list)
    attractor_kind: list[str] = field(default_factory=list)

    # Aerodromes (geometry, kind, name)
    aerodromes: list[tuple[BaseGeometry, str, str]] = field(default_factory=list)

    def summary(self) -> dict[str, int]:
        return {
            "buildings": int(self.building_xy.shape[0]),
            "roads": len(self.roads),
            "paths": len(self.paths),
            "railways": len(self.railways),
            "powerlines": len(self.powerlines) + len(self.power_towers),
            "areas": len(self.areas),
            "trees": len(self.trees),
            "protected": len(self.protected),
            "attractors": len(self.attractor_xy),
            "aerodromes": len(self.aerodromes),
        }


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
def _coords_from_geometry(geometry: Iterable[dict[str, float]], proj: LocalProjection) -> list[tuple[float, float]]:
    """Overpass ``geometry`` list -> list of (x, y) in metres."""
    lats, lons = [], []
    for node in geometry:
        if node is None or "lat" not in node or "lon" not in node:
            continue  # gaps appear where the tile clips the way
        lats.append(node["lat"])
        lons.append(node["lon"])
    if len(lats) < 2:
        return []
    x, y = proj.to_xy(np.asarray(lats), np.asarray(lons))
    return list(zip(x.tolist(), y.tolist()))


def _make_geometry(coords: list[tuple[float, float]], tags: dict[str, str]) -> BaseGeometry | None:
    """Builds a polygon or line string, repairing broken polygons on the way."""
    if len(coords) < 2:
        return None
    if is_area_geometry(coords, tags):
        try:
            poly = Polygon(coords)
            if not poly.is_valid:
                poly = poly.buffer(0)  # the classic self-intersection fix
            if poly.is_empty or poly.area <= 0:
                return None
            return poly.simplify(SIMPLIFY_TOLERANCE_M, preserve_topology=True)
        except (ValueError, TypeError):
            return None
    try:
        return LineString(coords).simplify(SIMPLIFY_TOLERANCE_M, preserve_topology=False)
    except (ValueError, TypeError):
        return None


def build_layers(
    elements: list[dict[str, Any]],
    proj: LocalProjection,
    config: dict[str, Any],
) -> OsmLayers:
    """Main entry point: Overpass elements -> ``OsmLayers``."""
    layers = OsmLayers(proj=proj)

    road_classes: dict[str, dict[str, float]] = config["road_classes"]
    path_classes: dict[str, float] = config["path_classes"]
    attractor_weights: dict[str, float] = config["attractor_weights"]

    building_lat: list[float] = []
    building_lon: list[float] = []
    building_res: list[bool] = []

    for el in elements:
        etype = el.get("type")
        tags = el.get("tags") or {}

        # ---- Buildings (arrive as ``center``) -----------------------------
        if "building" in tags and "center" in el:
            center = el["center"]
            building_lat.append(center["lat"])
            building_lon.append(center["lon"])
            btype = tags.get("building", "yes")
            if btype in NONRESIDENTIAL_BUILDINGS:
                building_res.append(False)
            else:
                building_res.append(btype in RESIDENTIAL_BUILDINGS or btype == "yes")
            continue

        # ---- Point POIs ----------------------------------------------------
        if etype == "node":
            _parse_node(el, tags, layers, proj, attractor_weights)
            continue

        # ---- Ways and relations --------------------------------------------
        geometries: list[list[tuple[float, float]]] = []
        if etype == "way" and "geometry" in el:
            coords = _coords_from_geometry(el["geometry"], proj)
            if coords:
                geometries.append(coords)
        elif etype == "relation":
            # Multipolygons: we only use the outer rings. Ignoring inner holes
            # (clearings) is the conservative choice - a point in a forest
            # clearing then counts as being in the forest.
            for member in el.get("members", []):
                if member.get("role") not in ("outer", "", None):
                    continue
                geom = member.get("geometry")
                if not geom:
                    continue
                coords = _coords_from_geometry(geom, proj)
                if coords:
                    geometries.append(coords)

        for coords in geometries:
            _parse_way_geometry(coords, tags, layers, road_classes, path_classes)

    if building_lat:
        bx, by = proj.to_xy(np.asarray(building_lat), np.asarray(building_lon))
        layers.building_xy = np.column_stack([bx, by])
        layers.building_residential = np.asarray(building_res, dtype=bool)

    return layers


def _parse_node(
    el: dict[str, Any],
    tags: dict[str, str],
    layers: OsmLayers,
    proj: LocalProjection,
    attractor_weights: dict[str, float],
) -> None:
    lat, lon = el.get("lat"), el.get("lon")
    if lat is None or lon is None:
        return
    x, y = proj.to_xy(lat, lon)
    x, y = float(x), float(y)

    # Pylons: a pure obstacle
    if tags.get("power") in ("tower", "pole", "portal"):
        layers.power_towers.append(Point(x, y))
        return

    # Aerodromes mapped as a node
    aeroway = tags.get("aeroway")
    if aeroway in ("aerodrome", "heliport", "airstrip"):
        layers.aerodromes.append((Point(x, y), aeroway, tags.get("name", "aerodrome")))
        return

    # Crowd magnets
    for key in ("leisure", "tourism", "amenity", "highway"):
        value = tags.get(key)
        if value and value in attractor_weights:
            layers.attractor_xy.append((x, y))
            layers.attractor_weight.append(float(attractor_weights[value]))
            layers.attractor_kind.append(value)
            return


def _parse_way_geometry(
    coords: list[tuple[float, float]],
    tags: dict[str, str],
    layers: OsmLayers,
    road_classes: dict[str, dict[str, float]],
    path_classes: dict[str, float],
) -> None:
    geom = _make_geometry(coords, tags)
    if geom is None or geom.is_empty:
        return

    # ---- Linear features ---------------------------------------------------
    highway = tags.get("highway")
    if highway:
        if highway in road_classes:
            layers.roads.append(geom)
            layers.road_traffic.append(float(road_classes[highway]["weight"]))
            layers.road_safety.append(float(road_classes[highway]["safety"]))
            layers.road_names.append(tags.get("name", ""))
            return
        if highway in path_classes:
            layers.paths.append(geom)
            layers.path_traffic.append(float(path_classes[highway]))
            return
        # Unknown highway values (e.g. ``construction``) are ignored.

    if tags.get("railway"):
        layers.railways.append(geom)
        return

    if tags.get("power") in ("line", "minor_line"):
        layers.powerlines.append(geom)
        return

    if tags.get("natural") == "tree_row":
        layers.trees.append(geom)
        return

    # ---- Areas --------------------------------------------------------------
    if is_protected(tags):
        layers.protected.append(geom)
        layers.protected_name.append(tags.get("name", "protected area"))
        layers.protected_class.append(protect_class(tags))
        # No return on purpose: a nature reserve is also a land use.

    category = classify_area(tags)
    if category is None:
        return

    if category == "aerodrome":
        layers.aerodromes.append((geom, "aerodrome", tags.get("name", "aerodrome")))

    # Only genuine areas go into the land use layer (line strings are useless
    # for "is this point inside category X").
    if isinstance(geom, Polygon):
        layers.areas.append(geom)
        layers.area_category.append(category)
        layers.area_name.append(tags.get("name", ""))
        if category in TREE_CATEGORIES:
            layers.trees.append(geom)
