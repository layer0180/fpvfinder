"""
Overpass API client.

Design:
  * The search area is split into fixed degree tiles (0.1 by default). Every
    tile is queried and cached individually, so overlapping searches are nearly
    free.
  * One query per tile fetches everything needed at once. Buildings come back
    as centroids only (``out center``), which saves a large multiple of the
    payload in densely built-up areas and is accurate enough for the 50-500 m
    distance thresholds we care about.
  * Rate limiting: globally serialised with a minimum gap between requests,
    plus retry with backoff on 429/504 and failover to the next instance.
"""

from __future__ import annotations

import asyncio
import math
import time
from typing import Any, Awaitable, Callable

import httpx

from app.config import SETTINGS
from app.services.cache import OverpassCache

# Bump this whenever the query changes -> invalidates the cache.
QUERY_VERSION = 3

# Whitelists, so the response is not bloated by exotic tags.
_RAILWAY_RE = "^(rail|light_rail|subway|tram|narrow_gauge|funicular|monorail)$"
_POWER_WAY_RE = "^(line|minor_line)$"
_POWER_NODE_RE = "^(tower|pole|portal)$"
_NATURAL_RE = "^(wood|scrub|heath|grassland|water|wetland|beach|sand|bare_rock|scree|cliff|tree_row)$"
_AMENITY_AREA_RE = "^(school|kindergarten|university|college|hospital|parking|marketplace|place_of_worship)$"
_AMENITY_NODE_RE = (
    "^(restaurant|cafe|biergarten|fast_food|pub|bar|parking|school|kindergarten|"
    "hospital|marketplace|shelter|bench|hunting_stand|bbq)$"
)
_TOURISM_RE = "^(viewpoint|picnic_site|camp_site|caravan_site|attraction|theme_park|zoo|information|artwork)$"
_LEISURE_NODE_RE = "^(playground|picnic_table|fitness_station|firepit|slipway|bird_hide)$"
_BOUNDARY_RE = "^(protected_area|national_park|aboriginal_lands)$"


class OverpassError(RuntimeError):
    """Overpass definitively failed to deliver."""


def build_query(south: float, west: float, north: float, east: float, timeout_s: int) -> str:
    """Builds the combined Overpass QL query for one tile."""
    bbox = f"({south:.6f},{west:.6f},{north:.6f},{east:.6f})"
    b = bbox  # short alias for readability below
    return f"""
[out:json][timeout:{timeout_s}];

// --- 1) Buildings: centroids only, otherwise the response explodes --------
(
  way["building"]{b};
  relation["building"]{b};
)->.bld;

// --- 2) Linear features: roads, paths, railways, power lines -------------
(
  way["highway"]{b};
  way["railway"~"{_RAILWAY_RE}"]{b};
  way["power"~"{_POWER_WAY_RE}"]{b};
)->.lines;

// --- 3) Areas: land use, nature, leisure, protection, aerodromes ---------
(
  way["landuse"]{b};
  relation["landuse"]{b};
  way["natural"~"{_NATURAL_RE}"]{b};
  relation["natural"~"{_NATURAL_RE}"]{b};
  way["leisure"]{b};
  relation["leisure"]{b};
  way["boundary"~"{_BOUNDARY_RE}"]{b};
  relation["boundary"~"{_BOUNDARY_RE}"]{b};
  way["aeroway"]{b};
  relation["aeroway"]{b};
  way["amenity"~"{_AMENITY_AREA_RE}"]{b};
  way["tourism"~"{_TOURISM_RE}"]{b};
  way["military"]{b};
  relation["military"]{b};
)->.areas;

// --- 4) Point POIs: crowd magnets plus obstacles --------------------------
(
  node["amenity"~"{_AMENITY_NODE_RE}"]{b};
  node["tourism"~"{_TOURISM_RE}"]{b};
  node["leisure"~"{_LEISURE_NODE_RE}"]{b};
  node["power"~"{_POWER_NODE_RE}"]{b};
  node["aeroway"~"^(aerodrome|heliport|airstrip)$"]{b};
  node["highway"="bus_stop"]{b};
)->.pois;

.bld   out center;
.lines out geom;
.areas out geom;
.pois  out body;
""".strip()


def tiles_for_bbox(
    south: float, west: float, north: float, east: float, tile_deg: float
) -> list[tuple[int, int]]:
    """All tile indices (ix, iy) covering the bbox."""
    ix0 = math.floor(west / tile_deg)
    ix1 = math.floor(east / tile_deg)
    iy0 = math.floor(south / tile_deg)
    iy1 = math.floor(north / tile_deg)
    return [(ix, iy) for iy in range(iy0, iy1 + 1) for ix in range(ix0, ix1 + 1)]


def tile_bbox(ix: int, iy: int, tile_deg: float) -> tuple[float, float, float, float]:
    """(south, west, north, east) of one tile."""
    return (iy * tile_deg, ix * tile_deg, (iy + 1) * tile_deg, (ix + 1) * tile_deg)


