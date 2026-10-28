"""
Read side of the local OSM tile store.

One SQLite file holds every 0.1 degree tile of an imported region plus the
region's outline. A tile is present in the file whenever it touches the
region - even when it holds no elements - so "missing" always means "outside
the import", never "nothing there".

The outline matters as much as the tiles: a tile on the German border holds
German data only. Without the outline, the Austrian half of such a tile would
look like empty land and score as a perfect, deserted spot.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

import numpy as np
import shapely
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.geometry.base import BaseGeometry

from app.osm.codec import CODEC_VERSION, unpack, unpack_compact

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tiles (
    ix INTEGER NOT NULL,
    iy INTEGER NOT NULL,
    n_elements INTEGER NOT NULL,
    payload BLOB NOT NULL,
    PRIMARY KEY (ix, iy)
);
"""


class StoreError(RuntimeError):
    """The store file exists but cannot be used."""


def parse_poly(text: str) -> MultiPolygon:
    """
    Osmosis ``.poly`` format (what Geofabrik publishes next to each extract)
    -> MultiPolygon in lon/lat. Sections starting with ``!`` are holes.
    """
    lines = [line.strip() for line in text.splitlines()]
    outers: list[list[tuple[float, float]]] = []
    holes: list[list[tuple[float, float]]] = []
    i = 1  # line 0 is the file name
    while i < len(lines):
        header = lines[i]
        i += 1
        if header in ("", "END"):
            continue
        ring: list[tuple[float, float]] = []
        while i < len(lines) and lines[i] != "END":
            lon, lat = lines[i].split()[:2]
            ring.append((float(lon), float(lat)))
            i += 1
        i += 1  # skip the section's END
        (holes if header.startswith("!") else outers).append(ring)

    polygons = [Polygon(ring) for ring in outers if len(ring) >= 3]
    area = shapely.union_all(polygons)
    for hole in holes:
        area = area.difference(Polygon(hole))
    if isinstance(area, Polygon):
        area = MultiPolygon([area])
    return area


class OsmTileStore:
    """Thread-safe, read-only access to an imported region."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        # Read-only URI: the server never writes to the store, and this way a
        # store mounted :ro into the container works too.
        self._conn = sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True, check_same_thread=False)
        self._lock = threading.Lock()
        meta = dict(self._conn.execute("SELECT key, value FROM meta").fetchall())

        version = int(meta.get("codec_version", "0"))
        if version != CODEC_VERSION:
            raise StoreError(
                f"{self.path.name} was written with codec version {version}, this build reads "
                f"version {CODEC_VERSION} - re-run the import."
            )
        self.meta = meta
        self.tile_deg = float(meta["tile_deg"])
        self.region = meta.get("region", "")
        self.data_timestamp = meta.get("data_timestamp", "")
        self.coverage: BaseGeometry = shape(json.loads(meta["coverage"]))
        shapely.prepare(self.coverage)
        self._tiles = {(ix, iy) for ix, iy in self._conn.execute("SELECT ix, iy FROM tiles")}

    @classmethod
    def open_if_present(cls, path: Path) -> "OsmTileStore | None":
        return cls(path) if Path(path).exists() else None

    @property
    def tile_count(self) -> int:
        return len(self._tiles)

    def has_tile(self, ix: int, iy: int) -> bool:
        return (ix, iy) in self._tiles

    def get(self, ix: int, iy: int, compact: bool = False) -> list[dict[str, Any]] | None:
        """A tile's elements; ``compact`` for the search pipeline (see codec.unpack_compact)."""
        with self._lock:
            row = self._conn.execute("SELECT payload FROM tiles WHERE ix = ? AND iy = ?", (ix, iy)).fetchone()
        if not row:
            return None
        # Ids of building batches: unique per tile, far from any OSM id.
        return unpack_compact(row[0], -(ix * 100_000 + iy) - 1) if compact else unpack(row[0])

    def covers(self, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
        """Boolean mask: which points lie inside the imported region."""
        return shapely.contains_xy(self.coverage, np.asarray(lon, dtype=float), np.asarray(lat, dtype=float))

    def close(self) -> None:
        self._conn.close()

    def summary(self) -> dict[str, Any]:
        return {
            "region": self.region,
            "data_timestamp": self.data_timestamp,
            "tiles": self.tile_count,
            "tile_deg": self.tile_deg,
            "size_bytes": self.path.stat().st_size,
        }


_store: OsmTileStore | None = None
_store_checked = False
_store_lock = threading.Lock()


def get_store() -> OsmTileStore | None:
    """
    The process-wide store, opened on first use; ``None`` when no file exists.

    A broken store is not swallowed: serving searches from Overpass while an
    unreadable 1.5 GB file sits in the data volume would hide the problem until
    the public instances fall over.
    """
    global _store, _store_checked
    with _store_lock:
        if not _store_checked:
            from app.config import SETTINGS

            _store = OsmTileStore.open_if_present(SETTINGS.osm_store)
            _store_checked = True
        return _store


def reload_store() -> OsmTileStore | None:
    """
    Opens the store file afresh, after the monthly refresh replaced it.

    The previous store is left open: searches running on it finish on the old
    file (Linux keeps a replaced file readable while it is open), and its
    connection closes once the last of them lets go of it.
    """
    global _store, _store_checked
    from app.config import SETTINGS

    fresh = OsmTileStore.open_if_present(SETTINGS.osm_store)
    with _store_lock:
        _store, _store_checked = fresh, True
    return fresh
