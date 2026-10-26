"""
Writes the tiny OSM test world (see test_osm_store.py) as a tile store, so the
end-to-end tests in CI can run real searches without any network access:

    python -m tests.make_fixture_store data/osm-fixture.sqlite
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from app.osm.importer import run_import
from tests.test_osm_store import OSM_XML, POLY


def main(target: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "fixture.osm").write_text(OSM_XML, encoding="utf-8")
        (work / "fixture.poly").write_text(POLY, encoding="utf-8")
        run_import(work / "fixture.osm", work / "fixture.poly", Path(target), 0.1, "flex_mem")


if __name__ == "__main__":
    main(sys.argv[1])
