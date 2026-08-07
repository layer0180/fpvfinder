"""
Protection for a publicly reachable instance.

Three separate mechanisms, because they guard against different things:

  * **Per-client rate limits** (token bucket) stop one visitor from monopolising
    the shared Overpass budget or the Nominatim quota.
  * **Global search concurrency** caps how much memory the process can use at
    once. A search holds its whole OSM extract in memory, and that grows with
    the square of the radius (measured: ~240 MiB of Python heap at 5 km), so two
    large parallel searches can exhaust a small container.
  * **Request size caps** keep a single request from being expensive at all.

Everything is in-process and in-memory on purpose: the app is designed to run as
a single container. Should you ever scale to several instances, these limits
become per-instance and you would want a shared store (Redis) instead.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from fastapi import HTTPException, Request

from app.config import SETTINGS


def client_key(request: Request) -> str:
    """
    Identifies the caller for rate limiting.

    Behind a reverse proxy the socket address is the proxy, so we read
    X-Forwarded-For instead - but ONLY when TRUST_PROXY is enabled. Trusting
    that header unconditionally would let anyone spoof an address and bypass
    every limit by sending a random value per request.
    """
    if SETTINGS.trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            # Left-most entry is the original client.
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip", "")
        if real_ip:
            return real_ip.strip()
    return request.client.host if request.client else "unknown"


@dataclass
class _Bucket:
    tokens: float
    updated_at: float


@dataclass
class TokenBucket:
    """
    Classic token bucket: ``capacity`` requests of burst, refilled over
    ``per_seconds``.
    """

    name: str
    capacity: int
    per_seconds: float
    _buckets: dict[str, _Bucket] = field(default_factory=dict)
    _last_prune: float = field(default_factory=time.monotonic)

    @property
    def refill_rate(self) -> float:
        return self.capacity / max(self.per_seconds, 1e-6)

    def consume(self, key: str, amount: float = 1.0) -> float:
        """
        Returns 0.0 when allowed, otherwise the number of seconds to wait.
        """
        now = time.monotonic()
        self._prune(now)

        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = _Bucket(tokens=float(self.capacity), updated_at=now)
            self._buckets[key] = bucket

        # Refill for the time that has passed.
        elapsed = now - bucket.updated_at
        bucket.tokens = min(float(self.capacity), bucket.tokens + elapsed * self.refill_rate)
        bucket.updated_at = now

        if bucket.tokens >= amount:
            bucket.tokens -= amount
            return 0.0
        missing = amount - bucket.tokens
        return missing / self.refill_rate

    def _prune(self, now: float) -> None:
        """Drops idle entries so the dict cannot grow without bound."""
        if now - self._last_prune < 60.0:
            return
        self._last_prune = now
        # A bucket that has had time to refill completely carries no state.
        cutoff = self.per_seconds
        stale = [k for k, b in self._buckets.items() if now - b.updated_at > cutoff]
        for k in stale:
            self._buckets.pop(k, None)


# ---------------------------------------------------------------------------
# Limiter instances
# ---------------------------------------------------------------------------
# Searches are by far the most expensive operation (Overpass traffic plus CPU
# and memory), so they get the tightest budget.
SEARCH_LIMITER = TokenBucket("search", SETTINGS.rate_search_burst, SETTINGS.rate_search_per_s)

# Geocoding is proxied to Nominatim, whose usage policy allows 1 request/second
# in total. The backend already serialises them; this stops one visitor from
# filling that queue.
GEOCODE_LIMITER = TokenBucket("geocode", SETTINGS.rate_geocode_burst, SETTINGS.rate_geocode_per_s)

# NOTE: there is deliberately no tile limiter any more. Map tiles (both the
# OpenStreetMap base map and the Strava heatmap) are fetched by the browser
# directly from their origin and never pass through this server, so there is
# nothing here to rate limit.


def enforce(limiter: TokenBucket, request: Request, cost: float = 1.0) -> None:
    """Raises 429 with a Retry-After header when the caller is over budget."""
    retry_after = limiter.consume(client_key(request), cost)
    if retry_after > 0.0:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Too many requests ({limiter.name}). This is a small, freely hosted "
                f"instance - please wait {retry_after:.0f} s. If you need heavy use, "
                "self-hosting is a few minutes of work (see the README)."
            ),
            headers={"Retry-After": str(max(1, int(retry_after + 0.5)))},
        )


# ---------------------------------------------------------------------------
# Global search concurrency
# ---------------------------------------------------------------------------
class SearchSlots:
    """
    Bounds how many searches run or wait at the same time.

    Without this, N parallel visitors would each hold a full OSM extract in
    memory and the container would be OOM-killed. Rejecting early with a clear
    message is far better than dying halfway through everybody's request.
    """

    def __init__(self, max_concurrent: int, max_queued: int) -> None:
        self.max_concurrent = max(1, max_concurrent)
        self.max_queued = max(0, max_queued)
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        self._waiting = 0
        self._running = 0
        self._lock = asyncio.Lock()

    @property
    def running(self) -> int:
        return self._running

    @property
    def waiting(self) -> int:
        return self._waiting

    def would_reject(self) -> bool:
        """Checked before a job is even created, so the caller gets a 503."""
        return self._waiting >= self.max_queued

    async def __aenter__(self):
        async with self._lock:
            self._waiting += 1
        try:
            await self._semaphore.acquire()
        finally:
            async with self._lock:
                self._waiting -= 1
        async with self._lock:
            self._running += 1
        return self

    async def __aexit__(self, *exc_info) -> None:
        async with self._lock:
            self._running -= 1
        self._semaphore.release()


SEARCH_SLOTS = SearchSlots(SETTINGS.search_max_concurrent, SETTINGS.search_max_queued)


def clamp_search_request(request_obj) -> list[str]:
    """
    Applies the instance limits to a search request, in place.

    Returns human-readable notes about anything that was clamped, so the user
    sees why they got something other than what they asked for instead of
    silently different results.

    Raising instead of clamping the radius would be unfriendly: a visitor who
    drags the slider to 20 km on a small instance should still get a result.
    """
    notes: list[str] = []

    max_radius = SETTINGS.max_radius_km
    if request_obj.radius_km > max_radius:
        notes.append(
            f"Radius reduced from {request_obj.radius_km:g} km to the limit of "
            f"{max_radius:g} km for this instance. Memory use grows with the square "
            "of the radius; self-host to raise it (see the README)."
        )
        request_obj.radius_km = max_radius

    if request_obj.spacing_m is not None and request_obj.spacing_m < SETTINGS.min_spacing_m:
        notes.append(
            f"Grid spacing raised from {request_obj.spacing_m:g} m to "
            f"{SETTINGS.min_spacing_m:g} m, the minimum for this instance."
        )
        request_obj.spacing_m = SETTINGS.min_spacing_m

    if request_obj.max_results is not None and request_obj.max_results > SETTINGS.max_results:
        notes.append(f"Result count capped at {SETTINGS.max_results}.")
        request_obj.max_results = SETTINGS.max_results

    # A per-request config override is fine, but it must not be used to lift the
    # instance limits through the back door.
    if request_obj.weights:
        grid = request_obj.weights.get("grid")
        if isinstance(grid, dict):
            for key in ("max_points", "max_results", "min_spacing_m"):
                grid.pop(key, None)

    return notes


def require_writable(action: str) -> None:
    """
    Blocks endpoints that change server-wide state when the instance is public.

    A shared deployment must not let a visitor rewrite the scoring weights or
    the no-fly zones for everybody else, or wipe the Overpass cache.
    """
    if SETTINGS.public_mode:
        raise HTTPException(
            status_code=403,
            detail=(
                f"{action} is disabled on this public instance, because it would change "
                "the configuration for every visitor. Run your own instance to use it - "
                "the README shows how in a few lines. Per-request weight overrides in "
                "the search body still work here."
            ),
        )


def limits_summary() -> dict:
    """Instance limits, so the frontend can adapt its controls."""
    return {
        "public_mode": SETTINGS.public_mode,
        "max_radius_km": SETTINGS.max_radius_km,
        "min_spacing_m": SETTINGS.min_spacing_m,
        "max_results": SETTINGS.max_results,
        "search_max_concurrent": SEARCH_SLOTS.max_concurrent,
        "search_running": SEARCH_SLOTS.running,
        "search_waiting": SEARCH_SLOTS.waiting,
        "config_writable": not SETTINGS.public_mode,
    }
