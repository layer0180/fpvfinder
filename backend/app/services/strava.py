"""
The Strava heatmap as an additional layer.

Why this is worth having at all: OSM only tells you WHAT an area is - not how
heavily it is used. A farm track between two fields looks unremarkable in OSM
but may be the standard after-work loop for every road cyclist in the area. The
(aggregated, anonymised) Strava tracks capture exactly that real-world movement.

Mechanics: for the duration of a search we fetch the heatmap tiles covering the
search area and read the pixel intensity at the position of every candidate
point.

## Why this still happens on the server

The heatmap is used for two different things, and only one of them can run in
the browser:

  * **The map layer** you see is fetched by the browser straight from Strava.
    It never touches this server (see MapView.jsx). That is where nearly all
    the bandwidth is.
  * **The score component** needs the actual pixel values. Reading pixels out
    of a cross-origin image requires CORS, and Strava's tile endpoint sends no
    ``Access-Control-Allow-Origin`` header, so a browser canvas would be
    tainted and ``getImageData()`` would throw. Sampling therefore has to
    happen here.

The volume is small and bounded by the search area: 9 tiles for a 5 km radius,
about 20 for 20 km, ~23 KiB each.

## Nothing is stored

Tiles are held only in the local variable of the search that fetched them, and
each tile is requested at most once per search (points are grouped by tile
before fetching). There is deliberately no disk or cross-request cache: Strava's
terms do not permit retaining their data, and with the map layer served directly
to the browser a cache would buy almost nothing anyway.

## Access: two tiers

1. **Public (the default, no login at all)** - up to and including zoom 12.
   Above that the server responds with
   "authentication is now required for data access beyond zoom level 12".
   Zoom 12 works out to roughly 25 m/pixel at 48 degrees north, which is plenty
   for a 150 m grid.

2. **Authenticated (optional)** - higher zoom levels via the ``tiles-auth``
   path with CloudFront cookies from a logged-in browser
   (``STRAVA_HEATMAP_COOKIES``). Note that Strava moves these endpoints around
   regularly. If authentication fails, this module falls back to tier 1
   automatically, so a search always completes.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass
from typing import Any

import httpx
import numpy as np

from app.config import SETTINGS
from app.services.spatial import deg2pixel

TILE_SIZE = 256

# Matches the sentinel the scoring uses for "this kind of thing is not around".
FAR_AWAY_M = 50_000.0


@dataclass
class StravaSample:
    """Both readings the scoring needs, per candidate point."""

    intensity: np.ndarray   # 0..1 at the point itself
    distance_m: np.ndarray  # metres to the nearest route above the threshold

# Browser user agent: Strava serves generic clients little or nothing.
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class _AuthProbe:
    """
    Process-wide result of the one-off authentication check.

    Stops every search from retrying against a broken or expired cookie set.
    """

    checked: bool = False
    usable: bool = False
    detail: str = ""

    @classmethod
    def reset(cls) -> None:
        cls.checked = False
        cls.usable = False
        cls.detail = ""


class StravaHeatmap:
    """Fetches and samples Strava heatmap tiles."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.cfg = config.get("strava", {})
        self.zoom = int(self.cfg.get("zoom", 12))
        self.activity = str(self.cfg.get("activity", "all"))
        self.color = str(self.cfg.get("color", "hot"))
        self.sample_radius = int(self.cfg.get("sample_radius_px", 1))
        self.gamma = float(self.cfg.get("intensity_gamma", 1.0))
        self.noise_floor = float(self.cfg.get("noise_floor", 0.35))
        # From this intensity upwards a pixel counts as "a route people use"
        # when measuring the distance to the nearest busy trail.
        self.activity_threshold = float(self.cfg.get("activity_threshold", 0.4))
        # How far out to look for one. Beyond this the distance ramp is
        # saturated anyway, so searching further would only cost tiles.
        self.search_radius_m = float(self.cfg.get("search_radius_m", 800.0))
        self.last_error: str | None = None
        self.notes: list[str] = []

    @property
    def enabled(self) -> bool:
        """The public endpoint requires no configuration."""
        return bool(self.cfg.get("enabled", True))

    @property
    def public_max_zoom(self) -> int:
        return int(SETTINGS.strava_public_max_zoom)

    # -- public API ---------------------------------------------------------
    async def resolve_zoom(self) -> int:
        """
        Clamps the zoom level to what is actually retrievable.

        Without (working) cookies, ``public_max_zoom`` is the ceiling. The
        authentication check runs exactly once per process.
        """
        if self.zoom <= self.public_max_zoom:
            return self.zoom

        if not SETTINGS.strava_configured:
            self.notes.append(
                f"Strava heatmap: zoom {self.zoom} requires a login - "
                f"using the public zoom {self.public_max_zoom} instead."
            )
            self.zoom = self.public_max_zoom
            return self.zoom

        if not _AuthProbe.checked:
            await self._probe_auth()

        if not _AuthProbe.usable:
            self.notes.append(
                f"Strava login not usable ({_AuthProbe.detail}) - "
                f"using the public zoom {self.public_max_zoom} instead."
            )
            self.zoom = self.public_max_zoom
        return self.zoom

    def metres_per_pixel(self, lat: float) -> float:
        """Ground resolution of one heatmap pixel at this latitude and zoom."""
        return 156543.03392 * math.cos(math.radians(lat)) / (2**self.zoom)

    async def sample(self, lats: np.ndarray, lons: np.ndarray) -> "StravaSample":
        """
        Two readings per point:

        * ``intensity`` - how busy it is exactly here (0 = nothing recorded).
        * ``distance_m`` - how far to the nearest *used* route, so that a spot
          200 m from a busy trail can score worse than one 300 m away.
          ``FAR_AWAY_M`` when nothing is within range.

        Falls back silently to "no activity anywhere" on any problem - the
        heatmap is a bonus signal, not a requirement.
        """
        n = len(lats)
        empty = StravaSample(np.zeros(n), np.full(n, FAR_AWAY_M))
        if not self.enabled or n == 0:
            return empty

        await self.resolve_zoom()

        # Global pixel coordinates for every point.
        pixel_x = np.empty(n)
        pixel_y = np.empty(n)
        for i in range(n):
            pixel_x[i], pixel_y[i] = deg2pixel(float(lats[i]), float(lons[i]), self.zoom, TILE_SIZE)

        m_per_px = self.metres_per_pixel(float(np.mean(lats)))
        # Look outwards only as far as the ramp still cares about; beyond
        # search_radius_m the score is saturated anyway.
        radius_px = max(1, int(math.ceil(self.search_radius_m / max(m_per_px, 1e-6))))

        mosaic, origin = await self._build_mosaic(pixel_x, pixel_y, radius_px)
        if mosaic is None:
            return empty

        local_x = (pixel_x - origin[0]).astype(int)
        local_y = (pixel_y - origin[1]).astype(int)

        intensity = np.array(
            [self._sample_pixel(mosaic, int(local_x[i]), int(local_y[i])) for i in range(n)]
        )

        # Anything at or above the threshold counts as "a route people use".
        busy = mosaic >= self.activity_threshold
        distance_px = _nearest_true_distance(busy, local_x, local_y, radius_px)
        distance_m = np.where(np.isfinite(distance_px), distance_px * m_per_px, FAR_AWAY_M)

        return StravaSample(np.clip(intensity, 0.0, 1.0), distance_m)

    async def _build_mosaic(
        self, pixel_x: np.ndarray, pixel_y: np.ndarray, pad_px: int
    ) -> tuple[np.ndarray | None, tuple[int, int]]:
        """
        Stitches the tiles covering all points (plus ``pad_px``) into one array.

        The padding matters: without it a point near the edge would report "no
        activity nearby" simply because the neighbouring tile was never
        fetched. Only the tiles actually needed are requested - usually the
        padding stays inside tiles we were fetching anyway.
        """
        x0 = int(math.floor((pixel_x.min() - pad_px) / TILE_SIZE))
        x1 = int(math.floor((pixel_x.max() + pad_px) / TILE_SIZE))
        y0 = int(math.floor((pixel_y.min() - pad_px) / TILE_SIZE))
        y1 = int(math.floor((pixel_y.max() + pad_px) / TILE_SIZE))

        width = (x1 - x0 + 1) * TILE_SIZE
        height = (y1 - y0 + 1) * TILE_SIZE
        # Guard against a pathological request eating memory.
        if width * height > 40_000_000:
            self.notes.append(
                "Strava heatmap skipped: the search area would need too large a tile mosaic."
            )
            return None, (0, 0)

        mosaic = np.zeros((height, width), dtype=float)
        got_any = False
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                array = await self._tile_array(tx, ty)
                if array is None:
                    continue
                got_any = True
                oy = (ty - y0) * TILE_SIZE
                ox = (tx - x0) * TILE_SIZE
                mosaic[oy:oy + TILE_SIZE, ox:ox + TILE_SIZE] = array

        if not got_any:
            return None, (0, 0)
        return mosaic, (x0 * TILE_SIZE, y0 * TILE_SIZE)

    # -- internals ----------------------------------------------------------
    def _tile_url(self, z: int, x: int, y: int) -> tuple[str, bool]:
        """
        Returns (URL, with_auth) for a tile.

        Up to ``public_max_zoom`` we deliberately ALWAYS use the public path:
        it is stable, whereas the authenticated path moves around regularly.
        """
        if z <= self.public_max_zoom:
            return (
                SETTINGS.strava_tile_url_public.format(
                    activity=self.activity, color=self.color, z=z, x=x, y=y
                ),
                False,
            )
        return (
            SETTINGS.strava_tile_url.format(activity=self.activity, color=self.color, z=z, x=x, y=y),
            True,
        )

    def _headers(self, with_auth: bool) -> dict[str, str]:
        headers = {
            "User-Agent": BROWSER_UA,
            "Referer": "https://www.strava.com/heatmap",
            "Accept": "image/avif,image/webp,image/png,*/*",
        }
        if with_auth and SETTINGS.strava_cookies:
            headers["Cookie"] = SETTINGS.strava_cookies
        return headers

    async def _probe_auth(self) -> None:
        """One-off test fetch of a tile at the requested zoom level."""
        _AuthProbe.checked = True
        # An arbitrary tile in central Europe - only the status code matters.
        z = self.zoom
        x, y = 4313 * 2 ** (z - 13), 2828 * 2 ** (z - 13)
        url, _ = self._tile_url(z, int(x), int(y))
        try:
            async with httpx.AsyncClient(
                timeout=20.0, headers=self._headers(True), follow_redirects=True
            ) as client:
                resp = await client.get(url)
            if resp.status_code == 200 and "image" in (resp.headers.get("content-type") or ""):
                _AuthProbe.usable = True
                return
            body = (resp.text or "")[:120].replace("\n", " ").strip()
            _AuthProbe.detail = f"HTTP {resp.status_code}: {body}" if body else f"HTTP {resp.status_code}"
        except httpx.HTTPError as exc:
            _AuthProbe.detail = f"{type(exc).__name__}: {exc}"

    async def _tile_bytes(self, z: int, x: int, y: int) -> bytes | None:
        """
        Fetches one tile. Nothing is written to disk and nothing is kept between
        searches - see the module docstring for why.
        """
        url, with_auth = self._tile_url(z, x, y)
        try:
            async with httpx.AsyncClient(
                timeout=20.0, headers=self._headers(with_auth), follow_redirects=True
            ) as client:
                resp = await client.get(url)

            if resp.status_code == 404:
                # No data for this tile = no activity there.
                return None
            if resp.status_code in (401, 403):
                body = (resp.text or "")[:120].replace("\n", " ").strip()
                self.last_error = f"Strava tile rejected (HTTP {resp.status_code}): {body}"
                return None
            resp.raise_for_status()
            if "image" not in (resp.headers.get("content-type") or ""):
                self.last_error = "Strava did not return an image."
                return None
            return resp.content
        except httpx.HTTPError as exc:
            self.last_error = f"Could not load Strava tile: {exc}"
            return None

    async def _tile_array(self, tx: int, ty: int) -> np.ndarray | None:
        """One tile as an (H, W) intensity array in 0..1."""
        data = await self._tile_bytes(self.zoom, tx, ty)
        if not data:
            return None
        try:
            from PIL import Image

            image = Image.open(io.BytesIO(data)).convert("RGBA")
            arr = np.asarray(image, dtype=float)
        except Exception as exc:  # Pillow raises a variety of error types
            self.last_error = f"Could not decode tile: {exc}"
            return None

        alpha = arr[..., 3] / 255.0
        # The heatmap encodes intensity primarily through opacity. If a tile is
        # fully opaque, fall back to brightness instead.
        if float(alpha.max()) <= 0.01:
            return np.zeros(arr.shape[:2])
        if float(alpha.min()) > 0.99:
            intensity = arr[..., :3].max(axis=-1) / 255.0
        else:
            intensity = alpha

        # Subtract the noise floor and rescale.
        #
        # Why this is necessary: Strava draws even a SINGLE recorded activity at
        # an alpha of roughly 0.2-0.4. In rural tiles about a third of all
        # pixels sit on exactly that plateau, which only means "somebody walked
        # here once" and is worthless as a signal. Without cutting it off,
        # nearly every candidate point would be penalised. "Actually busy"
        # starts above that plateau.
        floor = min(max(self.noise_floor, 0.0), 0.95)
        intensity = (np.clip(intensity, 0.0, 1.0) - floor) / max(1.0 - floor, 1e-6)
        return np.clip(intensity, 0.0, 1.0) ** self.gamma

    def _sample_pixel(self, array: np.ndarray, x: int, y: int) -> float:
        """Maximum within the radius - still hits the trace if slightly offset."""
        r = max(self.sample_radius, 0)
        h, w = array.shape
        x0, x1 = max(0, x - r), min(w, x + r + 1)
        y0, y1 = max(0, y - r), min(h, y + r + 1)
        if x0 >= x1 or y0 >= y1:
            return 0.0
        return float(array[y0:y1, x0:x1].max())


