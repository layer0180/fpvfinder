"""
The city list for the region pages (shared/regions/cities.json), from OSM.

    python -m app.cities germany-latest.osm.pbf --poly germany.poly

Reads every place=city/town node with a population of at least
--min-population from the extract, asks Photon for its federal state and
merges the result into cities.json. Entries already in the file keep their
slug and coordinates - a slug is a published address, and changing it would
break every link to that page. Run it by hand when the list should grow; the
monthly workflow only reads the file.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any

import httpx
import osmium
import shapely

from app.config import SETTINGS
from app.osm.store import parse_poly
from app.regions import CITIES_FILE

PLACES = {"city", "town"}

# Towns over the threshold whose population OSM lacks on the place node and on
# the boundary alike (checked October 2026). Rounded, from the federal
# statistics - only used to pass the threshold and to order the list.
KNOWN_POPULATION = {
    "Gießen": 92_000,
    "Rüsselsheim am Main": 66_000,
    "Hofheim am Taunus": 40_000,
    "Langen (Hessen)": 39_000,
    "Mühlhausen/Thüringen": 35_000,
    "Bad Vilbel": 34_000,
    "Bad Nauheim": 33_000,
    "Wernigerode": 32_000,
}


def slugify(name: str) -> str:
    """'Frankfurt (Oder)' -> 'frankfurt-oder', 'Mülheim an der Ruhr' -> 'muelheim-an-der-ruhr'."""
    text = name.lower()
    for umlaut, plain in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(umlaut, plain)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _population(tags: Any) -> int:
    # "12.345", "12 345" and "ca. 12345" all occur.
    digits = re.sub(r"\D", "", tags.get("population", "").split(";")[0])
    return int(digits) if digits else 0


def municipality_populations(pbf: Path) -> dict[int, tuple[str, int]]:
    """
    place node id -> (name, population) from the municipalities' boundaries.

    Many place nodes carry no population (Gießen, Wetzlar, ...) - the boundary
    relation does, and points at the node as its admin_centre or label. Only
    levels 6 (kreisfreie Stadt) and 8 (Gemeinde) and only under the same name:
    a district's admin_centre is its seat, whose population is not the
    district's.
    """
    found: dict[int, tuple[str, int]] = {}
    boundaries = osmium.filter.TagFilter(("boundary", "administrative"))
    for rel in osmium.FileProcessor(str(pbf), osmium.osm.RELATION).with_filter(boundaries):
        population = _population(rel.tags)
        if rel.tags.get("admin_level") not in ("6", "8") or not population:
            continue
        for member in rel.members:
            if member.type == "n" and member.role in ("admin_centre", "label"):
                found[member.ref] = (rel.tags.get("name", ""), population)
    return found


def read_places(pbf: Path, area, min_population: int) -> list[dict[str, Any]]:
    from_boundaries = municipality_populations(pbf)
    places = []
    for node in osmium.FileProcessor(str(pbf), osmium.osm.NODE).with_filter(osmium.filter.KeyFilter("place")):
        # name:de - Sorbian towns are named "Cottbus - Chóśebuz" in OSM.
        name = node.tags.get("name:de") or node.tags.get("name")
        if node.tags.get("place") not in PLACES or not name:
            continue
        population = _population(node.tags)
        if not population and node.id in from_boundaries:
            boundary_name, boundary_population = from_boundaries[node.id]
            if boundary_name in (name, node.tags.get("name")):
                population = boundary_population
        population = population or KNOWN_POPULATION.get(name, 0)
        lat, lon = node.location.lat, node.location.lon
        if population < min_population or not area.contains(shapely.Point(lon, lat)):
            continue
        places.append({"name": name, "lat": round(lat, 4), "lon": round(lon, 4), "population": population})
    return sorted(places, key=lambda p: -p["population"])


def federal_state(client: httpx.Client, lat: float, lon: float) -> str:
    time.sleep(0.5)  # well inside Photon's fair use
    resp = client.get(f"{SETTINGS.photon_url}/reverse", params={"lat": lat, "lon": lon, "lang": "de"})
    resp.raise_for_status()
    features = resp.json().get("features", [])
    return features[0]["properties"].get("state", "") if features else ""


def merge(existing: list[dict[str, Any]], found: list[dict[str, Any]], client: httpx.Client) -> list[dict[str, Any]]:
    by_slug = {c["slug"]: c for c in existing}
    merged = []
    for place in found:
        slug = slugify(place["name"])
        if slug in by_slug:
            # Published: keep slug, name and position, only learn the size.
            merged.append({**by_slug.pop(slug), "population": place["population"]})
            continue
        if any(c["slug"] == slug for c in merged):
            print(f"[cities] skipped a second '{place['name']}' - give it a distinct name by hand")
            continue
        state = federal_state(client, place["lat"], place["lon"])
        if not state:
            print(f"[cities] no federal state for {place['name']} - skipped")
            continue
        merged.append({"name": place["name"], "slug": slug, "lat": place["lat"], "lon": place["lon"], "state": state,
                       "population": place["population"]})
        print(f"[cities] + {place['name']} ({state}, {place['population']:,})")
    # Listed before but not found now (renamed in OSM, population tag gone):
    # kept, so their pages stay.
    for left in by_slug.values():
        print(f"[cities] kept {left['name']} - not in this extract with a population")
        merged.append(left)
    return sorted(merged, key=lambda c: -c.get("population", 0))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("pbf", type=Path)
    parser.add_argument("--poly", type=Path, required=True, help="the extract's outline, to drop places abroad")
    parser.add_argument("--min-population", type=int, default=30_000)
    args = parser.parse_args(argv)

    area = parse_poly(args.poly.read_text(encoding="utf-8"))
    shapely.prepare(area)
    found = read_places(args.pbf, area, args.min_population)
    print(f"[cities] {len(found)} places with at least {args.min_population:,} inhabitants")

    data = json.loads(CITIES_FILE.read_text(encoding="utf-8"))
    with httpx.Client(timeout=20.0, headers={"User-Agent": SETTINGS.user_agent}) as client:
        data["cities"] = merge(data["cities"], found, client)
    CITIES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[cities] {len(data['cities'])} cities -> {CITIES_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
