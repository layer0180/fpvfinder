"""
FastAPI entry point.

Start it from the ``backend`` directory:
    uvicorn app.main:app --reload --port 8000

The interactive API docs are then at http://localhost:8000/docs
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app import __version__, web
from app.api import routes_meta, routes_search
from app.config import SETTINGS, USER_AGENT_WARNING, load_config
from app.osm.refresh import refresh_loop
from app.osm.store import get_store
from app.services.overpass import OutsideCoverageError, OverpassError

DISCLAIMER = (
    "This app is a research tool built on freely available OpenStreetMap data. "
    "It does NOT replace an official airspace and legal check. Before every flight you "
    "must verify the EU drone regulation (2019/947), the applicable national rules, "
    "current NOTAMs and geographical UAS zones yourself. Land use and protected area "
    "data from OSM may be incomplete or out of date."
)


def _startup_log() -> None:
    config = load_config(force=True)
    print(f"[fpvfinder] version {__version__}")
    print(f"[fpvfinder] mode:     {'PUBLIC (config endpoints disabled)' if SETTINGS.public_mode else 'private'}")
    print(
        f"[fpvfinder] limits:   max {SETTINGS.max_radius_km:g} km radius, "
        f"{SETTINGS.search_max_concurrent} concurrent searches"
    )
    if SETTINGS.public_mode and not SETTINGS.trust_proxy:
        print(
            "[fpvfinder] NOTE:     PUBLIC_MODE without TRUST_PROXY - if a reverse proxy "
            "sits in front, every client looks like the proxy and shares one rate limit."
        )
    if USER_AGENT_WARNING:
        print(f"[fpvfinder] WARNING:  {USER_AGENT_WARNING}")
    if SETTINGS.public_mode and not SETTINGS.operator_name:
        print("[fpvfinder] WARNING:  OPERATOR_NAME/OPERATOR_ADDRESS not set - the imprint shows a gap")
    print(f"[fpvfinder] overpass: {SETTINGS.overpass_url}")
    print(f"[fpvfinder] cache:    {SETTINGS.cache_db}")
    strava_mode = "off"
    if SETTINGS.strava_enabled and config["strava"].get("enabled", True):
        strava_mode = f"zoom {config['strava'].get('zoom', 12)}"
        strava_mode += " (+cookies)" if SETTINGS.strava_configured else " (public)"
    print(f"[fpvfinder] strava:   {strava_mode}")
    print(f"[fpvfinder] raster:   {'on' if config['population'].get('enabled') else 'off'}")
    print(f"[fpvfinder] zones:    {'on' if SETTINGS.airspace_enabled else 'off'}")

    # SEO state. Both of these fail silently and invisibly when wrong - a
    # sitemap full of localhost URLs still serves with a 200 - so say it here
    # where it is seen on every boot.
    if web.DIST.exists():
        print(f"[fpvfinder] site:     {web.SERVE_URL}" + (f" (rewritten from {web.BAKED_URL})" if web.SERVE_URL != web.BAKED_URL else ""))
        if web.SERVE_URL.startswith("http://localhost"):
            print(
                "[fpvfinder] WARNING:  canonical links and sitemap.xml point at localhost. "
                "Set PUBLIC_URL to the public address or search engines will index nothing."
            )
    else:
        print("[fpvfinder] site:     web/dist not built - API only (run the Astro dev server)")
    store = get_store()
    print(
        f"[fpvfinder] osm:      {store.region} ({store.data_timestamp or 'unknown date'}), {store.tile_count} tiles"
        if store
        else "[fpvfinder] osm:      no local store - every area comes from Overpass"
    )
    print(f"[fpvfinder] fallback: {'live Overpass outside the store' if SETTINGS.osm_live_fallback else 'off'}")
    if os.environ.get("OSM_STORE_URL") or os.environ.get("REGIONS_URL"):
        hours = SETTINGS.osm_refresh_hours
        print(f"[fpvfinder] refresh:  {f'checks for new OSM data every {hours:g} h' if hours > 0 else 'only at start'}")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _startup_log()
    refresher = asyncio.create_task(refresh_loop())
    yield
    refresher.cancel()


app = FastAPI(
    lifespan=lifespan,
    title="FPV Flying Spot Finder",
    version=__version__,
    description=(
        "Finds locations for FPV flights with few people around and good flying "
        "conditions.\n\n**Legal notice:** " + DISCLAIMER
    ),
)

# JSON search results compress ~10x; the static assets are small enough either way.
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=SETTINGS.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    # The CSP is per page (see web.py); these hold for every response.
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(self), camera=(), microphone=(), payment=(), usb=()")
    return response


@app.exception_handler(OutsideCoverageError)
@app.exception_handler(OverpassError)
async def _data_error(_request: Request, exc: Exception) -> JSONResponse:
    # The synchronous search path; the job path reports the same code in its status.
    status = 422 if isinstance(exc, OutsideCoverageError) else 503
    return JSONResponse(status_code=status, content={"detail": str(exc), "code": exc.code})


app.include_router(routes_search.router)
app.include_router(routes_meta.router)


@app.get("/api/disclaimer", tags=["meta"], summary="Legal notice text")
async def disclaimer() -> dict[str, str]:
    return {"text": DISCLAIMER}


# The website (web/dist) - registered last, it catches every path the API
# routers above did not claim.
app.include_router(web.router)
