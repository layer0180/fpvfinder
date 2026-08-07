"""
Simple job management for running searches.

Why jobs at all? A search with a 20 km radius can take several minutes the
first time (many Overpass tiles, deliberately throttled). A synchronous HTTP
request would run into timeouts, and the frontend would have no progress
indication.

Deliberately in-memory and without persistence - the app runs locally in a
single process.
"""

from __future__ import annotations

import asyncio
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

JOB_TTL_S = 30 * 60


@dataclass
class Job:
    id: str
    status: str = "pending"          # pending | running | done | error
    progress: float = 0.0            # 0..1
    message: str = "Waiting to start ..."
    result: Any = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    task: asyncio.Task | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.id,
            "status": self.status,
            "progress": round(self.progress, 3),
            "message": self.message,
            "error": self.error,
            "elapsed_s": round(time.time() - self.created_at, 1),
            "result": self.result if self.status == "done" else None,
        }


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def create(self) -> Job:
        self._cleanup()
        job = Job(id=uuid.uuid4().hex[:12])
        self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def start(self, job: Job, work: Callable[[Job], Awaitable[Any]]) -> None:
        """Starts the work in the background and maintains the job status."""

        async def runner() -> None:
            job.status = "running"
            job.message = "Search started ..."
            job.updated_at = time.time()
            try:
                job.result = await work(job)
                job.status = "done"
                job.progress = 1.0
                job.message = "Done"
            except asyncio.CancelledError:
                job.status = "error"
                job.error = "Cancelled"
                raise
            except Exception as exc:
                job.status = "error"
                job.error = f"{type(exc).__name__}: {exc}"
                job.message = "Failed"
                traceback.print_exc()
            finally:
                job.updated_at = time.time()

        job.task = asyncio.create_task(runner())

    def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job and job.task and not job.task.done():
            job.task.cancel()
            return True
        return False

    def _cleanup(self) -> None:
        """Removes old finished jobs so memory does not grow unbounded."""
        now = time.time()
        stale = [
            jid
            for jid, job in self._jobs.items()
            if job.status in ("done", "error") and (now - job.updated_at) > JOB_TTL_S
        ]
        for jid in stale:
            self._jobs.pop(jid, None)


def progress_reporter(job: Job, start: float, end: float, total_hint: int = 1):
    """
    Builds a ``progress`` callback for one section of the pipeline.

    ``start`` and ``end`` bound this section on the 0..1 scale, so the progress
    bars of the individual phases do not overtake each other.
    """

    async def report(done: int, total: int, message: str) -> None:
        total = max(total or total_hint, 1)
        job.progress = start + (end - start) * min(done / total, 1.0)
        job.message = message
        job.updated_at = time.time()
        # Yield to the event loop briefly so status polls get through.
        await asyncio.sleep(0)

    return report


REGISTRY = JobRegistry()
