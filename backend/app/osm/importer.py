"""
Geofabrik extract (.osm.pbf + .poly) -> local tile store.

    python -m app.osm.importer germany-latest.osm.pbf --poly germany.poly \
        --out data/osm-store.sqlite

This is deliberately an offline job. The public server has 2 GB of RAM and one
core; importing Germany wants more than that and takes a while, so it runs on
a workstation or in CI and the server only ever receives the finished file.

Selection mirrors the Overpass query in app/services/overpass.py element for
element, so the pipeline sees the same data either way. One deliberate
difference: multipolygon members are merged into closed rings where they join
up, where Overpass hands back the raw member ways. A forest drawn as several
open way segments therefore arrives as an area instead of as a bundle of lines
that the layer builder cannot use as land cover.

Members that do NOT close into a ring are still kept, as open lines - exactly
what Overpass would have returned. osmium's own area assembler is not used for
that reason: it drops a relation entirely when any member is missing, and
large protected areas routinely reach past the edge of an extract. Measured on
the Tübingen extract, that lost 199 of 213 protected-area geometries and turned
154 grid points inside a nature reserve into "fine to fly".
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sqlite3
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import osmium
from shapely.geometry import MultiLineString, box, mapping
from shapely.ops import linemerge

from app.osm import codec
from app.osm.store import SCHEMA, parse_poly
from app.services import overpass as ov

# --- Selection, mirroring build_query() -----------------------------------
_RAILWAY = re.compile(ov._RAILWAY_RE)
_POWER_WAY = re.compile(ov._POWER_WAY_RE)
_POWER_NODE = re.compile(ov._POWER_NODE_RE)
_NATURAL = re.compile(ov._NATURAL_RE)
_AMENITY_AREA = re.compile(ov._AMENITY_AREA_RE)
_AMENITY_NODE = re.compile(ov._AMENITY_NODE_RE)
_TOURISM = re.compile(ov._TOURISM_RE)
_LEISURE_NODE = re.compile(ov._LEISURE_NODE_RE)
_BOUNDARY = re.compile(ov._BOUNDARY_RE)
_AERO_NODE = re.compile("^(aerodrome|heliport|airstrip)$")
_ROUTE = re.compile(ov._ROUTE_RE)

# Keys that can make a relation interesting; used to limit area assembly.
AREA_KEYS = ("building", "landuse", "natural", "leisure", "boundary", "aeroway", "military")


def _match(pattern: re.Pattern[str], value: str | None) -> bool:
    return value is not None and pattern.search(value) is not None


def wanted_node(t: dict[str, str]) -> bool:
    return (
        _match(_AMENITY_NODE, t.get("amenity"))
        or _match(_TOURISM, t.get("tourism"))
        or _match(_LEISURE_NODE, t.get("leisure"))
        or _match(_POWER_NODE, t.get("power"))
        or _match(_AERO_NODE, t.get("aeroway"))
        or t.get("highway") == "bus_stop"
    )


def wanted_way(t: dict[str, str]) -> bool:
    return (
        "highway" in t
        or _match(_RAILWAY, t.get("railway"))
        or _match(_POWER_WAY, t.get("power"))
        or "landuse" in t
        or _match(_NATURAL, t.get("natural"))
        or "leisure" in t
        or _match(_BOUNDARY, t.get("boundary"))
        or "aeroway" in t
        or _match(_AMENITY_AREA, t.get("amenity"))
        or _match(_TOURISM, t.get("tourism"))
        or "military" in t
    )


def wanted_relation(t: dict[str, str]) -> bool:
    return (
        "landuse" in t
        or _match(_NATURAL, t.get("natural"))
        or "leisure" in t
        or _match(_BOUNDARY, t.get("boundary"))
        or "aeroway" in t
        or "military" in t
    )


# --- Tiling ---------------------------------------------------------------
def tiles_touching(min_lat: float, min_lon: float, max_lat: float, max_lon: float, deg: float):
    for iy in range(math.floor(min_lat / deg), math.floor(max_lat / deg) + 1):
        for ix in range(math.floor(min_lon / deg), math.floor(max_lon / deg) + 1):
            yield ix, iy


def coverage_tiles(coverage, deg: float) -> set[tuple[int, int]]:
    min_lon, min_lat, max_lon, max_lat = coverage.bounds
    return {
        (ix, iy)
        for ix, iy in tiles_touching(min_lat, min_lon, max_lat, max_lon, deg)
        # Overlap, not just a shared edge: an outline running exactly along a
        # tile border would otherwise add a row of empty tiles.
        if coverage.intersection(box(ix * deg, iy * deg, (ix + 1) * deg, (iy + 1) * deg)).area > 0
    }


def join_rings(lines: list[list[tuple[float, float]]]) -> list[list[tuple[float, float]]]:
    """
    Member ways -> rings. Pieces that join up end to end become one closed
    ring; whatever cannot be closed (members missing from the extract) stays
    an open line, which is what Overpass would have returned for it.
    """
    if not lines:
        return []
    merged = linemerge(MultiLineString([[(lon, lat) for lat, lon in line] for line in lines]))
    parts = merged.geoms if hasattr(merged, "geoms") else [merged]
    return [[(lat, lon) for lon, lat in part.coords] for part in parts if len(part.coords) >= 2]


def _bbox(coords: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    lats = [c[0] for c in coords]
    lons = [c[1] for c in coords]
    return min(lats), min(lons), max(lats), max(lons)


# --- Import ---------------------------------------------------------------
class Stager:
    """Buffers (tile, element) rows in a scratch SQLite file, grouped at the end."""

    def __init__(self, path: Path, tiles: set[tuple[int, int]], deg: float) -> None:
        path.unlink(missing_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA journal_mode=OFF")
        self.conn.execute("PRAGMA synchronous=OFF")
        self.conn.execute("CREATE TABLE staged (ix INTEGER, iy INTEGER, el TEXT)")
        self.tiles = tiles
        self.deg = deg
        self.buffer: list[tuple[int, int, str]] = []
        self.count = 0

    def add(self, element: dict[str, Any], bbox: tuple[float, float, float, float]) -> None:
        payload = json.dumps(element, separators=(",", ":"))
        hit = False
        for tile in tiles_touching(*bbox, self.deg):
            if tile in self.tiles:
                self.buffer.append((tile[0], tile[1], payload))
                hit = True
        if hit:
            self.count += 1
        if len(self.buffer) >= 50_000:
            self.flush()

    def flush(self) -> None:
        self.conn.executemany("INSERT INTO staged VALUES (?, ?, ?)", self.buffer)
        # Commit every batch. Python's sqlite3 wraps INSERTs in an implicit
        # transaction, and with journal_mode=OFF nothing of an uncommitted one
        # is visible to another connection - the packing workers, or a
        # --from-staging run after an interruption, would see an empty table.
        self.conn.commit()
        self.buffer.clear()


def _pack_tile(job: tuple[str, int, int]) -> tuple[int, int, int, bytes]:
    """One tile's staged elements -> compressed payload. Runs in a worker process."""
    staging, ix, iy = job
    conn = sqlite3.connect(f"file:{Path(staging).as_posix()}?mode=ro", uri=True)
    rows = [r[0] for r in conn.execute("SELECT el FROM staged WHERE ix = ? AND iy = ?", (ix, iy))]
    conn.close()
    # The staged rows already are JSON objects: join them instead of parsing
    # and re-serialising every element.
    return ix, iy, len(rows), codec.pack_json("[" + ",".join(rows) + "]")


