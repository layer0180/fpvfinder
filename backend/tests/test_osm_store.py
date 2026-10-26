"""
The local OSM store: import -> encode -> store -> decode, without network.

The fixture is a tiny hand-written .osm file. It covers the cases that went
wrong while building the importer, because getting them wrong is silent and
dangerous - a nature reserve that vanishes just makes a spot look better:

  * a protected area whose outline is split over two open ways (must come back
    as ONE closed ring, i.e. as an area),
  * a protected area with a member way missing from the extract (must still
    come back, as an open line, the way Overpass would return it),
  * a building (centre only), a road, a POI, and an untagged way (dropped).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np
import pytest

from app.osm import codec
from app.osm.importer import join_rings, run_import
from app.osm.store import OsmTileStore, parse_poly

OSM_XML = """<?xml version='1.0' encoding='UTF-8'?>
<osm version="0.6" generator="test">
  <!-- square reserve 48.41..48.42 / 9.41..9.42, outline split over ways 10 + 11 -->
  <node id="1" lat="48.41" lon="9.41"/>
  <node id="2" lat="48.41" lon="9.42"/>
  <node id="3" lat="48.42" lon="9.42"/>
  <node id="4" lat="48.42" lon="9.41"/>
  <way id="10"><nd ref="1"/><nd ref="2"/><nd ref="3"/></way>
  <way id="11"><nd ref="3"/><nd ref="4"/><nd ref="1"/></way>
  <relation id="100">
    <member type="way" ref="10" role="outer"/>
    <member type="way" ref="11" role="outer"/>
    <tag k="type" v="multipolygon"/>
    <tag k="leisure" v="nature_reserve"/>
    <tag k="name" v="Testreservat"/>
    <tag k="note" v="dropped - not a tag the layers read"/>
  </relation>

  <!-- second reserve: member 21 is not in the extract -->
  <node id="5" lat="48.43" lon="9.43"/>
  <node id="6" lat="48.43" lon="9.44"/>
  <way id="20"><nd ref="5"/><nd ref="6"/></way>
  <relation id="101">
    <member type="way" ref="20" role="outer"/>
    <member type="way" ref="21" role="outer"/>
    <tag k="type" v="boundary"/>
    <tag k="boundary" v="protected_area"/>
    <tag k="protect_class" v="4"/>
  </relation>

  <!-- building -> centre only -->
  <node id="7" lat="48.450" lon="9.450"/>
  <node id="8" lat="48.450" lon="9.452"/>
  <node id="9" lat="48.452" lon="9.452"/>
  <way id="30"><nd ref="7"/><nd ref="8"/><nd ref="9"/><nd ref="7"/><tag k="building" v="house"/><tag k="addr:street" v="Weg"/></way>

  <!-- regional hiking route over the road below -->
  <relation id="200">
    <member type="way" ref="40" role=""/>
    <tag k="type" v="route"/>
    <tag k="route" v="hiking"/>
    <tag k="network" v="rwn"/>
  </relation>

  <!-- road, POI, untagged way -->
  <way id="40"><nd ref="1"/><nd ref="9"/><tag k="highway" v="secondary"/></way>
  <node id="50" lat="48.44" lon="9.44"><tag k="amenity" v="biergarten"/></node>
  <way id="60"><nd ref="5"/><nd ref="9"/></way>
</osm>
"""

POLY = """test
1
   9.40   48.40
   9.50   48.40
   9.50   48.50
   9.40   48.50
