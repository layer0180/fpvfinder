"""
Place search: Photon first, Nominatim as the fallback, both behind a cache.

Why two services. Nominatim's policy allows one request per second for the
whole app and forbids autocomplete; with a search box that suggests places as
you type, a busy evening would queue everybody behind that one-per-second gate
and still break the rules. Photon (komoot) is built for type-ahead and asks
only for fair use. Nominatim stays as the fallback because it is the
reference and is sometimes better at exact addresses.

The cache is what keeps "fair use" true when traffic spikes: the places
people search for after a video are the same handful of towns, so nearly every
lookup after the first is answered locally and never leaves the server.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import time
from typing import Any

import httpx

from app.config import SETTINGS

_rate_lock = asyncio.Lock()
_last_call: dict[str, float] = {}

# Minimum gap per upstream. Nominatim's is policy; Photon's is courtesy.
MIN_INTERVAL_S = {"nominatim": 1.1, "photon": 0.2}

CACHE_TTL_S = 30 * 86400

# Photon is fast when it is up, and sometimes not up at all (connections that
# hang until the timeout). A short timeout plus a pause after a failure keeps
# a dead Photon from adding seconds to every lookup.
PHOTON_TIMEOUT_S = 3.0
PHOTON_PAUSE_S = 300.0
_photon_down_until = 0.0

# Photon's ``osm_value`` for places worth offering first. Streets and shops are
# still returned, just ranked below towns and villages.
PLACE_VALUES = {"city", "town", "village", "suburb", "hamlet", "municipality", "borough", "quarter"}


class GeocodeError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
class _Cache:
    def __init__(self) -> None:
        self._conn = sqlite3.connect(SETTINGS.data_dir / "geocode.sqlite", check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS geocode (key TEXT PRIMARY KEY, created_at REAL NOT NULL, payload TEXT NOT NULL)"
        )
        self._lock = threading.Lock()

    def get(self, key: str) -> list[dict[str, Any]] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM geocode WHERE key = ? AND created_at > ?", (key, time.time() - CACHE_TTL_S)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, key: str, value: list[dict[str, Any]]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO geocode VALUES (?, ?, ?)", (key, time.time(), json.dumps(value))
            )
            self._conn.commit()


_cache: _Cache | None = None


def _get_cache() -> _Cache:
    global _cache
    if _cache is None:
        _cache = _Cache()
    return _cache


def _normalise(query: str) -> str:
    return " ".join(query.lower().split())


async def _throttle(service: str) -> None:
    async with _rate_lock:
        wait = MIN_INTERVAL_S[service] - (time.monotonic() - _last_call.get(service, 0.0))
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call[service] = time.monotonic()


# ---------------------------------------------------------------------------
# Upstreams
# ---------------------------------------------------------------------------
def _photon_label(props: dict[str, Any]) -> str:
    """'Bad Urach, Reutlingen, Baden-Württemberg' - name first, then context."""
    parts = [props.get("name")]
    if props.get("street") and props.get("name") != props.get("street"):
        parts.append(f"{props['street']} {props.get('housenumber', '')}".strip())
    for key in ("city", "county", "state"):
        value = props.get(key)
        if value and value not in parts:
            parts.append(value)
    return ", ".join(p for p in parts if p)


async def _photon(query: str, limit: int, lang: str) -> list[dict[str, Any]]:
    await _throttle("photon")
    params: dict[str, Any] = {"q": query, "limit": str(limit * 3), "lang": lang}
    async with httpx.AsyncClient(timeout=PHOTON_TIMEOUT_S, headers={"User-Agent": SETTINGS.user_agent}) as client:
        resp = await client.get(f"{SETTINGS.photon_url}/api", params=params)
    resp.raise_for_status()

    results = []
    for feature in resp.json().get("features", []):
        props = feature.get("properties", {})
        if SETTINGS.geocode_country and props.get("countrycode", "").lower() != SETTINGS.geocode_country:
            continue
        lon, lat = feature["geometry"]["coordinates"][:2]
        results.append(
            {
                "label": _photon_label(props),
                "lat": float(lat),
                "lon": float(lon),
                "type": props.get("osm_value", ""),
            }
        )
    # Places before streets and POIs, otherwise keep Photon's own ranking.
    results.sort(key=lambda r: r["type"] not in PLACE_VALUES)
    return results[:limit]


async def _nominatim(query: str, limit: int, lang: str) -> list[dict[str, Any]]:
    await _throttle("nominatim")
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": str(limit),
        "addressdetails": "1",
        "accept-language": lang,
    }
    if SETTINGS.geocode_country:
        params["countrycodes"] = SETTINGS.geocode_country
    async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": SETTINGS.user_agent}) as client:
        resp = await client.get(f"{SETTINGS.nominatim_url}/search", params=params)
    resp.raise_for_status()
    return [
        {
            "label": item.get("display_name", ""),
            "lat": float(item["lat"]),
            "lon": float(item["lon"]),
            "type": item.get("type", ""),
        }
        for item in resp.json()
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def geocode(query: str, limit: int = 5, lang: str = "de", suggest: bool = False) -> list[dict[str, Any]]:
    """
    Place name or address -> matches, from cache, Photon or Nominatim.

    ``suggest`` marks type-ahead lookups. Those go to Photon only: Nominatim's
    policy forbids autocomplete, so while Photon is unavailable the search box
    simply shows no suggestions, and Nominatim answers only explicit searches.
    """
    global _photon_down_until
    key = f"{lang}:{limit}:{_normalise(query)}"
    cache = _get_cache()
    cached = cache.get(key)
    if cached is not None:
        return cached

    upstreams = []
    if SETTINGS.photon_url and time.monotonic() >= _photon_down_until:
        upstreams.append(("photon", _photon))
    if not suggest:
        upstreams.append(("nominatim", _nominatim))
    if not upstreams:
        return []

    errors: list[str] = []
    for name, upstream in upstreams:
        try:
            results = await upstream(query, limit, lang)
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            errors.append(f"{name}: {exc}")
            if name == "photon":
                _photon_down_until = time.monotonic() + PHOTON_PAUSE_S
            continue
        cache.put(key, results)
        return results
    if suggest:
        return []
    raise GeocodeError("; ".join(errors))


async def _nominatim_reverse(lat: float, lon: float, lang: str) -> str:
    await _throttle("nominatim")
    params = {"lat": str(lat), "lon": str(lon), "format": "jsonv2", "zoom": "14", "accept-language": lang}
    async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": SETTINGS.user_agent}) as client:
        resp = await client.get(f"{SETTINGS.nominatim_url}/reverse", params=params)
    resp.raise_for_status()
    address = resp.json().get("address", {})
    place = next((address[k] for k in ("village", "town", "suburb", "city", "municipality") if address.get(k)), "")
    return ", ".join(v for v in (place, address.get("county")) if v)


async def reverse_geocode(lat: float, lon: float, lang: str = "de", nominatim_fallback: bool = False) -> str:
    """
    Coordinate -> short place name (for labelling "my location").

    ``nominatim_fallback`` is for offline batch jobs only (app/regions.py): a
    few hundred lookups at one per second are within Nominatim's policy, a
    busy finder is not.
    """
    key = f"rev:{lang}:{lat:.3f},{lon:.3f}"
    cache = _get_cache()
    cached = cache.get(key)
    if cached is not None:
        return cached[0]["label"] if cached else ""
    label = ""
    try:
        if time.monotonic() < _photon_down_until:
            raise httpx.ConnectError("photon paused")
        await _throttle("photon")
        async with httpx.AsyncClient(timeout=PHOTON_TIMEOUT_S, headers={"User-Agent": SETTINGS.user_agent}) as client:
            resp = await client.get(
                f"{SETTINGS.photon_url}/reverse", params={"lat": str(lat), "lon": str(lon), "lang": lang}
            )
        resp.raise_for_status()
        features = resp.json().get("features", [])
        if features:
            # "Gomadingen, Landkreis Reutlingen" rather than a house number:
            # this labels where someone is, it is not a postal address.
            props = features[0].get("properties", {})
            label = ", ".join(v for v in (props.get("city") or props.get("name"), props.get("county")) if v)
    except (httpx.HTTPError, ValueError, KeyError):
        if not nominatim_fallback:
            return ""
        try:
            label = await _nominatim_reverse(lat, lon, lang)
        except (httpx.HTTPError, ValueError, KeyError):
            return ""
    cache.put(key, [{"label": label}])
    return label
