"""
Downloads a prebuilt OSM tile store, e.g. the monthly GitHub release asset.

    python -m app.osm.fetch            # uses OSM_STORE_URL / OSM_STORE

Run by the container entrypoint before the server starts. It does nothing when
OSM_STORE_URL is unset, or when the local file exists and is younger than
OSM_STORE_MAX_AGE_DAYS (0 = keep forever). The download goes to a temporary
file that is checked and then renamed, so an interrupted download never
replaces a working store.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

from app.config import SETTINGS
from app.osm.codec import CODEC_VERSION

CHUNK = 1 << 20


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


def fetch(url: str, target: Path, max_age_days: float, validate=_valid) -> bool:
    if target.exists():
        age_days = (time.time() - target.stat().st_mtime) / 86400
        if max_age_days <= 0 or age_days < max_age_days:
            print(f"[osm-fetch] {target.name} present ({age_days:.0f} days old) - keeping it")
            return False
        print(f"[osm-fetch] {target.name} is {age_days:.0f} days old - refreshing")

    partial = target.with_suffix(".download")
    print(f"[osm-fetch] downloading {url}")
    request = urllib.request.Request(url, headers={"User-Agent": SETTINGS.user_agent})
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

    problem = validate(partial)
    if problem:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"downloaded file rejected: {problem}")
    os.replace(partial, target)
    print(f"[osm-fetch] done: {target} ({target.stat().st_size / 1e6:,.0f} MB)")
    return True


def main() -> int:
    max_age = float(os.environ.get("OSM_STORE_MAX_AGE_DAYS", "0") or 0)
    # The region pages (app/regions.py) are computed from the same import and
    # published next to it, so they follow the same refresh rhythm.
    jobs = [
        (os.environ.get("OSM_STORE_URL", "").strip(), SETTINGS.osm_store, _valid),
        (os.environ.get("REGIONS_URL", "").strip(), SETTINGS.data_dir / "regions.json", _valid_regions),
    ]
    for url, target, validate in jobs:
        if not url:
            continue
        try:
            fetch(url, target, max_age, validate)
        except Exception as exc:  # noqa: BLE001 - never keep the server from starting
            # Stale data, or Overpass as a fallback, beats no server at all.
            print(f"[osm-fetch] WARNING: {exc} - starting with what is there")
    return 0


if __name__ == "__main__":
    sys.exit(main())
