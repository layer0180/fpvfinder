"""
Persistent cache for Overpass responses (SQLite plus gzip).

Why per tile? Because search areas overlap heavily: if you first search with a
5 km radius and then with 8 km, the inner tiles are already there and only the
new edge tiles hit the API. This is by far the most effective lever against
Overpass rate limits.
"""

from __future__ import annotations

import gzip
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS overpass_cache (
    key        TEXT PRIMARY KEY,
    fetched_at REAL NOT NULL,
    n_elements INTEGER NOT NULL,
    payload    BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_overpass_fetched ON overpass_cache(fetched_at);
"""


class OverpassCache:
    """Thread-safe key/value cache for JSON payloads."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        # check_same_thread=False: FastAPI runs the blocking parts in a thread pool.
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def get(self, key: str, max_age_s: float | None = None) -> list[dict[str, Any]] | None:
        """Returns the element list, or ``None`` on a miss or when expired."""
        with self._lock:
            row = self._conn.execute(
                "SELECT fetched_at, payload FROM overpass_cache WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        fetched_at, payload = row
        if max_age_s is not None and (time.time() - fetched_at) > max_age_s:
            return None
        try:
            return json.loads(gzip.decompress(payload).decode("utf-8"))
        except (OSError, json.JSONDecodeError):
            # Corrupted entry -> treat it like a miss.
            return None

    def put(self, key: str, elements: list[dict[str, Any]]) -> None:
        blob = gzip.compress(json.dumps(elements, separators=(",", ":")).encode("utf-8"), 6)
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO overpass_cache (key, fetched_at, n_elements, payload) "
                "VALUES (?, ?, ?, ?)",
                (key, time.time(), len(elements), sqlite3.Binary(blob)),
            )
            self._conn.commit()

    def stats(self) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(n_elements), 0), COALESCE(SUM(LENGTH(payload)), 0), "
                "MIN(fetched_at), MAX(fetched_at) FROM overpass_cache"
            ).fetchone()
        return {
            "tiles": row[0],
            "elements": row[1],
            "compressed_bytes": row[2],
            "oldest": row[3],
            "newest": row[4],
            "db_path": str(self.db_path),
        }

    def clear(self, older_than_s: float | None = None) -> int:
        """Deletes cache entries. Returns the number of rows removed."""
        with self._lock:
            if older_than_s is None:
                cur = self._conn.execute("DELETE FROM overpass_cache")
            else:
                cur = self._conn.execute(
                    "DELETE FROM overpass_cache WHERE fetched_at < ?", (time.time() - older_than_s,)
                )
            self._conn.commit()
            deleted = cur.rowcount
        with self._lock:
            self._conn.execute("VACUUM")
        return max(deleted, 0)