END
END
"""


@pytest.fixture(scope="module")
def store(tmp_path_factory) -> OsmTileStore:
    work = tmp_path_factory.mktemp("osm")
    (work / "test.osm").write_text(OSM_XML, encoding="utf-8")
    (work / "test.poly").write_text(POLY, encoding="utf-8")
    out = work / "osm-store.sqlite"
    run_import(work / "test.osm", work / "test.poly", out, 0.1, "flex_mem", log=lambda *_: None)
    s = OsmTileStore(out)
    yield s
    s.close()


def _by_id(store: OsmTileStore) -> dict[tuple[str, int], dict]:
    return {(e["type"], e["id"]): e for e in store.get(94, 484)}


def test_split_outline_becomes_one_closed_ring(store):
    reserve = _by_id(store)[("relation", 100)]
    assert len(reserve["members"]) == 1
    lats, lons = codec.latlon(reserve["members"][0]["geometry"])
    assert len(lats) == 5 and (lats[0], lons[0]) == (lats[-1], lons[-1])
    assert reserve["tags"] == {"leisure": "nature_reserve", "name": "Testreservat"}


def test_incomplete_relation_is_kept_as_open_line(store):
    reserve = _by_id(store)[("relation", 101)]
    lats, lons = codec.latlon(reserve["members"][0]["geometry"])
    assert len(lats) == 2 and (lats[0], lons[0]) != (lats[-1], lons[-1])
    assert reserve["tags"]["protect_class"] == "4"


def test_building_is_stored_as_bbox_centre(store):
    building = _by_id(store)[("way", 30)]
    assert building["center"] == {"lat": 48.451, "lon": 9.451}
    assert "geometry" not in building
    assert building["tags"] == {"building": "house"}


def test_selection_matches_the_overpass_query(store):
    ids = _by_id(store)
    assert ("way", 40) in ids        # highway
    assert ("node", 50) in ids       # crowd magnet POI
    assert ("way", 60) not in ids    # untagged
    assert ("way", 10) not in ids    # untagged member: only part of its relation


def test_route_ways_are_marked_and_route_relations_dropped(store):
    ids = _by_id(store)
    assert ids[("way", 40)]["tags"]["_route"] == "rwn"
    assert ("relation", 200) not in ids


def test_overpass_route_annotation_keeps_the_strongest_level():
    from app.services.overpass import annotate_routes

    elements = [
        {"type": "way", "id": 1, "tags": {"highway": "track"}, "geometry": []},
        {"type": "way", "id": 2, "tags": {"highway": "path"}, "geometry": []},
        {"type": "relation", "id": 9, "tags": {"route": "hiking", "network": "lwn"},
         "members": [{"type": "way", "ref": 1}, {"type": "way", "ref": 2}]},
        {"type": "relation", "id": 8, "tags": {"route": "bicycle", "network": "ncn"},
         "members": [{"type": "way", "ref": 1}]},
    ]
    out = annotate_routes(elements)
    assert [e["id"] for e in out] == [1, 2]
    assert out[0]["tags"]["_route"] == "ncn"
    assert out[1]["tags"]["_route"] == "lwn"


def test_store_metadata_and_coverage(store):
    assert store.tile_deg == 0.1
    assert store.has_tile(94, 484) and not store.has_tile(95, 484)
    inside = store.covers(np.array([48.45, 48.55]), np.array([9.45, 9.45]))
    assert inside.tolist() == [True, False]


def test_codec_roundtrip_is_metre_accurate():
    elements = [
        codec.encode_way(1, {"highway": "track"}, [(48.1234567, 9.7654321), (48.2, 9.8)]),
        codec.encode_node(2, {"amenity": "bench"}, 48.3, 9.9),
    ]
    way, node = codec.unpack(codec.pack(elements))
    assert way["type"] == "way" and way["tags"] == {"highway": "track"}
    lats, _ = codec.latlon(way["geometry"])
    assert abs(lats[0] - 48.1234567) < 1e-5
    assert (node["lat"], node["lon"]) == (48.3, 9.9)


def test_latlon_reads_both_geometry_forms():
    overpass = [{"lat": 48.1, "lon": 9.1}, None, {"lat": 48.2, "lon": 9.2}]
    store = codec.unpack(codec.pack([codec.encode_way(1, {}, [(48.1, 9.1), (48.2, 9.2)])]))[0]["geometry"]
    for geometry in (overpass, store):
        lats, lons = codec.latlon(geometry)
        assert lats.tolist() == pytest.approx([48.1, 48.2]) and lons.tolist() == pytest.approx([9.1, 9.2])


def test_join_rings_keeps_unjoinable_pieces():
    rings = join_rings([[(0, 0), (0, 1)], [(0, 1), (1, 1)], [(5, 5), (6, 6)]])
    assert sorted(len(r) for r in rings) == [2, 3]


def test_parse_poly_handles_holes():
    text = "x\n1\n 0 0\n 10 0\n 10 10\n 0 10\nEND\n!2\n 4 4\n 6 4\n 6 6\n 4 6\nEND\nEND\n"
    area = parse_poly(text)
    assert area.area == pytest.approx(100 - 4)


def test_store_rejects_other_codec_versions(tmp_path):
    path = tmp_path / "osm-store.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript("CREATE TABLE meta (key TEXT, value TEXT); CREATE TABLE tiles (ix, iy, n_elements, payload);")
    conn.executemany(
        "INSERT INTO meta VALUES (?, ?)",
        [("codec_version", "999"), ("tile_deg", "0.1"), ("coverage", json.dumps({"type": "Point", "coordinates": [0, 0]}))],
    )
    conn.commit()
    conn.close()
    from app.osm.store import StoreError

    with pytest.raises(StoreError):
        OsmTileStore(Path(path))


def test_write_store_refuses_an_empty_staging_file(tmp_path):
    from app.osm.importer import write_store
    from shapely.geometry import box as shp_box

    staging = tmp_path / "x.staging.sqlite"
    conn = sqlite3.connect(staging)
    conn.execute("CREATE TABLE staged (ix INTEGER, iy INTEGER, el TEXT)")
    conn.commit()
    conn.close()
    with pytest.raises(RuntimeError, match="no staged elements"):
        write_store(staging, {(94, 484)}, shp_box(9.4, 48.4, 9.5, 48.5), tmp_path / "out.sqlite", 0.1, "x", "", log=lambda *_: None)
    assert staging.exists()