def _nearest_true_distance(
    mask: np.ndarray, xs: np.ndarray, ys: np.ndarray, radius_px: int
) -> np.ndarray:
    """
    For each query pixel, the distance to the nearest ``True`` cell in pixels
    (``inf`` if none within ``radius_px``).

    Why not a full distance transform: an exact Euclidean transform would mean
    adding scipy, and we do not need a value for every one of the ~600,000
    mosaic pixels - only for the few thousand candidate points. So the offsets
    within the radius are walked in order of increasing distance and the first
    hit wins. That is exact to the pixel grid, and each step is one vectorised
    lookup over the points still unresolved, which shrink away quickly.
    """
    n = len(xs)
    result = np.full(n, np.inf)
    if n == 0 or not mask.any():
        return result

    height, width = mask.shape

    # Offsets inside the circle, nearest first.
    offsets = []
    for dy in range(-radius_px, radius_px + 1):
        for dx in range(-radius_px, radius_px + 1):
            d = math.hypot(dx, dy)
            if d <= radius_px:
                offsets.append((d, dy, dx))
    offsets.sort(key=lambda o: o[0])

    pending = np.arange(n)
    for d, dy, dx in offsets:
        if pending.size == 0:
            break
        yy = ys[pending] + dy
        xx = xs[pending] + dx
        inside = (yy >= 0) & (yy < height) & (xx >= 0) & (xx < width)
        if not inside.any():
            continue
        hit = np.zeros(pending.size, dtype=bool)
        hit[inside] = mask[yy[inside], xx[inside]]
        if hit.any():
            result[pending[hit]] = d
            pending = pending[~hit]
    return result


def recommended_zoom(radius_m: float, max_zoom: int) -> int:
    """
    Picks a zoom level that keeps the tile count manageable.

    At zoom 12 one tile is about 6.5 km wide (at 50 degrees north), so a 20 km
    radius would need ~50 tiles - hence one step coarser for large radii.
    ``max_zoom`` is the ceiling coming from the configuration.
    """
    if radius_m <= 8000:
        zoom = max_zoom
    elif radius_m <= 15000:
        zoom = max_zoom - 1
    else:
        zoom = max_zoom - int(math.ceil(math.log2(radius_m / 15000))) - 1
    return max(9, min(max_zoom, zoom))
