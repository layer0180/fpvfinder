"""Search endpoints (job based, plus a synchronous variant for small radii)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.limits import (
    SEARCH_LIMITER,
    SEARCH_SLOTS,
    clamp_search_request,
    enforce,
)
from app.models import JobStatus, SearchRequest, SearchResult
from app.pipeline import run_search
from app.services.jobs import REGISTRY, Job

router = APIRouter(prefix="/api", tags=["search"])

# Above this radius the synchronous variant is refused - the first (uncached)
# call would otherwise run into an HTTP timeout.
SYNC_MAX_RADIUS_KM = 6.0


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
    enforce(SEARCH_LIMITER, http_request)
    _reject_if_busy()

    # Clamp to the instance limits before anything expensive happens, and pass
    # the reasons through so the user sees them in the result notes.
    clamp_notes = clamp_search_request(request)

    job = REGISTRY.create()

    async def work(j: Job):
        # The slot is held for the whole search, so the number of OSM extracts
        # in memory at once stays bounded.
        j.message = "Waiting for a free search slot ..."
        async with SEARCH_SLOTS:
            result = await run_search(request, job=j)
        if clamp_notes:
            result["notes"] = clamp_notes + result.get("notes", [])
        return result

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

    async with SEARCH_SLOTS:
        result = await run_search(request)
    if clamp_notes:
        result["notes"] = clamp_notes + result.get("notes", [])
    return SearchResult(**result)
