"""
Region pages at scale: some 380 towns, many of them so close that their
search circles overlap. Each page must still say something of its own.
"""

from __future__ import annotations

import asyncio

from app import region_pages, regions
from app.cities import slugify


def _point(lat: float, lon: float, score: float = 0.9) -> dict:
    return {
        "lat": lat, "lon": lon, "score": score, "blocked": False, "category": "meadow", "area_name": "",
        "reasons": [], "warnings": [],
    }


# Four good spots well apart, around 51.50 / 7.20 (between Bochum and Herne).
SHARED = [_point(51.50 + 0.02 * i, 7.20) for i in range(4)]


def _fake_search(points_for):
    async def run_search(request):
        centre = {"lat": request.lat, "lon": request.lon}
        # Like the real search: only points inside the circle.
        inside = [p for p in points_for(request.lat, request.lon) if regions._distance_m(p, centre) <= 10_000]
        return {"points": inside}

    return run_search


def test_a_town_whose_spots_are_on_a_neighbours_page_gets_none(monkeypatch):
    big = {"name": "Bochum", "slug": "bochum", "lat": 51.48, "lon": 7.22, "state": "Nordrhein-Westfalen"}
    small = {"name": "Herne", "slug": "herne", "lat": 51.54, "lon": 7.22, "state": "Nordrhein-Westfalen"}
    own = [_point(51.60 + 0.02 * i, 7.30) for i in range(3)]
    elsewhere = {"name": "Recklinghausen", "slug": "recklinghausen", "lat": 51.61, "lon": 7.20, "state": "Nordrhein-Westfalen"}

    monkeypatch.setattr(regions, "run_search", _fake_search(lambda lat, lon: SHARED + (own if lat > 51.6 else [])))

    async def no_place(*_args, **_kwargs):
        return ""

    monkeypatch.setattr(regions, "reverse_geocode", no_place)
    built = asyncio.run(regions.build([big, small, elsewhere], log=lambda _msg: None))

    # Bochum lists the shared spots; Herne would only repeat them; Recklinghausen
    # has three of its own and lists only those.
    assert [r["slug"] for r in built] == ["bochum", "recklinghausen"]
    assert {(s["lat"], s["lon"]) for s in built[1]["spots"]} == {(p["lat"], p["lon"]) for p in own}


def test_nearby_regions_cross_state_borders():
    mainz = {"name": "Mainz", "slug": "mainz", "lat": 49.99, "lon": 8.27, "state": "Rheinland-Pfalz"}
    wiesbaden = {"name": "Wiesbaden", "slug": "wiesbaden", "lat": 50.08, "lon": 8.24, "state": "Hessen"}
    trier = {"name": "Trier", "slug": "trier", "lat": 49.75, "lon": 6.64, "state": "Rheinland-Pfalz"}
    for r in (mainz, wiesbaden, trier):
        r.update(radius_km=10.0, spots=[], facts={"points": 1, "blocked_share": 0, "good_spots": 3,
                                                   "nature_reserves": [], "aerodromes": []})
    body = region_pages.region_page(mainz, [trier, wiesbaden, mainz], {}, "de")["body"]
    assert "Regionen in der Nähe" in body
    assert body.index("/regionen/wiesbaden") < body.index("/regionen/trier")


def test_slugs_match_the_published_ones():
    assert slugify("Frankfurt (Oder)") == "frankfurt-oder"
    assert slugify("Mülheim an der Ruhr") == "muelheim-an-der-ruhr"
    assert slugify("Halle (Saale)") == "halle-saale"
    assert slugify("Lahr/Schwarzwald") == "lahr-schwarzwald"
    assert slugify("Weiden in der Oberpfalz") == "weiden-in-der-oberpfalz"
