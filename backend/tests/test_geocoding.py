"""
Place search fallbacks, without network: Photon failing must not slow every
lookup down, and type-ahead must never reach Nominatim (its policy forbids
autocomplete).
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.services import geocoding


@pytest.fixture()
def fake(monkeypatch, tmp_path):
    calls: list[str] = []

    async def photon_down(query, limit, lang):
        calls.append("photon")
        raise httpx.ConnectTimeout("hangs")

    async def nominatim(query, limit, lang):
        calls.append("nominatim")
        return [{"label": query, "lat": 48.0, "lon": 9.0, "type": "town"}]

    class NoCache:
        def get(self, key):
            return None

        def put(self, key, value):
            pass

    monkeypatch.setattr(geocoding, "_photon", photon_down)
    monkeypatch.setattr(geocoding, "_nominatim", nominatim)
    monkeypatch.setattr(geocoding, "_get_cache", lambda: NoCache())
    monkeypatch.setattr(geocoding, "_photon_down_until", 0.0)
    return calls


def test_type_ahead_never_asks_nominatim(fake):
    assert asyncio.run(geocoding.geocode("Bad Ur", suggest=True)) == []
    assert fake == ["photon"]


def test_explicit_search_falls_back_and_photon_is_paused(fake):
    first = asyncio.run(geocoding.geocode("Bad Urach"))
    assert first[0]["label"] == "Bad Urach"
    assert fake == ["photon", "nominatim"]
    # Photon just failed: the next lookup goes straight to Nominatim.
    asyncio.run(geocoding.geocode("Münsingen"))
    assert fake == ["photon", "nominatim", "nominatim"]


def test_kp_takes_the_worst_slot_of_the_next_hours():
    from datetime import datetime, timezone

    from app.services.spaceweather import _next_hours_max

    rows = [
        {"time_tag": "2026-10-24T03:00:00", "kp": 6.0},  # over
        {"time_tag": "2026-10-24T09:00:00", "kp": 2.3},  # current slot
        {"time_tag": "2026-10-24T12:00:00", "kp": 4.7},  # within three hours
        {"time_tag": "2026-10-24T18:00:00", "kp": 7.0},  # too far ahead
    ]
    assert _next_hours_max(rows, datetime(2026, 10, 24, 10, 30, tzinfo=timezone.utc)) == 4.7