class OverpassClient:
    """
    Async client with a global rate limit.

    The rate limit is process wide (class attributes) so that parallel search
    jobs cannot overwhelm the public instance either.
    """

    _rate_lock = asyncio.Lock()
    _last_request_at: float = 0.0

    def __init__(self, cache: OverpassCache | None = None) -> None:
        self.cache = cache or OverpassCache(SETTINGS.cache_db)
        self.settings = SETTINGS

    # -- public API ---------------------------------------------------------
    async def fetch_area(
        self,
        south: float,
        west: float,
        north: float,
        east: float,
        progress: Callable[[int, int, str], Awaitable[None]] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, int]]:
        """
        Fetches all OSM elements for the bbox (tile by tile, with caching).

        Returns: (deduplicated element list, statistics dict)
        """
        tile_deg = self.settings.overpass_tile_deg
        tiles = tiles_for_bbox(south, west, north, east, tile_deg)
        total = len(tiles)
        stats = {"tiles_total": total, "tiles_cached": 0, "tiles_fetched": 0, "elements_raw": 0}

        # Deduplicate by (type, id): ways on tile boundaries appear several times.
        merged: dict[tuple[str, int], dict[str, Any]] = {}

        for idx, (ix, iy) in enumerate(tiles):
            key = f"v{QUERY_VERSION}:{tile_deg:g}:{ix}:{iy}"
            max_age = self.settings.overpass_cache_ttl_days * 86400.0
            elements = self.cache.get(key, max_age_s=max_age)

            if elements is None:
                s, w, n, e = tile_bbox(ix, iy, tile_deg)
                if progress:
                    await progress(idx, total, f"Loading Overpass tile {idx + 1}/{total} ...")
                elements = await self._fetch_tile(s, w, n, e)
                self.cache.put(key, elements)
                stats["tiles_fetched"] += 1
            else:
                stats["tiles_cached"] += 1
                if progress:
                    await progress(idx, total, f"Tile {idx + 1}/{total} from cache")

            stats["elements_raw"] += len(elements)
            for el in elements:
                el_key = (el.get("type", "?"), int(el.get("id", 0)))
                if el_key not in merged:
                    merged[el_key] = el

        if progress:
            await progress(total, total, "OSM data complete")
        return list(merged.values()), stats

    # -- internals ----------------------------------------------------------
    async def _fetch_tile(self, south: float, west: float, north: float, east: float) -> list[dict[str, Any]]:
        query = build_query(south, west, north, east, int(self.settings.overpass_timeout_s))
        last_error: Exception | None = None
        urls = self.settings.overpass_urls or ["https://overpass-api.de/api/interpreter"]

        for attempt in range(self.settings.overpass_max_retries):
            # Use the next instance on every attempt: 429 and 504 are almost
            # always instance specific (load), not query specific.
            url = urls[attempt % len(urls)]
            await self._throttle()
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self.settings.overpass_timeout_s + 30.0),
                    headers={"User-Agent": self.settings.user_agent},
                ) as client:
                    resp = await client.post(url, data={"data": query})

                # 429 = rate limit, 504 = gateway timeout: both are worth retrying.
                if resp.status_code in (429, 502, 503, 504):
                    # Overpass occasionally sends Retry-After on 429.
                    retry_after = resp.headers.get("Retry-After")
                    try:
                        wait = float(retry_after) if retry_after else 0.0
                    except ValueError:
                        wait = 0.0
                    # A short wait is enough, since the next attempt lands on a
                    # different instance anyway.
                    wait = max(wait, min(30.0, 3.0 * (2**attempt)))
                    last_error = OverpassError(f"HTTP {resp.status_code} from {url}")
                    await asyncio.sleep(wait)
                    continue

                resp.raise_for_status()
                payload = resp.json()

                # Overpass sometimes reports errors with HTTP 200 in "remark".
                remark = payload.get("remark")
                if remark and "error" in remark.lower():
                    raise OverpassError(f"Overpass error: {remark}")

                return payload.get("elements", [])

            except (httpx.HTTPError, ValueError, OverpassError) as exc:
                last_error = exc
                if attempt < self.settings.overpass_max_retries - 1:
                    await asyncio.sleep(min(30.0, 3.0 * (2**attempt)))

        raise OverpassError(
            f"Overpass query failed after {self.settings.overpass_max_retries} attempts "
            f"across {len(urls)} instances: {last_error}. All public instances appear to be "
            "busy - try again later, or reduce OVERPASS_TILE_DEG in backend/.env (e.g. to 0.05) "
            "so the individual queries get lighter."
        )

    async def _throttle(self) -> None:
        """Enforces the minimum gap between two requests."""
        async with OverpassClient._rate_lock:
            wait = self.settings.overpass_min_interval_s - (time.monotonic() - OverpassClient._last_request_at)
            if wait > 0:
                await asyncio.sleep(wait)
            OverpassClient._last_request_at = time.monotonic()
