"""
Region pages: "FPV spots around <city>", computed offline.

    python -m app.regions --out data/regions.json

Runs the normal search around every city in shared/regions/cities.json and
keeps what a page needs: the best few spots (spread out, with a place name,
reasons and warnings) plus a few facts about the area. It runs after the
monthly OSM import (.github/workflows/osm-data.yml), never on the server -
85 searches in big cities take the better part of an hour.

A region only gets a page when it has enough to say: at least
MIN_GOOD_SPOTS spots scoring 70 or more. Thin pages that merely repeat a
city name are what search engines call doorway pages, and they hurt the
whole site.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

from app.config import BACKEND_DIR
from app.models import SearchRequest
from app.osm.store import get_store
from app.pipeline import run_search
from app.scoring.aggregate import STRICT_PROTECTED_CODES
from app.services.geocoding import reverse_geocode

CITIES_FILE = BACKEND_DIR.parent / "shared" / "regions" / "cities.json"

RADIUS_KM = 10.0
# A typical leisure slot - the one most visitors will look for.
TIME_PROFILE = "weekend_afternoon"
TOP_SPOTS = 6
MIN_SEPARATION_M = 1500.0
GOOD_SCORE = 0.7
MIN_GOOD_SPOTS = 3


def _distance_m(a: dict[str, float], b: dict[str, float]) -> float:
    k = math.pi / 180
    x = (b["lon"] - a["lon"]) * k * math.cos((a["lat"] + b["lat"]) / 2 * k)
    y = (b["lat"] - a["lat"]) * k
    return math.hypot(x, y) * 6_371_000


# Operating sites score well (empty, open) but are fenced, private and often
# dangerous - never recommend them. Same list as NOT_LISTED in the finder.
NOT_LISTED = {"landfill", "quarry", "construction", "military", "industrial", "railway_area", "farmyard"}


def _listable(p: dict[str, Any]) -> bool:
    return (
        not p["blocked"]
        and p["category"] not in NOT_LISTED
        and not any(w["level"] == "danger" for w in p["warnings"])
    )


def top_spots(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Best points without a block or a red warning, MIN_SEPARATION_M apart (cf. pickTopSpots in the finder)."""
    picked: list[dict[str, Any]] = []
    for p in sorted(filter(_listable, points), key=lambda p: -p["score"]):
        if all(_distance_m(p, q) >= MIN_SEPARATION_M for q in picked):
            picked.append(p)
        if len(picked) >= TOP_SPOTS:
            break
    return picked


def area_facts(points: list[dict[str, Any]]) -> dict[str, Any]:
    """Things worth telling about the area, read from the warnings of all points."""
    reserves: set[str] = set()
    aerodromes: set[str] = set()
    # The layer builder's stand-ins for unnamed objects are no facts.
    placeholders = {"aerodrome", "protected area", ""}
    for p in points:
        for w in p["warnings"]:
            name = w.get("params", {}).get("name") or ""
            if name in placeholders:
                continue
            if w["code"] in STRICT_PROTECTED_CODES:
                reserves.add(name)
            elif w["code"] in ("aerodrome_too_close", "aerodrome_near"):
                aerodromes.add(name)
    blocked = sum(p["blocked"] for p in points)
    return {
        "points": len(points),
        "blocked_share": round(blocked / max(len(points), 1), 3),
        "good_spots": sum(1 for p in points if _listable(p) and p["score"] >= GOOD_SCORE),
        "nature_reserves": sorted(reserves)[:8],
        "aerodromes": sorted(aerodromes)[:5],
    }


SPOT_FIELDS = ("lat", "lon", "score", "category", "area_name", "reasons", "warnings")


async def build(cities: list[dict[str, Any]], log=print) -> list[dict[str, Any]]:
    regions = []
    for n, city in enumerate(cities, 1):
        started = time.perf_counter()
        result = await run_search(
            SearchRequest(lat=city["lat"], lon=city["lon"], radius_km=RADIUS_KM, time_profile=TIME_PROFILE, use_strava=False)
        )
        points = result["points"]
        facts = area_facts(points)
        spots = top_spots(points)
        if facts["good_spots"] < MIN_GOOD_SPOTS:
            log(f"[regions] {n}/{len(cities)} {city['name']}: only {facts['good_spots']} good spots - no page")
            continue
        out_spots = []
        for spot in spots:
            item = {k: spot[k] for k in SPOT_FIELDS}
            # "near Leinfelden-Echterdingen" - a spot needs a place to be findable.
            item["place"] = (await reverse_geocode(spot["lat"], spot["lon"], "de", nominatim_fallback=True)).split(",")[0]
            out_spots.append(item)
        regions.append({**city, "radius_km": RADIUS_KM, "time_profile": TIME_PROFILE, "spots": out_spots, "facts": facts})
        log(
            f"[regions] {n}/{len(cities)} {city['name']}: {facts['good_spots']} good spots, "
            f"best {round(spots[0]['score'] * 100)}, {time.perf_counter() - started:.0f} s"
        )
    return regions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=Path("data/regions.json"))
    parser.add_argument("--only", help="comma separated city slugs, for trying it out")
    args = parser.parse_args(argv)

    store = get_store()
    if store is None:
        print("[regions] no OSM store - import one first (app.osm.importer)")
        return 1
    cities = json.loads(CITIES_FILE.read_text(encoding="utf-8"))["cities"]
    if args.only:
        wanted = set(args.only.split(","))
        cities = [c for c in cities if c["slug"] in wanted]
    regions = asyncio.run(build(cities))
    payload = {
        "generated_at": time.strftime("%Y-%m-%d", time.gmtime()),
        "data_timestamp": store.data_timestamp,
        "regions": regions,
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"[regions] {len(regions)} of {len(cities)} cities get a page -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
