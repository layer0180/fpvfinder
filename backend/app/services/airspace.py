"""
Manually maintained airspace and no-fly zones.

Background: official airspace data (DFS AIS, Droniq and equivalents) is not
freely available as an API. This file is therefore deliberately an *advisory*
layer that you maintain yourself - not a substitute for the official check.

Format: an ordinary GeoJSON ``FeatureCollection`` in
``backend/data/airspace.geojson``. Supported geometries: Point, LineString,
Polygon, MultiPolygon.

Properties per feature:
    name      : display name (required)
    kind      : free text, e.g. "ctr", "airport", "nature", "military", "custom"
    severity  : "block" (points get blocked) | "warn" | "info"   [default: warn]
    buffer_m  : radius in metres; required for Point/LineString, optional for Polygon
    note      : free text, shown in the detail panel
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from shapely import STRtree
from shapely import points as shapely_points
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform

from app.config import SETTINGS
from app.services.spatial import LocalProjection

SEVERITY_ORDER = {"info": 0, "warn": 1, "block": 2}


def load_airspace() -> dict[str, Any]:
    """Reads the GeoJSON file (an empty FeatureCollection if it is missing)."""
    path: Path = SETTINGS.airspace_file
    if not path.exists():
        return {"type": "FeatureCollection", "features": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("type") != "FeatureCollection":
            return {"type": "FeatureCollection", "features": []}
        return data
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[airspace] WARNING: could not read {path.name}: {exc}")
        return {"type": "FeatureCollection", "features": []}


def save_airspace(collection: dict[str, Any]) -> None:
    SETTINGS.airspace_file.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.airspace_file.write_text(json.dumps(collection, indent=2, ensure_ascii=False), encoding="utf-8")


class AirspaceZones:
    """Projected no-fly zones with a fast point lookup."""

    def __init__(self, proj: LocalProjection, collection: dict[str, Any] | None = None) -> None:
        self.proj = proj
        self.geoms: list[BaseGeometry] = []
        self.names: list[str] = []
        self.severities: list[str] = []
        self.notes: list[str] = []

        collection = collection if collection is not None else load_airspace()
        for feature in collection.get("features", []):
            geometry = feature.get("geometry")
            if not geometry:
                continue
            props = feature.get("properties") or {}
            try:
                geom = shape(geometry)
            except (ValueError, AttributeError):
                continue

            # GeoJSON is lon/lat -> convert into local metres.
            local = shapely_transform(lambda x, y, z=None: self._project(x, y), geom)

            buffer_m = float(props.get("buffer_m", 0) or 0)
            if buffer_m > 0 or local.geom_type in ("Point", "LineString", "MultiLineString"):
                # Points and lines need a radius, otherwise they never match.
                local = local.buffer(max(buffer_m, 1.0))
            if local.is_empty:
                continue

            self.geoms.append(local)
            self.names.append(str(props.get("name", "no-fly zone")))
            severity = str(props.get("severity", "warn")).lower()
            self.severities.append(severity if severity in SEVERITY_ORDER else "warn")
            self.notes.append(str(props.get("note", "")))

        self._tree = STRtree(self.geoms) if self.geoms else None

    def _project(self, lon, lat):
        x, y = self.proj.to_xy(lat, lon)
        return float(x), float(y)

    def evaluate(self, px: np.ndarray, py: np.ndarray) -> dict[str, Any]:
        """
        Assigns each point the most severe zone containing it.

        Returns ``{"zone_names": [...], "zone_severity": [...], "zone_notes": [...]}``.
        """
        n = len(px)
        names = [""] * n
        severity = ["info"] * n
        notes = [""] * n
        rank = np.full(n, -1)

        if self._tree is None or n == 0:
            return {"zone_names": names, "zone_severity": severity, "zone_notes": notes}

        pairs = self._tree.query(shapely_points(px, py), predicate="within")
        if pairs.size == 0:
            return {"zone_names": names, "zone_severity": severity, "zone_notes": notes}

        for point_id, zone_id in zip(pairs[0], pairs[1]):
            zone_rank = SEVERITY_ORDER[self.severities[zone_id]]
            if zone_rank > rank[point_id]:
                rank[point_id] = zone_rank
                names[point_id] = self.names[zone_id]
                severity[point_id] = self.severities[zone_id]
                notes[point_id] = self.notes[zone_id]

        return {"zone_names": names, "zone_severity": severity, "zone_notes": notes}
