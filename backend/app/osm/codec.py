"""
Compact on-disk encoding for one tile's OSM elements.

The pipeline consumes elements in the shape Overpass returns them (``out
center`` for buildings, ``out geom`` for everything else). Storing that shape
verbatim costs ~1.6 MB per 0.1 degree tile, which is ~7 GB for Germany - too
much for a small server. Measured on real tiles, three things bring it to
~0.33 MB without changing a single score:

  * Only the tags ``osm_layers.py`` actually reads are kept (Overpass returns
    every tag, including addresses, opening hours and source notes).
  * Coordinates are stored as integers in 1e-5 degrees, about 1 m - well below
    the 2 m simplification tolerance applied when the layers are built.
  * zstd instead of gzip.

``unpack`` returns Overpass-shaped dicts again, with one difference: a way's
``geometry`` is a flat int32 array [lat0, lon0, lat1, lon1, ...] in 1e-5
degrees instead of a list of {"lat", "lon"} dicts. Measured on a 10 km search
in Reutlingen, the dict form alone took ~500 MB for 1.2 million points - too
much for a small server. Read geometries through ``latlon()``, which accepts
both forms, so Overpass data keeps working unchanged.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Iterable

import numpy as np
import zstandard

# Bump when the encoding changes; the store refuses files with another version.
CODEC_VERSION = 1

SCALE = 100_000  # 1e-5 degrees, ~1.1 m north-south

ROUTE_TAG = "_route"

# Every tag osm_layers.py looks at. Anything else is dropped at import time.
KEEP_TAGS = frozenset(
    {
        "building", "highway", "railway", "power", "natural", "landuse", "leisure",
        "tourism", "amenity", "aeroway", "military", "boundary", "protect_class",
        "name", "area",
        # Tells FFH from bird protection areas (protect_class 97).
        "protection_title",
        # Not an OSM tag: set at import time on ways that belong to a
        # signposted route, holding the route's network level (see
        # annotate_routes in app/services/overpass.py).
        ROUTE_TAG,
    }
)

_COMPRESSOR = zstandard.ZstdCompressor(level=19)
_DECOMPRESSOR = zstandard.ZstdDecompressor()


def slim_tags(tags: Iterable[tuple[str, str]]) -> dict[str, str]:
    return {k: v for k, v in tags if k in KEEP_TAGS}


def q(value: float) -> int:
    """Degrees -> fixed-point integer."""
    return round(value * SCALE)


def encode_node(osm_id: int, tags: dict[str, str], lat: float, lon: float) -> dict[str, Any]:
    return {"i": osm_id, "t": "n", "g": tags, "p": [q(lat), q(lon)]}


def encode_center(osm_type: str, osm_id: int, tags: dict[str, str], lat: float, lon: float) -> dict[str, Any]:
    """A building: only its centre is kept, exactly like Overpass ``out center``."""
    return {"i": osm_id, "t": osm_type, "g": tags, "c": [q(lat), q(lon)]}


def encode_way(osm_id: int, tags: dict[str, str], coords: list[tuple[float, float]]) -> dict[str, Any]:
    """``coords`` as (lat, lon) pairs; stored flat as [lat0, lon0, lat1, lon1, ...]."""
    return {"i": osm_id, "t": "w", "g": tags, "l": [v for lat, lon in coords for v in (q(lat), q(lon))]}


def encode_relation(osm_id: int, tags: dict[str, str], rings: list[list[tuple[float, float]]]) -> dict[str, Any]:
    """A multipolygon by its outer rings only - inner rings are ignored downstream anyway."""
    return {
        "i": osm_id,
        "t": "r",
        "g": tags,
        "m": [[v for lat, lon in ring for v in (q(lat), q(lon))] for ring in rings],
    }


def pack(elements: list[dict[str, Any]]) -> bytes:
    return pack_json(json.dumps(elements, separators=(",", ":")))


def pack_json(text: str) -> bytes:
    """An already serialised element list -> compressed payload."""
    return _COMPRESSOR.compress(text.encode("utf-8"))


def latlon(geometry: Any) -> tuple[np.ndarray, np.ndarray]:
    """
    A way's geometry -> (lats, lons) in degrees, from either form: the
    store's flat int32 array, or Overpass's list of {"lat", "lon"} dicts (with
    the None gaps Overpass leaves where a tile clips a way).
    """
    if isinstance(geometry, np.ndarray):
        return geometry[0::2] / SCALE, geometry[1::2] / SCALE
    pts = [p for p in geometry if p is not None and "lat" in p and "lon" in p]
    return np.array([p["lat"] for p in pts], dtype=float), np.array([p["lon"] for p in pts], dtype=float)


def _flat(values: list[int]) -> np.ndarray:
    return np.asarray(values, dtype=np.int32)


BUILDING_BATCH = "building_batch"


def unpack_compact(blob: bytes, batch_id: int) -> list[dict[str, Any]]:
    """
    Like ``unpack``, but cheaper for the search pipeline, which decodes a
    million elements for a 10 km search in a city:

      * All buildings of the tile become ONE element of type
        ``building_batch`` with arrays ``lat``/``lon`` (degrees) and a list
        ``kind`` (the building=* value) - the layer builder needs nothing else.
        A building's centre lies in exactly one tile, so batches never need
        de-duplicating; ``batch_id`` only keeps their ids apart.
      * Identical tag dicts are shared: a hundred thousand
        {"highway": "track"} are one object.

    Measured on Berlin, 10 km: the decoded elements shrink from ~960 MB.
    """
    tag_pool: dict[tuple, dict[str, str]] = {}
    b_lat: list[int] = []
    b_lon: list[int] = []
    b_kind: list[str] = []
    out: list[dict[str, Any]] = []
    for e in json.loads(_DECOMPRESSOR.decompress(blob)):
        if "c" in e:
            b_lat.append(e["c"][0])
            b_lon.append(e["c"][1])
            b_kind.append(sys.intern(e["g"].get("building", "yes")))
            continue
        key = tuple(e["g"].items())
        tags = tag_pool.setdefault(key, e["g"])
        kind = e["t"]
        el: dict[str, Any] = {"type": {"n": "node", "w": "way", "r": "relation"}[kind], "id": e["i"], "tags": tags}
        if kind == "n":
            el["lat"], el["lon"] = e["p"][0] / SCALE, e["p"][1] / SCALE
        elif kind == "w":
            el["geometry"] = _flat(e["l"])
        else:
            el["members"] = [{"type": "way", "role": "outer", "geometry": _flat(ring)} for ring in e["m"]]
        out.append(el)
    if b_lat:
        out.append(
            {
                "type": BUILDING_BATCH,
                "id": batch_id,
                "tags": {},
                "lat": np.asarray(b_lat, dtype=np.int32) / SCALE,
                "lon": np.asarray(b_lon, dtype=np.int32) / SCALE,
                "kind": b_kind,
            }
        )
    return out


def unpack(blob: bytes) -> list[dict[str, Any]]:
    """Compressed tile -> Overpass-shaped elements."""
    out: list[dict[str, Any]] = []
    for e in json.loads(_DECOMPRESSOR.decompress(blob)):
        kind = e["t"]
        el: dict[str, Any] = {
            "type": {"n": "node", "w": "way", "r": "relation"}[kind],
            "id": e["i"],
            "tags": e["g"],
        }
        if "c" in e:
            el["center"] = {"lat": e["c"][0] / SCALE, "lon": e["c"][1] / SCALE}
        elif kind == "n":
            el["lat"], el["lon"] = e["p"][0] / SCALE, e["p"][1] / SCALE
        elif kind == "w":
            el["geometry"] = _flat(e["l"])
        else:
            el["members"] = [{"type": "way", "role": "outer", "geometry": _flat(ring)} for ring in e["m"]]
        out.append(el)
    return out
