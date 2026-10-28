"""
Running a server for months without looking after it: the OSM data follows
the monthly release on its own, the scoring follows the code's defaults, and
expected search failures stay one line in the log.
"""

from __future__ import annotations

import asyncio
import functools
import json
import os
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from app import config
from app.osm import fetch
from app.scoring.defaults import DEFAULT_CONFIG
from app.services.jobs import JobRegistry
from app.services.overpass import OutsideCoverageError

REGIONS = {"regions": [{"slug": "berlin"}]}


@pytest.fixture
def release(tmp_path):
    """A local stand-in for the GitHub release: serves a folder, HEAD included."""
    folder = tmp_path / "release"
    folder.mkdir()
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(folder))
    handler.log_message = lambda *args: None
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield folder, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def _publish(folder: Path, data: dict, age_s: float = 0) -> None:
    path = folder / "regions.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    stamp = time.time() - age_s
    os.utime(path, (stamp, stamp))


def test_fetch_follows_the_release_by_its_date(release, tmp_path):
    folder, base = release
    target = tmp_path / "data" / "regions.json"
    target.parent.mkdir()
    url = f"{base}/regions.json"

    # Missing -> downloaded.
    _publish(folder, REGIONS, age_s=3600)
    assert fetch.fetch(url, target, 35, fetch._valid_regions)
    assert json.loads(target.read_text()) == REGIONS

    # The release is older than the local copy -> kept, however old the copy.
    assert not fetch.fetch(url, target, 0.0001, fetch._valid_regions)

    # A newer release -> replaced, without waiting for any max age.
    newer = {"regions": [{"slug": "hamburg"}]}
    _publish(folder, newer)
    os.utime(target, (time.time() - 60, time.time() - 60))
    assert fetch.fetch(url, target, 35, fetch._valid_regions)
    assert json.loads(target.read_text()) == newer


def test_a_broken_download_never_replaces_working_data(release, tmp_path):
    folder, base = release
    target = tmp_path / "regions.json"
    target.write_text(json.dumps(REGIONS), encoding="utf-8")
    os.utime(target, (time.time() - 60, time.time() - 60))
    (folder / "regions.json").write_text("<html>rate limited</html>", encoding="utf-8")

    with pytest.raises(RuntimeError, match="rejected"):
        fetch.fetch(f"{base}/regions.json", target, 35, fetch._valid_regions)
    assert json.loads(target.read_text()) == REGIONS
    assert not target.with_suffix(".download").exists()
    # The same unusable file is not fetched again every round ...
    assert not fetch.fetch(f"{base}/regions.json", target, 35, fetch._valid_regions)
    # ... the next release is.
    _publish(folder, {"regions": []}, age_s=-5)
    assert fetch.fetch(f"{base}/regions.json", target, 35, fetch._valid_regions)


def test_a_full_disk_keeps_the_old_data(release, tmp_path, monkeypatch):
    folder, base = release
    _publish(folder, REGIONS)
    monkeypatch.setattr(fetch, "DISK_RESERVE", 1 << 60)
    with pytest.raises(RuntimeError, match="disk space"):
        fetch.fetch(f"{base}/regions.json", tmp_path / "regions.json", 35, fetch._valid_regions)


@pytest.fixture
def weights_file(tmp_path, monkeypatch):
    path = tmp_path / "weights.json"
    monkeypatch.setattr(config, "WEIGHTS_FILE", path)
    yield path
    config.load_config(force=True)


def test_a_public_instance_ignores_a_left_over_weights_file(weights_file, monkeypatch):
    # What v2.0.0 wrote on first start: every default of that release.
    frozen = json.loads(json.dumps(DEFAULT_CONFIG))
    frozen["total"]["solitude_weight"] = 0.99
    weights_file.write_text(json.dumps(frozen), encoding="utf-8")

    monkeypatch.setattr(config.SETTINGS, "use_weights_file", False)
    assert config.load_config(force=True)["total"]["solitude_weight"] == DEFAULT_CONFIG["total"]["solitude_weight"]
    monkeypatch.setattr(config.SETTINGS, "use_weights_file", True)
    assert config.load_config(force=True)["total"]["solitude_weight"] == 0.99


def test_saved_weights_hold_only_the_changes(weights_file, monkeypatch):
    monkeypatch.setattr(config.SETTINGS, "use_weights_file", True)
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    cfg["total"]["solitude_weight"] = 0.7
    config.save_config(cfg)
    assert json.loads(weights_file.read_text()) == {"total": {"solitude_weight": 0.7}}

    # Back to the defaults: nothing left to keep, and nothing written up front.
    config.save_config(json.loads(json.dumps(DEFAULT_CONFIG)))
    assert json.loads(weights_file.read_text()) == {}
    weights_file.unlink()
    config.load_config(force=True)
    assert not weights_file.exists()


def _run_failing_job(exc: Exception) -> None:
    async def main() -> None:
        registry = JobRegistry()
        job = registry.create()

        async def work(_job):
            raise exc

        registry.start(job, work)
        await job.task

    asyncio.run(main())


def test_expected_search_failures_are_one_line(capsys):
    _run_failing_job(OutsideCoverageError("This area is outside the region this instance covers."))
    err = capsys.readouterr()
    assert err.out.strip() == "[search] outside_coverage: This area is outside the region this instance covers."
    assert "Traceback" not in err.err

    _run_failing_job(ValueError("a real bug"))
    assert "Traceback" in capsys.readouterr().err
