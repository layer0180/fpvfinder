"""
Central configuration: paths, environment variables and the scoring weights.

Two separate concerns:
  * ``Settings``    -> technical settings (URLs, rate limits, secrets),
                       read from environment variables or the ``.env`` file.
  * ``get_config()`` -> the scoring configuration from ``config/weights.json``.
                       Reloadable at runtime and writable through the API.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.scoring.defaults import DEFAULT_CONFIG, deep_merge

# backend/app/config.py -> backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BACKEND_DIR / "config"
DATA_DIR = BACKEND_DIR / "data"
WEIGHTS_FILE = CONFIG_DIR / "weights.json"


def _load_dotenv() -> None:
    """Minimal .env loader (avoids an extra dependency)."""
    env_file = BACKEND_DIR / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Real environment variables that are already set take precedence.
        os.environ.setdefault(key, value)


_load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# Identifies the application to Nominatim and Overpass. A repository URL is an
# acceptable contact route under the OSM usage policy; an operator running this
# publicly should still replace it with their own address.
DEFAULT_USER_AGENT = "fpvfinder/0.1 (+https://github.com/Layer0180/fpvfinder)"

# Nominatim answers 403 to any User-Agent containing this, no matter what else
# is in the string - it reads as "the placeholder was never filled in".
_PLACEHOLDER_MARKERS = ("example.com", "example.org", "your.name", "dein.name")


def _sanitise_user_agent(value: str) -> tuple[str, str | None]:
    """
    Returns (usable user agent, warning or None).

    Copying .env.example verbatim used to break address search with an opaque
    403. Falling back to a working identifier keeps the feature alive and says
    what to fix, rather than failing at the first search.
    """
    candidate = (value or "").strip()
    if not candidate:
        return DEFAULT_USER_AGENT, None
    lowered = candidate.lower()
    for marker in _PLACEHOLDER_MARKERS:
        if marker in lowered:
            return (
                DEFAULT_USER_AGENT,
                f"USER_AGENT still contains the placeholder {marker!r}. Nominatim rejects "
                f"that with HTTP 403, so {DEFAULT_USER_AGENT!r} is being used instead. "
                "Set USER_AGENT to your own contact address or project URL.",
            )
    return candidate, None


def _normalise_verification(value: str) -> str:
    """
    Normalises GOOGLE_SITE_VERIFICATION to the file name Google looks for.

    Search Console shows the token in several shapes depending on where you
    copy it from - the download link, the file name, the file's own contents -
    so all three are accepted rather than making the operator guess which one
    this wants. Returns "" when unset or when the value is not a plausible
    token, because serving a wrong file is indistinguishable from serving none
    and this way a typo fails loudly at startup instead of silently in the
    Search Console.
    """
    token = (value or "").strip()
    if not token:
        return ""
    # "google-site-verification: googleabc.html" -> "googleabc.html"
    if ":" in token:
        token = token.split(":", 1)[1].strip()
    if token.endswith(".html"):
        token = token[: -len(".html")]
    if token.startswith("google"):
        token = token[len("google") :]
    # What is left must be the bare token. Google uses hex, but the exact
    # alphabet is not documented, so this only rejects the obviously wrong.
    if not token or not all(c.isalnum() or c in "-_" for c in token):
        return ""
    return f"google{token}.html"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    """Technical settings (as opposed to the scoring configuration)."""

    # --- Public deployment -------------------------------------------------
    # PUBLIC_MODE=true disables every endpoint that changes server-wide state
    # (weights, no-fly zones, cache), because on a shared instance one visitor
    # must not reconfigure the app for everyone else.
    public_mode: bool = field(default_factory=lambda: _env_bool("PUBLIC_MODE", False))

    # Only trust X-Forwarded-For when a reverse proxy actually sets it.
    # Enabling this without a proxy in front lets anyone spoof their address and
    # walk straight past the rate limits.
    trust_proxy: bool = field(default_factory=lambda: _env_bool("TRUST_PROXY", False))

    # Public base URL, used for canonical links and CORS on a real domain.
    #
    # This is the single most important setting for search engines. The static
    # pages are generated at build time with an absolute base URL baked into
    # every canonical link, hreflang, Open Graph tag and sitemap entry - and a
    # published image cannot know which domain it will be deployed under. Set
    # this and main.py rewrites those URLs on the way out.
    public_url: str = field(default_factory=lambda: _env("PUBLIC_URL"))

    # Google Search Console ownership proof, HTML-file method. Search Console
    # hands out a file named google<hash>.html; put either that name or just
    # the hash here and the app serves it with the content Google expects.
    # Empty means no such route exists at all.
    site_verification: str = field(default_factory=lambda: _env("GOOGLE_SITE_VERIFICATION"))

    # Self-maintained no-fly zones (data/airspace.geojson). Off by default:
    # the shipped file contains clearly-marked EXAMPLE geometry, and drawing
    # invented control zones on a public map is worse than drawing none. Turn
    # it on only once the file holds real zones you maintain yourself.
    airspace_enabled: bool = field(default_factory=lambda: _env_bool("AIRSPACE_ENABLED", False))

    # --- Request limits ----------------------------------------------------
    # Memory scales with the square of the radius. Measured on this codebase:
    #   2.5 km -> ~40 MiB      5 km -> ~240 MiB      10 km -> ~1 GiB
    # Pick this to fit the container, and give the process headroom on top.
    max_radius_km: float = field(default_factory=lambda: _env_float("MAX_RADIUS_KM", 20.0))
    min_spacing_m: float = field(default_factory=lambda: _env_float("MIN_SPACING_M", 50.0))
    max_results: int = field(default_factory=lambda: _env_int("MAX_RESULTS", 2000))

    # How many searches may run at once, and how many may queue behind them.
    search_max_concurrent: int = field(default_factory=lambda: _env_int("SEARCH_MAX_CONCURRENT", 2))
    search_max_queued: int = field(default_factory=lambda: _env_int("SEARCH_MAX_QUEUED", 8))

    # --- Rate limits (burst / refill window in seconds) --------------------
    rate_search_burst: int = field(default_factory=lambda: _env_int("RATE_SEARCH_BURST", 5))
    rate_search_per_s: float = field(default_factory=lambda: _env_float("RATE_SEARCH_PER_S", 300.0))
    rate_geocode_burst: int = field(default_factory=lambda: _env_int("RATE_GEOCODE_BURST", 20))
    rate_geocode_per_s: float = field(default_factory=lambda: _env_float("RATE_GEOCODE_PER_S", 120.0))

    # --- Donations / legal pages -------------------------------------------
    # Empty means the button is simply not rendered.
    donate_url: str = field(default_factory=lambda: _env("DONATE_URL"))
    donate_label: str = field(default_factory=lambda: _env("DONATE_LABEL", "Buy me a coffee"))
    # Where the legal pages point people. The repository doubles as the contact
    # route (issues), so no personal details have to be published.
    project_url: str = field(
        default_factory=lambda: _env("PROJECT_URL", "https://github.com/Layer0180/fpvfinder")
    )
    # Optional and empty by default - only used if a template asks for it.
    contact_email: str = field(default_factory=lambda: _env("CONTACT_EMAIL"))

    # --- Overpass ----------------------------------------------------------
    # Comma separated list of instances. If one fails (429/504), the next retry
    # uses the following one. The main public instance is regularly overloaded,
    # which makes the alternatives important.
    overpass_urls: list[str] = field(
        default_factory=lambda: [
            u.strip()
            for u in _env(
                "OVERPASS_URLS",
                "https://overpass-api.de/api/interpreter,"
                "https://overpass.kumi.systems/api/interpreter,"
                "https://overpass.private.coffee/api/interpreter",
            ).split(",")
            if u.strip()
        ]
    )
    overpass_timeout_s: float = field(default_factory=lambda: _env_float("OVERPASS_TIMEOUT_S", 240.0))
    # Minimum gap between two Overpass requests (politeness plus rate limiting)
    overpass_min_interval_s: float = field(default_factory=lambda: _env_float("OVERPASS_MIN_INTERVAL_S", 1.5))
    overpass_max_retries: int = field(default_factory=lambda: _env_int("OVERPASS_MAX_RETRIES", 4))
    # Edge length of one cache tile in degrees. Smaller = finer cache but more
    # requests. 0.1 degrees is roughly 11 km north to south.
    overpass_tile_deg: float = field(default_factory=lambda: _env_float("OVERPASS_TILE_DEG", 0.1))
    overpass_cache_ttl_days: float = field(default_factory=lambda: _env_float("OVERPASS_CACHE_TTL_DAYS", 30.0))

    # --- Nominatim (geocoding) ---------------------------------------------
    nominatim_url: str = field(
        default_factory=lambda: _env("NOMINATIM_URL", "https://nominatim.openstreetmap.org")
    )
    # Nominatim requires a User-Agent that identifies the application. Anything
    # containing "example.com" is rejected outright with 403 (verified against
    # the live service), because that means a placeholder was never replaced -
    # see _sanitise_user_agent below.
    user_agent: str = field(default_factory=lambda: _env("USER_AGENT", DEFAULT_USER_AGENT))

    # --- Strava heatmap ----------------------------------------------------
    # Strava serves heatmap tiles up to and including zoom 12 WITHOUT any login
    # (~25 m/pixel at 48 degrees north, which is plenty for a 150 m grid).
    # Above that the server responds with:
    #   "authentication is now required for data access beyond zoom level 12"
    # So the public endpoint is the default and cookies are an optional upgrade
    # to higher zoom levels.
    strava_tile_url_public: str = field(
        default_factory=lambda: _env(
            "STRAVA_TILE_URL_PUBLIC",
            "https://heatmap-external-a.strava.com/tiles/{activity}/{color}/{z}/{x}/{y}.png?px=256",
        )
    )
    # Optional: cookie string from a logged-in browser, for zoom > 12.
    strava_cookies: str = field(default_factory=lambda: _env("STRAVA_HEATMAP_COOKIES"))
    strava_tile_url: str = field(
        default_factory=lambda: _env(
            "STRAVA_TILE_URL",
            "https://heatmap-external-a.strava.com/tiles-auth/{activity}/{color}/{z}/{x}/{y}.png?px=256",
        )
    )
    # Highest zoom level the public endpoint will serve.
    strava_public_max_zoom: int = field(default_factory=lambda: _env_int("STRAVA_PUBLIC_MAX_ZOOM", 12))

    # --- Paths -------------------------------------------------------------
    data_dir: Path = DATA_DIR
    cache_db: Path = DATA_DIR / "cache.sqlite"
    airspace_file: Path = DATA_DIR / "airspace.geojson"
    # Imprint / privacy markdown, editable without rebuilding the image.
    content_dir: Path = BACKEND_DIR / "content"

    # --- CORS --------------------------------------------------------------
    cors_origins: list[str] = field(
        default_factory=lambda: [
            o.strip()
            for o in _env("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
            if o.strip()
        ]
    )

    @property
    def strava_configured(self) -> bool:
        return bool(self.strava_cookies)

    @property
    def overpass_url(self) -> str:
        """Primary instance - for display and health output only."""
        return self.overpass_urls[0] if self.overpass_urls else ""


SETTINGS = Settings()

# Applied after construction so the warning can be surfaced at startup rather
# than swallowed inside a field factory.
SETTINGS.user_agent, USER_AGENT_WARNING = _sanitise_user_agent(SETTINGS.user_agent)

# When the app is served from its own domain, that origin has to be allowed too.
# (In the single-container setup the frontend is same-origin, so this only
# matters if somebody runs the UI separately.)
if SETTINGS.public_url and SETTINGS.public_url not in SETTINGS.cors_origins:
    SETTINGS.cors_origins.append(SETTINGS.public_url.rstrip("/"))

SETTINGS.site_verification = _normalise_verification(SETTINGS.site_verification)

# Create the directories up front so nothing fails later on.
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS.data_dir.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Scoring configuration
# ---------------------------------------------------------------------------
_config_lock = threading.Lock()
_config_cache: dict[str, Any] | None = None


def load_config(force: bool = False) -> dict[str, Any]:
    """
    Loads ``config/weights.json`` and merges it on top of ``DEFAULT_CONFIG``.

    If the file does not exist it is created from the defaults, so you always
    have a complete, editable template to start from.
    """
    global _config_cache
    with _config_lock:
        if _config_cache is not None and not force:
            return _config_cache

        user_cfg: dict[str, Any] = {}
        if WEIGHTS_FILE.exists():
            try:
                user_cfg = json.loads(WEIGHTS_FILE.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                # Better to carry on with the defaults than to kill the backend.
                print(f"[config] WARNING: {WEIGHTS_FILE.name} is not valid JSON ({exc}) - using defaults.")
                user_cfg = {}
        else:
            WEIGHTS_FILE.write_text(
                json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        cfg = deep_merge(DEFAULT_CONFIG, user_cfg)
        cfg = _auto_enable_optional_sources(cfg)
        _config_cache = cfg
        return cfg


def _auto_enable_optional_sources(cfg: dict[str, Any]) -> dict[str, Any]:
    """
    Enables optional data sources automatically once they become available,
    so nothing has to be switched on in two places at once.
    """
    # Strava no longer needs any configuration - the public endpoint always
    # works. The zoom level is clamped at runtime instead.

    # Population raster: active if the file exists AND rasterio is installed.
    pop = cfg.get("population", {})
    raster_path = BACKEND_DIR / str(pop.get("raster_path", ""))
    if raster_path.exists():
        try:
            import rasterio  # noqa: F401

            pop["enabled"] = True
            # Give it a sensible starting weight if the user still has it at 0.
            comp = cfg["solitude"]["components"]["population"]
            if comp.get("weight", 0.0) <= 0.0:
                comp["weight"] = 0.15
        except ImportError:
            print("[config] Note: population raster found, but 'rasterio' is missing (pip install rasterio).")
            pop["enabled"] = False
    return cfg


def save_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Writes the configuration to ``config/weights.json`` and clears the cache."""
    global _config_cache
    with _config_lock:
        WEIGHTS_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        _config_cache = None
    return load_config(force=True)


def get_config() -> dict[str, Any]:
    """Convenience accessor for the current configuration."""
    return load_config()