class _Inline:
    """Stand-in for a process pool when one process is enough."""

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None

    @staticmethod
    def map(fn, items, chunksize=1):
        return map(fn, items)


def run_import(pbf: Path, poly: Path, out: Path, deg: float, index: str, log=print) -> dict[str, Any]:
    started = time.perf_counter()
    coverage = parse_poly(poly.read_text(encoding="utf-8"))
    tiles = coverage_tiles(coverage, deg)
    log(f"[import] {poly.stem}: {len(tiles)} tiles of {deg:g} degrees")

    work = out.with_suffix(".staging.sqlite")
    stager = Stager(work, tiles, deg)
    counts = {"nodes": 0, "ways": 0, "buildings": 0, "relations": 0}

    # --- Pass 1: which relations do we want, and which ways make them up ---
    relations: dict[int, tuple[dict[str, str], list[int]]] = {}
    member_ways: set[int] = set()
    # Ways on signposted routes -> strongest route level (see annotate_routes).
    route_levels: dict[int, str] = {}
    for rel in osmium.FileProcessor(str(pbf), osmium.osm.RELATION).with_filter(
        osmium.filter.KeyFilter(*AREA_KEYS, "route")
    ):
        tags = dict(rel.tags)
        if _match(_ROUTE, tags.get("route")):
            level = ov.route_level(tags)
            for m in rel.members:
                if m.type == "w":
                    route_levels[m.ref] = ov.stronger_level(route_levels.get(m.ref), level)
            continue
        if not ("building" in tags or wanted_relation(tags)):
            continue
        ways = [m.ref for m in rel.members if m.type == "w" and m.role in ("outer", "")]
        if ways:
            relations[rel.id] = (codec.slim_tags(tags.items()), ways)
            member_ways.update(ways)
    log(
        f"[import] pass 1: {len(relations)} relations with {len(member_ways)} member ways, "
        f"{len(route_levels)} ways on signposted routes"
    )

    # --- Pass 2: nodes and ways, with locations ---------------------------
    member_coords: dict[int, list[tuple[float, float]]] = {}
    # Untagged nodes only carry positions. The location index (which runs
    # before any filter) still sees them, but Python does not have to iterate
    # them - about 95 % of all objects. Ways stay unfiltered: untagged ways are
    # the outer rings of many multipolygons.
    untagged_nodes = osmium.filter.EmptyTagFilter()
    untagged_nodes.enable_for(osmium.osm.NODE)
    processor = (
        osmium.FileProcessor(str(pbf), osmium.osm.NODE | osmium.osm.WAY)
        .with_locations(index)
        .with_filter(untagged_nodes)
    )

    seen = 0
    for obj in processor:
        seen += 1
        if seen % 5_000_000 == 0:
            log(f"[import]   {seen / 1e6:.0f} M objects, {stager.count / 1e6:.2f} M kept, {time.perf_counter() - started:.0f} s")

        if obj.is_node():
            if not obj.tags:
                continue
            tags = dict(obj.tags)
            if wanted_node(tags) and obj.location.valid():
                lat, lon = obj.location.lat, obj.location.lon
                stager.add(codec.encode_node(obj.id, codec.slim_tags(tags.items()), lat, lon), (lat, lon, lat, lon))
                counts["nodes"] += 1

        elif obj.is_way():
            is_member = obj.id in member_ways
            if not obj.tags and not is_member:
                continue
            tags = dict(obj.tags)
            is_building = "building" in tags
            wanted = is_building or wanted_way(tags)
            if not (wanted or is_member):
                continue
            coords = [(n.lat, n.lon) for n in obj.nodes if n.location.valid()]
            if len(coords) < 2:
                continue
            if is_member:
                member_coords[obj.id] = coords
            if not wanted:
                continue
            bbox = _bbox(coords)
            slim = codec.slim_tags(tags.items())
            if is_building:
                # Overpass ``out center`` = centre of the bounding box.
                c_lat, c_lon = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
                stager.add(codec.encode_center("w", obj.id, slim, c_lat, c_lon), (c_lat, c_lon, c_lat, c_lon))
                counts["buildings"] += 1
            else:
                if obj.id in route_levels:
                    slim[codec.ROUTE_TAG] = route_levels[obj.id]
                stager.add(codec.encode_way(obj.id, slim, coords), bbox)
                counts["ways"] += 1

    # --- Relations: join the member ways into rings ----------------------
    for rel_id, (slim, ways) in relations.items():
        rings = join_rings([member_coords[w] for w in ways if w in member_coords])
        if not rings:
            continue  # every member lies outside the extract
        bbox = _bbox([c for r in rings for c in r])
        if "building" in slim:
            c_lat, c_lon = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
            stager.add(codec.encode_center("r", rel_id, slim, c_lat, c_lon), (c_lat, c_lon, c_lat, c_lon))
            counts["buildings"] += 1
        else:
            stager.add(codec.encode_relation(rel_id, slim, rings), bbox)
            counts["relations"] += 1
    member_coords.clear()

    stager.flush()
    read_s = time.perf_counter() - started
    log(f"[import] read done in {read_s:.0f} s: {counts}")

    stager.conn.commit()
    stager.conn.close()
    header = osmium.io.Reader(str(pbf), osmium.osm.osm_entity_bits.NOTHING).header()
    total_bytes = write_store(
        work, tiles, coverage, out, deg, poly.stem, header.get("osmosis_replication_timestamp", ""), log
    )
    work.unlink(missing_ok=True)

    result = {
        **counts,
        "tiles": len(tiles),
        "store_mb": round(out.stat().st_size / 1e6, 1),
        "avg_tile_kb": round(total_bytes / max(len(tiles), 1) / 1e3, 1),
        "read_s": round(read_s),
        "total_s": round(time.perf_counter() - started),
    }
    log(f"[import] done: {result}")
    return result


