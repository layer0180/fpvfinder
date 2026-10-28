"""
Keeps the OSM store and the region pages current while the server runs.

Every OSM_REFRESH_HOURS the server asks the release (app/osm/fetch.py) whether
newer files exist. A new store is downloaded next to the old one, checked,
swapped in and reopened - searches keep running throughout, the ones already
under way finish on the old file. No restart, no cron job.

Nothing else has to follow: cached search results are keyed by the store's
data timestamp (api/routes_search.py), and the region pages reload
regions.json when its modification time changes (region_pages.py).
"""

from __future__ import annotations

import asyncio

from app.config import SETTINGS
from app.osm import fetch
from app.osm.store import reload_store


async def refresh_once() -> None:
    # The download is blocking I/O: off the event loop, so searches go on.
    replaced = await asyncio.to_thread(fetch.fetch_all)
    if SETTINGS.osm_store in replaced:
        store = await asyncio.to_thread(reload_store)
        if store:
            print(f"[osm-refresh] new store in use: {store.region} ({store.data_timestamp}), {store.tile_count} tiles")


async def refresh_loop() -> None:
    """Runs until cancelled. The container start has just checked, so it waits first."""
    if SETTINGS.osm_refresh_hours <= 0 or not fetch.jobs():
        return
    while True:
        await asyncio.sleep(SETTINGS.osm_refresh_hours * 3600)
        try:
            await refresh_once()
        except Exception as exc:  # noqa: BLE001 - the next round tries again
            print(f"[osm-refresh] WARNING: {exc}")
