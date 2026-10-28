"""
Downloads a prebuilt OSM tile store, e.g. the monthly GitHub release asset.

    python -m app.osm.fetch            # uses OSM_STORE_URL / OSM_STORE

Run by the container entrypoint before the server starts, and by the server
itself every OSM_REFRESH_HOURS (app/osm/refresh.py). It does nothing when
OSM_STORE_URL is unset or the local file is current: when the server behind
the URL reports a Last-Modified date (GitHub does), the file is fetched only
if that date is newer than the local copy; otherwise only when the local copy
is older than OSM_STORE_MAX_AGE_DAYS (0 = keep forever).

The download goes to a temporary file that is checked and then renamed, so an
interrupted download never replaces a working store.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from email.utils import parsedate_to_datetime
from pathlib import Path

from app.config import SETTINGS
from app.osm.codec import CODEC_VERSION

CHUNK = 1 << 20
DEFAULT_MAX_AGE_DAYS = 35
# Room left on the disk after a download, for the cache and the logs.
DISK_RESERVE = 300 * 1024 * 1024

# url -> Last-Modified of a file this process downloaded and could not use (a
# newer codec than this build reads, a swap the OS refused). Without it the
# refresh would fetch the same 1.5 GB again every round until the next release.
_unusable: dict[str, float] = {}


def _valid(path: Path) -> str | None:
    """None when the file is a usable store, otherwise the reason it is not."""
    try:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
        tiles = conn.execute("SELECT COUNT(*) FROM tiles").fetchone()[0]
        conn.close()
    except sqlite3.Error as exc:
        return f"not a tile store ({exc})"
    if int(meta.get("codec_version", 0)) != CODEC_VERSION:
        return f"codec version {meta.get('codec_version')} - this build reads {CODEC_VERSION}"
    if tiles == 0:
        return "contains no tiles"
    return None


def _valid_regions(path: Path) -> str | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return f"not JSON ({exc})"
    return None if isinstance(data.get("regions"), list) else "no regions list"


def _remote(url: str) -> tuple[float | None, int]:
    """(Last-Modified as a timestamp or None, size in bytes or 0), from a HEAD request."""
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": SETTINGS.user_agent})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            size = int(response.headers.get("Content-Length") or 0)
            modified = response.headers.get("Last-Modified")
    except urllib.error.HTTPError:
        # A server that does not answer HEAD: fall back on the file's age.
        return None, 0
    try:
        return (parsedate_to_datetime(modified).timestamp() if modified else None), size
    except (TypeError, ValueError):
        return None, size


def fetch(url: str, target: Path, max_age_days: float, validate=_valid) -> bool:
    """Downloads ``url`` to ``target`` when that is missing or outdated; True if it did."""
    modified, size = _remote(url)
    if modified is not None and _unusable.get(url) == modified:
        print(f"[osm-fetch] {target.name}: the newer file was unusable - waiting for the next one")
        return False
    if target.exists():
        local = target.stat().st_mtime
        age_days = (time.time() - local) / 86400
        if modified is not None:
            # The download is written after the upload, so a current copy is
            # always younger than the file it came from.
            if modified <= local:
                print(f"[osm-fetch] {target.name} is current ({age_days:.0f} days old)")
                return False
            print(f"[osm-fetch] {target.name}: newer file at the source - refreshing")
        elif max_age_days <= 0 or age_days < max_age_days:
            print(f"[osm-fetch] {target.name} present ({age_days:.0f} days old) - keeping it")
            return False
        else:
            print(f"[osm-fetch] {target.name} is {age_days:.0f} days old - refreshing")

    # Old and new file sit side by side until the swap.
    free = shutil.disk_usage(target.parent).free
    if size and free < size + DISK_RESERVE:
        raise RuntimeError(
            f"not enough disk space for {target.name}: {size / 1e9:.1f} GB needed, "
            f"{free / 1e9:.1f} GB free - keeping the current file"
        )

    partial = target.with_suffix(".download")
    print(f"[osm-fetch] downloading {url}")
    request = urllib.request.Request(url, headers={"User-Agent": SETTINGS.user_agent})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, open(partial, "wb") as out:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            next_report = 0.0
            while chunk := response.read(CHUNK):
                out.write(chunk)
                done += len(chunk)
                if total and done / total >= next_report:
                    print(f"[osm-fetch]   {done / 1e6:,.0f} / {total / 1e6:,.0f} MB")
                    next_report += 0.1
    except BaseException:
        partial.unlink(missing_ok=True)
        raise

    problem = validate(partial)
    try:
        if problem:
            raise RuntimeError(f"downloaded file rejected: {problem}")
        os.replace(partial, target)
    except Exception:
        partial.unlink(missing_ok=True)
        if modified is not None:
            _unusable[url] = modified
        raise
    print(f"[osm-fetch] done: {target} ({target.stat().st_size / 1e6:,.0f} MB)")
    return True


def jobs() -> list[tuple[str, Path, object]]:
    """(url, local file, validator) for every configured download."""
    # The region pages (app/regions.py) are computed from the same import and
    # published next to it, so they follow the same refresh rhythm.
    return [
        (url, target, validate)
        for url, target, validate in (
            (os.environ.get("OSM_STORE_URL", "").strip(), SETTINGS.osm_store, _valid),
            (os.environ.get("REGIONS_URL", "").strip(), SETTINGS.data_dir / "regions.json", _valid_regions),
        )
        if url
    ]


def fetch_all() -> list[Path]:
    """Runs every configured download; returns the files that were replaced."""
    max_age = float(os.environ.get("OSM_STORE_MAX_AGE_DAYS", "") or DEFAULT_MAX_AGE_DAYS)
    replaced = []
    for url, target, validate in jobs():
        try:
            if fetch(url, target, max_age, validate):
                replaced.append(target)
        except Exception as exc:  # noqa: BLE001 - never keep the server from starting
            # Stale data, or Overpass as a fallback, beats no server at all.
            print(f"[osm-fetch] WARNING: {exc} - working with what is there")
    return replaced


def main() -> int:
    fetch_all()
    return 0


if __name__ == "__main__":
    sys.exit(main())
