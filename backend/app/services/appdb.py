"""
Small persistent state of the app itself: finished search results and shared
spots. One SQLite file in the data volume, separate from the OSM data so that
replacing the OSM store never touches either.

Result cache - why it pays off: a video that shows "spots near Stuttgart" sends
thousands of people who type the same town and get the same coordinates from
the geocoder. Only the first of them needs a search slot; on a one-core server
that is the difference between a queue and an instant answer.

Shares - a shared link must keep working after the result cache has moved on
and after the next OSM import changed the scores, so a share stores its own
small snapshot of the spot instead of pointing into a result.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

import zstandard

from app.config import SETTINGS

_SCHEMA = """
CREATE TABLE IF NOT EXISTS results (
    key        TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    payload    BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_results_created ON results(created_at);
CREATE TABLE IF NOT EXISTS shares (
    id         TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    payload    TEXT NOT NULL
);
"""

RESULT_TTL_S = 7 * 86400
# ~100 KB each after compression, so this caps the cache near 50 MB.
MAX_RESULTS = 500

# Share ids: short enough to read out in a video, long enough not to guess.
SHARE_ID_ALPHABET = "23456789abcdefghijkmnpqrstuvwxyz"
SHARE_ID_LENGTH = 8

_COMPRESSOR = zstandard.ZstdCompressor(level=6)
_DECOMPRESSOR = zstandard.ZstdDecompressor()


class AppDB:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._lock = threading.Lock()

    # -- result cache -------------------------------------------------------
    @staticmethod
    def result_key(request: dict[str, Any], data_version: str) -> str:
        """
        Identical inputs on identical data -> identical result. ``data_version``
        is the OSM store's timestamp, so a new import invalidates everything.
        """
        canonical = json.dumps({"r": request, "v": data_version}, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def get_result(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM results WHERE key = ? AND created_at > ?", (key, time.time() - RESULT_TTL_S)
            ).fetchone()
        return json.loads(_DECOMPRESSOR.decompress(row[0])) if row else None

    def put_result(self, key: str, result: dict[str, Any]) -> None:
        blob = _COMPRESSOR.compress(json.dumps(result, separators=(",", ":")).encode())
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO results (key, created_at, payload) VALUES (?, ?, ?)", (key, time.time(), blob)
            )
            # Keep only the newest MAX_RESULTS entries.
            self._conn.execute(
                "DELETE FROM results WHERE key NOT IN (SELECT key FROM results ORDER BY created_at DESC LIMIT ?)",
                (MAX_RESULTS,),
            )
            self._conn.commit()

    # -- shares -------------------------------------------------------------
    def create_share(self, payload: dict[str, Any]) -> str:
        text = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        with self._lock:
            while True:
                share_id = "".join(secrets.choice(SHARE_ID_ALPHABET) for _ in range(SHARE_ID_LENGTH))
                try:
                    self._conn.execute(
                        "INSERT INTO shares (id, created_at, payload) VALUES (?, ?, ?)", (share_id, time.time(), text)
                    )
                    self._conn.commit()
                    return share_id
                except sqlite3.IntegrityError:
                    continue  # collision - astronomically rare, just draw again

    def get_share(self, share_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT payload, created_at FROM shares WHERE id = ?", (share_id,)).fetchone()
        if row is None:
            return None
        return {**json.loads(row[0]), "created_at": row[1]}


_db: AppDB | None = None
_db_lock = threading.Lock()


def get_db() -> AppDB:
    global _db
    with _db_lock:
        if _db is None:
            _db = AppDB(SETTINGS.data_dir / "app.sqlite")
        return _db