def write_store(
    staging: Path,
    tiles: set[tuple[int, int]],
    coverage,
    out: Path,
    deg: float,
    region: str,
    data_timestamp: str,
    log=print,
) -> int:
    """
    Staged (tile, element) rows -> the finished store. Separate from the read
    pass so an import can be resumed from its staging file (--from-staging)
    after the expensive part is done. Returns the payload bytes written.
    """
    conn = sqlite3.connect(staging)
    staged_rows = conn.execute("SELECT COUNT(*) FROM staged").fetchone()[0]
    if staged_rows == 0:
        conn.close()
        raise RuntimeError(f"{staging} holds no staged elements - nothing to write, staging file kept")
    log(f"[import] {staged_rows:,} staged rows")
    conn.execute("CREATE INDEX IF NOT EXISTS staged_tile ON staged (ix, iy)")
    conn.commit()
    conn.close()

    out.unlink(missing_ok=True)
    store = sqlite3.connect(out)
    store.executescript(SCHEMA)
    total_bytes = 0
    jobs = [(str(staging), ix, iy) for ix, iy in sorted(tiles)]
    # zstd at level 19 manages ~2 MB/s per core - for Germany (~9 GB of JSON)
    # that is over an hour on one core, so tiles are packed in parallel.
    # Small imports (tests, a district) are not worth starting processes for.
    workers = min(os.cpu_count() or 1, 16) if len(jobs) >= 64 else 1
    with ProcessPoolExecutor(max_workers=workers) if workers > 1 else _Inline() as pool:
        written_rows = 0
        for n, (ix, iy, count, blob) in enumerate(pool.map(_pack_tile, jobs, chunksize=4)):
            total_bytes += len(blob)
            written_rows += count
            store.execute("INSERT INTO tiles VALUES (?, ?, ?, ?)", (ix, iy, count, blob))
            if n % 200 == 0:
                store.commit()
                log(f"[import]   packed {n}/{len(jobs)} tiles ({workers} processes)")

    # Every staged row belongs to exactly one tile. A mismatch means the store
    # is incomplete - fail loudly instead of shipping it (and deleting the
    # staging file it could be rebuilt from).
    if written_rows != staged_rows:
        store.close()
        raise RuntimeError(f"wrote {written_rows:,} of {staged_rows:,} staged rows - store incomplete, staging file kept")

    meta = {
        "codec_version": str(codec.CODEC_VERSION),
        "tile_deg": f"{deg:g}",
        "region": region,
        "data_timestamp": data_timestamp,
        "imported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "coverage": json.dumps(mapping(coverage)),
    }
    store.executemany("INSERT INTO meta VALUES (?, ?)", meta.items())
    store.commit()
    store.execute("VACUUM")
    store.close()
    return total_bytes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("pbf", type=Path)
    parser.add_argument("--poly", type=Path, required=True, help="Geofabrik .poly outline of the extract")
    parser.add_argument("--out", type=Path, default=Path("data/osm-store.sqlite"))
    parser.add_argument("--tile-deg", type=float, default=0.1, help="must match OVERPASS_TILE_DEG")
    parser.add_argument(
        "--index",
        default="flex_mem",
        help="osmium node location index. flex_mem is fine for a state; for Germany on a "
        "machine with <16 GB RAM use 'sparse_file_array,<path>'",
    )
    parser.add_argument(
        "--from-staging",
        action="store_true",
        help="skip reading the PBF and finish from <out>.staging.sqlite left by an interrupted run",
    )
    args = parser.parse_args(argv)
    if args.from_staging:
        coverage = parse_poly(args.poly.read_text(encoding="utf-8"))
        header = osmium.io.Reader(str(args.pbf), osmium.osm.osm_entity_bits.NOTHING).header()
        staging = args.out.with_suffix(".staging.sqlite")
        write_store(
            staging,
            coverage_tiles(coverage, args.tile_deg),
            coverage,
            args.out,
            args.tile_deg,
            args.poly.stem,
            header.get("osmosis_replication_timestamp", ""),
        )
        staging.unlink(missing_ok=True)
        print(f"[import] done: {args.out} ({args.out.stat().st_size / 1e6:,.0f} MB)")
        return 0
    run_import(args.pbf, args.poly, args.out, args.tile_deg, args.index)
    return 0


if __name__ == "__main__":
    sys.exit(main())
