"""
Result cache, shares and coverage over the HTTP API, on the tiny fixture store
from test_osm_store.py - no network.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.osm.store as store_module
from app.config import SETTINGS
from app.limits import SEARCH_LIMITER, SHARE_LIMITER
from app.services import appdb
from tests.test_osm_store import store  # noqa: F401 - the fixture


@pytest.fixture()
def client(store, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(store_module, "_store", store)
    monkeypatch.setattr(store_module, "_store_checked", True)
    monkeypatch.setattr(appdb, "_db", appdb.AppDB(tmp_path / "app.sqlite"))
    monkeypatch.setattr(SETTINGS, "osm_live_fallback", False)
    # Every test client is the same "visitor"; give each test a fresh budget.
    monkeypatch.setattr(SEARCH_LIMITER, "_buckets", {})
    monkeypatch.setattr(SHARE_LIMITER, "_buckets", {})
    from app.main import app

    with TestClient(app) as c:
        yield c


SEARCH = {"lat": 48.45, "lon": 9.45, "radius_km": 1.0, "use_strava": False}


def test_identical_searches_share_one_result(client):
    first = client.post("/api/search/sync", json=SEARCH).json()
    second = client.post("/api/search/sync", json={**SEARCH, "lat": 48.450001}).json()
    assert first["result_id"] and first["result_id"] == second["result_id"]
    assert first["stats"]["tiles_local"] == 1


def test_cached_result_is_returned_as_finished_job(client):
    client.post("/api/search/sync", json=SEARCH)
    job = client.post("/api/search", json=SEARCH).json()
    assert job["status"] == "done" and job["result"]["points"]


def test_share_copies_the_servers_own_numbers(client):
    result = client.post("/api/search/sync", json=SEARCH).json()
    point = max(result["points"], key=lambda p: p["score"])
    created = client.post("/api/share", json={"result_id": result["result_id"], "point_id": point["id"]})
    assert created.status_code == 200
    share = client.get(f"/api/share/{created.json()['id']}").json()
    assert share["spot"]["score"] == point["score"]
    assert share["spot"]["reasons"] == point["reasons"]
    assert share["search"]["radius_km"] == 1.0


def test_share_of_unknown_result_is_refused(client):
    response = client.post("/api/share", json={"result_id": "0" * 64, "point_id": 1})
    assert response.status_code == 410


def test_search_outside_coverage_says_so(client):
    response = client.post("/api/search/sync", json={**SEARCH, "lat": 52.5, "lon": 13.4})
    assert response.status_code == 422
    assert response.json()["code"] == "outside_coverage"


def test_points_outside_the_outline_are_dropped(client):
    # 48.495 is 500 m inside the fixture outline (top edge 48.5): a 1 km
    # radius reaches past it, and those points must not be scored.
    result = client.post("/api/search/sync", json={**SEARCH, "lat": 48.495}).json()
    assert all(p["lat"] < 48.5 for p in result["points"])
    assert any("outside the covered region" in n for n in result["notes"])


def test_cached_searches_do_not_use_up_the_rate_limit(client):
    client.post("/api/search", json=SEARCH)
    # Far more than the burst of 5 - all identical, so all cache hits.
    statuses = {client.post("/api/search", json=SEARCH).status_code for _ in range(12)}
    assert statuses == {200}
