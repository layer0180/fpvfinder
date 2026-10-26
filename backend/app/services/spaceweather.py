"""
Planetary Kp index from NOAA's Space Weather Prediction Center.

Fetched by the server, not the browser: the value is the same for everyone,
so one request every half hour serves all visitors, and no visitor's IP
address goes to a US agency.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import httpx

from app.config import SETTINGS

KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"
CACHE_S = 30 * 60

_cache: tuple[float, float | None] | None = None


def _next_hours_max(rows: list[dict], now: datetime) -> float | None:
    """Highest Kp of the three-hour slots overlapping the next three hours."""
    values = []
    for row in rows:
        try:
            start = datetime.fromisoformat(row["time_tag"]).replace(tzinfo=timezone.utc)
            kp = float(row["kp"])
        except (KeyError, TypeError, ValueError):
            continue
        if start + timedelta(hours=3) > now and start < now + timedelta(hours=3):
            values.append(kp)
    return max(values) if values else None


async def current_kp() -> float | None:
    global _cache
    if _cache and time.monotonic() - _cache[0] < CACHE_S:
        return _cache[1]
    try:
        async with httpx.AsyncClient(timeout=10.0, headers={"User-Agent": SETTINGS.user_agent}) as client:
            resp = await client.get(KP_URL)
        resp.raise_for_status()
        value = _next_hours_max(resp.json(), datetime.now(timezone.utc))
    except (httpx.HTTPError, ValueError):
        value = None
    _cache = (time.monotonic(), value)
    return value
