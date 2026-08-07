"""
Address lookup via Nominatim (OpenStreetMap).

Nominatim usage policy: at most one request per second and a meaningful
User-Agent. Both are implemented here.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from app.config import SETTINGS

_rate_lock = asyncio.Lock()
_last_call = 0.0
MIN_INTERVAL_S = 1.1


async def _throttle() -> None:
    global _last_call
    async with _rate_lock:
        wait = MIN_INTERVAL_S - (time.monotonic() - _last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call = time.monotonic()


async def geocode(query: str, limit: int = 5, country_codes: str = "") -> list[dict[str, Any]]:
    """
    Address or place name -> list of matches with lat/lon.

    ``country_codes`` optionally restricts the search (e.g. "de,at,ch").
    Empty means worldwide.
    """
    await _throttle()
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": str(limit),
        "addressdetails": "1",
    }
    if country_codes:
        params["countrycodes"] = country_codes

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


async def reverse_geocode(lat: float, lon: float) -> str:
    """Coordinate -> plain text address (for displaying the starting point)."""
    await _throttle()
    params = {"lat": str(lat), "lon": str(lon), "format": "jsonv2", "zoom": "14"}
    try:
        async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": SETTINGS.user_agent}) as client:
            resp = await client.get(f"{SETTINGS.nominatim_url}/reverse", params=params)
        resp.raise_for_status()
        return resp.json().get("display_name", "")
    except (httpx.HTTPError, ValueError):
        return ""
