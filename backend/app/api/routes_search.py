"""Search endpoints (job based, plus a synchronous variant for small radii)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.limits import (
    SEARCH_LIMITER,
    SEARCH_SLOTS,
    SHARE_LIMITER,
    clamp_search_request,
    enforce,
)
from app.models import JobStatus, SearchRequest, SearchResult, ShareCreate, ShareCreated
from app.osm.store import get_store
from app.pipeline import run_search
from app.services.appdb import get_db
from app.services.jobs import REGISTRY, Job

router = APIRouter(prefix="/api", tags=["search"])

# Above this radius the synchronous variant is refused - the first (uncached)
# call would otherwise run into an HTTP timeout.
SYNC_MAX_RADIUS_KM = 6.0


# 4 decimals is ~10 m - far below the grid spacing, so snapping changes
# nothing a visitor could notice, but it makes "the same place" hash the same.
COORD_DECIMALS = 4


def _normalise(request: SearchRequest) -> None:
    request.lat = round(request.lat, COORD_DECIMALS)
    request.lon = round(request.lon, COORD_DECIMALS)


def _result_key(request: SearchRequest) -> str:
    store = get_store()
    data_version = f"{store.region}@{store.data_timestamp}" if store else "overpass"
    return get_db().result_key(request.model_dump(), data_version)


async def _search_cached(request: SearchRequest, clamp_notes: list[str], job: Job | None = None) -> dict:
    """Runs the search unless the identical one is already cached."""
    key = _result_key(request)
    db = get_db()
    result = db.get_result(key)
    if result is None:
        if job is not None:
            job.message = "Waiting for a free search slot ..."
        async with SEARCH_SLOTS:
            result = await run_search(request, job=job)
        if clamp_notes:
            result["notes"] = clamp_notes + result.get("notes", [])
        result["result_id"] = key
        db.put_result(key, result)
    return result


def _reject_if_busy() -> None:
    if SEARCH_SLOTS.would_reject():
        raise HTTPException(
            status_code=503,
            detail=(
                f"The search queue is full ({SEARCH_SLOTS.running} running, "
                f"{SEARCH_SLOTS.waiting} waiting). Please try again shortly."
            ),
            headers={"Retry-After": "30"},
        )


@router.post("/search", response_model=JobStatus, summary="Start a search as a background job")
async def start_search(request: SearchRequest, http_request: Request) -> JobStatus:
    """
    Starts the search and returns a ``job_id`` immediately.

    Poll ``GET /api/search/{job_id}`` afterwards for progress and the result.
    """
    # Clamp to the instance limits before anything expensive happens, and pass
    # the reasons through so the user sees them in the result notes.
    clamp_notes = clamp_search_request(request)
    _normalise(request)

    # A cached result needs no slot and costs nothing, so it is served even
    # with a full queue and does not count against the visitor's budget -
    # which matters exactly when everybody is searching for the same town.
    cached = get_db().get_result(_result_key(request))
    if cached is not None:
        return JobStatus(**REGISTRY.create_finished(cached).to_dict())

    enforce(SEARCH_LIMITER, http_request)
    _reject_if_busy()
    job = REGISTRY.create()

    async def work(j: Job):
        # The slot is held for the whole search, so the number of OSM extracts
        # in memory at once stays bounded.
        return await _search_cached(request, clamp_notes, job=j)

    REGISTRY.start(job, work)
    return JobStatus(**job.to_dict())


@router.get("/search/{job_id}", response_model=JobStatus, summary="Status and result of a search job")
async def get_search(job_id: str) -> JobStatus:
    job = REGISTRY.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown or expired job.")
    return JobStatus(**job.to_dict())


@router.delete("/search/{job_id}", summary="Cancel a running search job")
async def cancel_search(job_id: str) -> dict[str, bool]:
    return {"cancelled": REGISTRY.cancel(job_id)}


@router.post("/search/sync", response_model=SearchResult, summary="Synchronous search (small radii only)")
async def search_sync(request: SearchRequest, http_request: Request) -> SearchResult:
    """Handy for tests and scripts - bypasses the job machinery."""
    enforce(SEARCH_LIMITER, http_request)
    # Clamp to the instance limits FIRST: if this instance caps the radius below
    # the synchronous ceiling anyway, an oversized request is still serviceable
    # and there is no reason to refuse it.
    clamp_notes = clamp_search_request(request)
    if request.radius_km > SYNC_MAX_RADIUS_KM:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Synchronous searches are limited to {SYNC_MAX_RADIUS_KM:g} km radius - "
                "use POST /api/search for anything larger."
            ),
        )
    _reject_if_busy()
    _normalise(request)
    return SearchResult(**await _search_cached(request, clamp_notes))


# Fields copied from a result point into a share. Everything comes from the
# server's own result: a client that could post its own numbers could publish
# "100/100, perfectly legal" for any field in the country under this domain.
SHARE_POINT_FIELDS = (
    "lat", "lon", "score", "solitude", "flyability", "blocked",
    "category", "area_name", "distances", "warnings", "reasons",
)


@router.post("/share", response_model=ShareCreated, summary="Create a short link for one spot of a result")
async def create_share(body: ShareCreate, http_request: Request) -> ShareCreated:
    enforce(SHARE_LIMITER, http_request)
    db = get_db()
    result = db.get_result(body.result_id)
    if result is None:
        raise HTTPException(status_code=410, detail="This result has expired - run the search again to share it.")
    point = next((p for p in result["points"] if p["id"] == body.point_id), None)
    if point is None:
        raise HTTPException(status_code=404, detail="No such spot in this result.")
    snapshot = {
        "spot": {k: point.get(k) for k in SHARE_POINT_FIELDS},
        "search": {
            "lat": result["center"]["lat"],
            "lon": result["center"]["lon"],
            "radius_km": result["radius_km"],
            "time_profile": result["time_profile"],
        },
    }
    return ShareCreated(id=db.create_share(snapshot))


@router.get("/share/{share_id}", summary="A shared spot")
async def get_share(share_id: str) -> dict:
    share = get_db().get_share(share_id)
    if share is None:
        raise HTTPException(status_code=404, detail="Unknown share link.")
    return share
