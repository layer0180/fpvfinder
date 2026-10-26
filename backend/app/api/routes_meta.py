"""Configuration, geocoding, no-fly zones and cache management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from app.config import SETTINGS, get_config, save_config
from app.limits import GEOCODE_LIMITER, enforce, limits_summary, require_writable
from app.models import ConfigUpdate, GeocodeResult
from app.scoring.defaults import DEFAULT_CONFIG, deep_merge
from app.scoring.labels import CATEGORY_LABELS, COMPONENT_LABELS, DISTANCE_LABELS
from app.services.airspace import load_airspace, save_airspace
from app.services.cache import OverpassCache
from app.services.geocoding import GeocodeError, geocode, reverse_geocode
from app.services.spaceweather import current_kp

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health", summary="Status information")
async def health() -> dict[str, Any]:
    config = get_config()
    return {
        "status": "ok",
        "overpass_url": SETTINGS.overpass_url,
        # The public heatmap endpoint needs no login - cookies are only an
        # upgrade to higher zoom levels.
        "map_style_url": SETTINGS.map_style_url,
        "time_profiles": list(config["time_profiles"].keys()),
        "strava_enabled": bool(SETTINGS.strava_enabled and config["strava"].get("enabled", True)),
        "strava_cookies_present": SETTINGS.strava_configured,
        "strava_public_max_zoom": SETTINGS.strava_public_max_zoom,
        "strava_zoom": int(config["strava"].get("zoom", 12)),
        # Tile template for the map layer, with only {z}/{x}/{y} left for
        # Leaflet to fill in. The browser fetches these DIRECTLY from Strava -
        # they never touch this server - tile bandwidth is by far the largest
        # traffic item, so proxying it would put all of it on the host.
        "strava_tile_url": SETTINGS.strava_tile_url_public.replace(
            "{activity}", str(config["strava"].get("activity", "all"))
        ).replace("{color}", str(config["strava"].get("color", "hot"))),
        "population_enabled": bool(config["population"].get("enabled")),
        "airspace_enabled": SETTINGS.airspace_enabled,
        "airspace_features": len(load_airspace().get("features", [])) if SETTINGS.airspace_enabled else 0,
        "limits": limits_summary(),
        # Rendered by the frontend footer; empty means "do not show".
        "donate_url": SETTINGS.donate_url,
        "donate_label": SETTINGS.donate_label,
    }


@router.get("/config", summary="Current scoring configuration")
async def read_config() -> dict[str, Any]:
    return {
        "config": get_config(),
        "labels": {
            "categories": CATEGORY_LABELS,
            "components": COMPONENT_LABELS,
            "distances": DISTANCE_LABELS,
        },
    }


@router.put("/config", summary="Save the configuration")
async def write_config(update: ConfigUpdate) -> dict[str, Any]:
    """
    Writes to ``config/weights.json``.

    ``merge=True`` (the default) only applies the keys you send, which is handy
    for changing individual weights from the UI.
    """
    require_writable("Saving the configuration")
    base = get_config() if update.merge else DEFAULT_CONFIG
    merged = deep_merge(base, update.config)
    return {"config": save_config(merged)}


@router.post("/config/reset", summary="Reset the configuration to the defaults")
async def reset_config() -> dict[str, Any]:
    require_writable("Resetting the configuration")
    return {"config": save_config(dict(DEFAULT_CONFIG))}


@router.get("/geocode", response_model=list[GeocodeResult], summary="Place search (Photon, Nominatim)")
async def geocode_endpoint(
    request: Request,
    q: str = Query(..., min_length=2, max_length=200, description="Place name or address"),
    limit: int = Query(5, ge=1, le=10),
    lang: str = Query("de", pattern="^(de|en)$"),
    suggest: bool = Query(False, description="Type-ahead lookup: Photon only, never Nominatim"),
) -> list[GeocodeResult]:
    enforce(GEOCODE_LIMITER, request)
    try:
        results = await geocode(q, limit=limit, lang=lang, suggest=suggest)
    except GeocodeError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "geocoder_unavailable", "message": f"Place search is unavailable right now ({exc})."},
        ) from exc
    return [GeocodeResult(**r) for r in results]


@router.get("/reverse", summary="Short place name for a coordinate")
async def reverse_endpoint(
    request: Request,
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    lang: str = Query("de", pattern="^(de|en)$"),
) -> dict[str, str]:
    enforce(GEOCODE_LIMITER, request)
    return {"label": await reverse_geocode(lat, lon, lang=lang)}


@router.get("/kp", summary="Planetary Kp index for the next hours (GPS quality)")
async def kp_endpoint() -> dict[str, float | None]:
    return {"kp": await current_kp()}


@router.get("/airspace", summary="Custom no-fly zones as GeoJSON")
async def read_airspace() -> dict[str, Any]:
    # An empty collection rather than a 404: the frontend can then render
    # "nothing" without special-casing the disabled state.
    if not SETTINGS.airspace_enabled:
        return {"type": "FeatureCollection", "features": []}
    return load_airspace()


@router.put("/airspace", summary="Save the no-fly zones")
async def write_airspace(collection: dict[str, Any]) -> dict[str, Any]:
    require_writable("Editing the no-fly zones")
    if not SETTINGS.airspace_enabled:
        raise HTTPException(
            status_code=409,
            detail="Custom no-fly zones are disabled. Set AIRSPACE_ENABLED=true to use them.",
        )
    if collection.get("type") != "FeatureCollection":
        raise HTTPException(status_code=400, detail="A GeoJSON FeatureCollection is expected.")
    save_airspace(collection)
    return {"saved": len(collection.get("features", []))}


@router.get("/cache/stats", summary="Overpass cache statistics")
async def cache_stats() -> dict[str, Any]:
    return OverpassCache(SETTINGS.cache_db).stats()


@router.delete("/cache", summary="Clear the Overpass cache")
async def clear_cache(older_than_days: float | None = Query(None, ge=0)) -> dict[str, int]:
    # Wiping the cache would force every later visitor to re-hit Overpass.
    require_writable("Clearing the cache")
    cache = OverpassCache(SETTINGS.cache_db)
    deleted = cache.clear(None if older_than_days is None else older_than_days * 86400)
    return {"deleted": deleted}
