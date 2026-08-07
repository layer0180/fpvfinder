"""
FastAPI entry point.

Start it from the ``backend`` directory:
    uvicorn app.main:app --reload --port 8000

The interactive API docs are then at http://localhost:8000/docs
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import routes_legal, routes_meta, routes_search
from app.config import SETTINGS, USER_AGENT_WARNING, load_config

DISCLAIMER = (
    "This app is a research tool built on freely available OpenStreetMap data. "
    "It does NOT replace an official airspace and legal check. Before every flight you "
    "must verify the EU drone regulation (2019/947), the applicable national rules, "
    "current NOTAMs and geographical UAS zones yourself. Land use and protected area "
    "data from OSM may be incomplete or out of date."
)

app = FastAPI(
    title="FPV Flying Spot Finder",
    version=__version__,
    description=(
        "Finds locations for FPV flights with few people around and good flying "
        "conditions.\n\n**Legal notice:** " + DISCLAIMER
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=SETTINGS.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_search.router)
app.include_router(routes_meta.router)
app.include_router(routes_legal.router)


@app.on_event("startup")
async def on_startup() -> None:
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
    print(f"[fpvfinder] overpass: {SETTINGS.overpass_url}")
    print(f"[fpvfinder] cache:    {SETTINGS.cache_db}")
    strava_mode = "off"
    if config["strava"].get("enabled", True):
        strava_mode = f"zoom {config['strava'].get('zoom', 12)}"
        strava_mode += " (+cookies)" if SETTINGS.strava_configured else " (public)"
    print(f"[fpvfinder] strava:   {strava_mode}")
    print(f"[fpvfinder] raster:   {'on' if config['population'].get('enabled') else 'off'}")
    print(f"[fpvfinder] zones:    {'on' if SETTINGS.airspace_enabled else 'off'}")

    # SEO state. Both of these fail silently and invisibly when wrong - a
    # sitemap full of localhost URLs still serves with a 200 - so say it here
    # where it is seen on every boot, rather than leaving it to Search Console
    # to report a week later.
    if FRONTEND_DIST.exists():
        effective = SERVE_URL if REWRITE_URLS else BAKED_URL
        print(f"[fpvfinder] site:     {effective}{' (rewritten from ' + BAKED_URL + ')' if REWRITE_URLS else ''}")
        if effective.startswith("http://localhost"):
            print(
                "[fpvfinder] WARNING:  canonical links and sitemap.xml point at localhost. "
                "Set PUBLIC_URL to the public address or search engines will index nothing."
            )
        print(
            f"[fpvfinder] gsc:      /{SETTINGS.site_verification}"
            if SETTINGS.site_verification
            else "[fpvfinder] gsc:      no verification file (set GOOGLE_SITE_VERIFICATION)"
        )


@app.get("/api/disclaimer", tags=["meta"], summary="Legal notice text")
async def disclaimer() -> dict[str, str]:
    return {"text": DISCLAIMER}


# ---------------------------------------------------------------------------
# Optionally serve the built frontend (npm run build -> frontend/dist)
# ---------------------------------------------------------------------------
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    # -- Absolute URLs -----------------------------------------------------
    # frontend/scripts/build-site.mjs bakes SITE_URL into every canonical link,
    # hreflang, og:url and sitemap entry, because those are meaningless as
    # relative paths. That is a problem for a published image: it is built once
    # and deployed under whatever domain the operator has, so the baked value is
    # wrong for everyone but whoever ran the build. Google is unforgiving here -
    # a sitemap listing localhost is rejected outright, and canonical tags
    # pointing at another host deindex the site.
    #
    # So PUBLIC_URL wins at serve time. The generator records what it baked as
    # the first line of robots.txt ("# <url>"); that comment exists for exactly
    # this purpose, so do not remove it there without changing this.
    BUILD_FALLBACK_URL = "http://localhost:8000"

    def _baked_base_url() -> str:
        robots = FRONTEND_DIST / "robots.txt"
        if robots.exists():
            first = robots.read_text(encoding="utf-8").partition("\n")[0].strip()
            if first.startswith("#") and "://" in first:
                return first.lstrip("#").strip().rstrip("/")
        return BUILD_FALLBACK_URL

    BAKED_URL = _baked_base_url()
    SERVE_URL = SETTINGS.public_url.rstrip("/")
    REWRITE_URLS = bool(SERVE_URL) and SERVE_URL != BAKED_URL

    _text_cache: dict[str, bytes] = {}

    def _text_file(filename: str) -> bytes:
        """Reads a text asset, rewriting the base URL, and caches the result."""
        cached = _text_cache.get(filename)
        if cached is not None:
            return cached
        target = FRONTEND_DIST / filename
        if not target.exists():
            raise HTTPException(status_code=404, detail=f"{filename} was not built.")
        body = target.read_text(encoding="utf-8")
        if REWRITE_URLS:
            body = body.replace(BAKED_URL, SERVE_URL)
        encoded = body.encode("utf-8")
        _text_cache[filename] = encoded
        return encoded

    # Clean URL -> file. The static marketing pages are generated by
    # frontend/scripts/build-site.mjs; the app is a separate entry point.
    #
    # /app is deliberately NOT the landing page: search engines and inbound
    # links should arrive on a document that actually has text, and the tool
    # renders nothing without JavaScript.
    PAGES = {
        "/": "index.html",
        "/faq": "faq.html",
        "/en": "en/index.html",
        "/en/": "en/index.html",
        "/en/faq": "en/faq.html",
        "/app": "app.html",
    }

    # Files served straight from the root of the site. The third field says
    # whether the base URL has to be rewritten - robots.txt and sitemap.xml
    # are made of absolute URLs, the rest never mentions one.
    ROOT_FILES = {
        "/robots.txt": ("robots.txt", "text/plain; charset=utf-8", True),
        "/sitemap.xml": ("sitemap.xml", "application/xml", True),
        "/site.css": ("site.css", "text/css", False),
        "/favicon.svg": ("favicon.svg", "image/svg+xml", False),
        "/og-image.png": ("og-image.png", "image/png", False),
    }

    def _register_page(route: str, filename: str) -> None:
        async def handler() -> Response:
            return Response(
                content=_text_file(filename),
                media_type="text/html; charset=utf-8",
            )

        app.get(route, include_in_schema=False)(handler)

    for _route, _file in PAGES.items():
        _register_page(_route, _file)

    def _register_file(route: str, filename: str, media_type: str, rewrite: bool) -> None:
        # Hashed assets are immutable; these are not, so keep the TTL short.
        headers = {"Cache-Control": "public, max-age=3600"}

        async def handler() -> Response:
            if rewrite:
                return Response(
                    content=_text_file(filename),
                    media_type=media_type,
                    headers=headers,
                )
            target = FRONTEND_DIST / filename
            if not target.exists():
                raise HTTPException(status_code=404, detail=f"{filename} was not built.")
            return FileResponse(target, media_type=media_type, headers=headers)

        app.get(route, include_in_schema=False)(handler)

    for _route, (_file, _mime, _rewrite) in ROOT_FILES.items():
        _register_file(_route, _file, _mime, _rewrite)

    # -- Google Search Console ownership proof ------------------------------
    # The HTML-file method, served from configuration rather than from a file
    # committed to the repository. Two reasons: the token is per-property, so
    # it does not belong in an image that other people run, and this way
    # verification needs an environment variable rather than a rebuild.
    #
    # Google fetches the exact path it gave you and expects the file to contain
    # its own name on that one line. Anything else counts as unverified.
    if SETTINGS.site_verification:
        _verification_body = f"google-site-verification: {SETTINGS.site_verification}".encode()

        @app.get(f"/{SETTINGS.site_verification}", include_in_schema=False)
        async def google_site_verification() -> Response:
            return Response(content=_verification_body, media_type="text/html; charset=utf-8")

else:

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        # In development the frontend runs on the Vite dev server at port 5173.
        return RedirectResponse("/docs")
