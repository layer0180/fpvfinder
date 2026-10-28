"""
Region pages: "FPV spots around <city>", computed offline.

    python -m app.regions --out data/regions.json

Runs the normal search around every city in shared/regions/cities.json and
keeps what a page needs: the best few spots (spread out, with a place name,
reasons and warnings) plus a few facts about the area. It runs after the
monthly OSM import (.github/workflows/osm-data.yml), never on the server -
some 380 searches take a few hours. The list itself comes from app/cities.py.

A region only gets a page when it has enough to say: at least
MIN_GOOD_SPOTS spots scoring 70 or more. Thin pages that merely repeat a
city name are what search engines call doorway pages, and they hurt the
whole site.

The same goes for neighbours: in the Ruhr or around Stuttgart the 10 km
circles of several towns overlap. Cities are processed largest first, and a
spot already listed on another page is not listed again - a town gets a page
only with at least MIN_OWN_SPOTS spots of its own.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
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
MIN_OWN_SPOTS = 3
# A spot this close to one on another page counts as the same spot.
SAME_SPOT_M = 500.0


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


def top_spots(points: list[dict[str, Any]], taken: list[dict[str, Any]] = ()) -> list[dict[str, Any]]:
    """
    Best points without a block or a red warning, MIN_SEPARATION_M apart (cf.
    pickTopSpots in the finder), leaving out the ``taken`` ones of other pages.
    """
    picked: list[dict[str, Any]] = []
    for p in sorted(filter(_listable, points), key=lambda p: -p["score"]):
        if any(_distance_m(p, q) < SAME_SPOT_M for q in taken):
            continue
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
# Per city, the best listable points kept for the selection - far more than a
# page shows, so a town whose best spots went to a neighbour still has some.
CANDIDATES = 400


async def survey(city: dict[str, Any]) -> dict[str, Any]:
    """The search around one city, boiled down to what the selection needs."""
    result = await run_search(
        SearchRequest(lat=city["lat"], lon=city["lon"], radius_km=RADIUS_KM, time_profile=TIME_PROFILE, use_strava=False)
    )
    points = result["points"]
    best = sorted(filter(_listable, points), key=lambda p: -p["score"])[:CANDIDATES]
    return {"facts": area_facts(points), "candidates": [{k: p[k] for k in (*SPOT_FIELDS, "blocked")} for p in best]}


def _survey_in_process(city: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(survey(city))


async def _survey_all(cities: list[dict[str, Any]], workers: int, log) -> list[dict[str, Any]]:
    """
    The searches, the slow part: one process per core. They do not depend on
    each other - only the selection afterwards does, and that runs in order.
    """
    if workers <= 1:
        return [await survey(city) for city in cities]
    loop = asyncio.get_running_loop()
    done = 0

    async def one(pool, city):
        nonlocal done
        result = await loop.run_in_executor(pool, _survey_in_process, city)
        done += 1
        log(f"[regions] searched {done}/{len(cities)}: {city['name']}")
        return result

    with ProcessPoolExecutor(workers) as pool:
        return await asyncio.gather(*(one(pool, city) for city in cities))


async def build(cities: list[dict[str, Any]], log=print, workers: int = 1) -> list[dict[str, Any]]:
    surveys = await _survey_all(cities, workers, log)
    regions = []
    listed: list[dict[str, Any]] = []
    for n, (city, found) in enumerate(zip(cities, surveys), 1):
        facts = found["facts"]
        if facts["good_spots"] < MIN_GOOD_SPOTS:
            log(f"[regions] {n}/{len(cities)} {city['name']}: only {facts['good_spots']} good spots - no page")
            continue
        # Only the spots near listed ones need checking against them.
        nearby = [s for s in listed if _distance_m(s, city) < (RADIUS_KM * 1000 + SAME_SPOT_M)]
        spots = top_spots(found["candidates"], nearby)
        if len(spots) < MIN_OWN_SPOTS:
            log(f"[regions] {n}/{len(cities)} {city['name']}: its spots are on neighbouring pages - no page")
            continue
        listed.extend(spots)
        out_spots = []
        for spot in spots:
            item = {k: spot[k] for k in SPOT_FIELDS}
            # "near Leinfelden-Echterdingen" - a spot needs a place to be findable.
            item["place"] = (await reverse_geocode(spot["lat"], spot["lon"], "de", nominatim_fallback=True)).split(",")[0]
            out_spots.append(item)
        regions.append({**city, "radius_km": RADIUS_KM, "time_profile": TIME_PROFILE, "spots": out_spots, "facts": facts})
        log(f"[regions] {n}/{len(cities)} {city['name']}: {facts['good_spots']} good spots, best {round(spots[0]['score'] * 100)}")
    return regions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=Path("data/regions.json"))
    parser.add_argument("--only", help="comma separated city slugs, for trying it out")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1, help="searches in parallel (default: one per core)")
    args = parser.parse_args(argv)

    store = get_store()
    if store is None:
        print("[regions] no OSM store - import one first (app.osm.importer)")
        return 1
    cities = json.loads(CITIES_FILE.read_text(encoding="utf-8"))["cities"]
    if args.only:
        wanted = set(args.only.split(","))
        cities = [c for c in cities if c["slug"] in wanted]
    started = time.perf_counter()
    regions = asyncio.run(build(cities, workers=args.workers))
    payload = {
        "generated_at": time.strftime("%Y-%m-%d", time.gmtime()),
        "data_timestamp": store.data_timestamp,
        "regions": regions,
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(
        f"[regions] {len(regions)} of {len(cities)} cities get a page -> {args.out} "
        f"({(time.perf_counter() - started) / 60:.0f} min)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
