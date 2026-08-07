"""
Guards the things search engines depend on - no network access.

These are worth a test precisely because breaking them is invisible: a sitemap
listing localhost, a canonical tag pointing at the wrong host and a missing
verification file all still answer with HTTP 200. Nothing goes red; the site
just quietly stops being indexable, and you find out weeks later in the Search
Console.

Run it from the ``backend`` directory:
    .venv\\Scripts\\python.exe -m tests.test_seo
or with pytest:
    .venv\\Scripts\\python.exe -m pytest tests
"""

from __future__ import annotations

import importlib
import os
import re
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

SITE = "https://spots.example.test"
TOKEN = "google0123456789abcdef.html"

SITEMAP_NS = {
    "s": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "x": "http://www.w3.org/1999/xhtml",
}


@contextmanager
def _app(**env: str):
    """
    A client for the app configured from scratch.

    Both the base URL and the verification route are decided while the module
    is imported, so the module has to be reloaded rather than patched - which
    also means this reflects what a real deployment does at boot.
    """
    previous = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        from app import config, main

        importlib.reload(config)
        importlib.reload(main)
        with TestClient(main.app) as client:
            yield client
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        from app import config, main

        importlib.reload(config)
        importlib.reload(main)


def _built() -> bool:
    """The static pages are a build artefact, so skip rather than fail."""
    return (Path(__file__).resolve().parents[2] / "frontend" / "dist" / "sitemap.xml").exists()


def test_public_url_rewrites_every_absolute_url() -> None:
    if not _built():
        print("SKIP frontend/dist not built")
        return
    with _app(PUBLIC_URL=SITE) as client:
        sitemap = client.get("/sitemap.xml").text
        assert "localhost" not in sitemap, "sitemap still advertises the build-time host"

        root = ET.fromstring(sitemap)
        locs = [e.text or "" for e in root.findall(".//s:loc", SITEMAP_NS)]
        assert locs, "sitemap lists no URLs at all"
        assert all(u.startswith(SITE + "/") for u in locs), locs
        assert len(set(locs)) == len(locs), f"duplicate URLs: {locs}"

        # Every entry must declare its translations, or Google reads the two
        # languages as duplicates of each other instead of alternates.
        alternates = [e.get("href") or "" for e in root.findall(".//x:link", SITEMAP_NS)]
        assert alternates and all(u.startswith(SITE) for u in alternates), alternates

        # The sitemap and the pages both declare hreflang, which is allowed only
        # as long as they agree. Where they disagree Google reports a conflict
        # and trusts neither, so compare the actual sets rather than the counts.
        for url in root.findall(".//s:url", SITEMAP_NS):
            loc = (url.find("s:loc", SITEMAP_NS).text or "").replace(SITE, "") or "/"
            in_sitemap = {e.get("hreflang") for e in url.findall("x:link", SITEMAP_NS)}
            html = client.get(loc).text
            in_page = set(re.findall(r'rel="alternate" hreflang="([^"]+)"', html))
            assert in_sitemap == in_page, f"{loc}: sitemap {sorted(in_sitemap)} vs page {sorted(in_page)}"
            assert "x-default" in in_sitemap, f"{loc}: no x-default"

        for path in ("/", "/faq", "/en", "/en/faq"):
            html = client.get(path).text
            assert f'<link rel="canonical" href="{SITE}' in html, f"{path}: canonical not rewritten"
            assert "localhost" not in html, f"{path}: build-time host leaked into the page"

        robots = client.get("/robots.txt").text
        assert robots.splitlines()[0].strip() == f"# {SITE}", robots.splitlines()[0]
        assert f"Sitemap: {SITE}/sitemap.xml" in robots, robots


def test_app_is_noindex_but_not_blocked() -> None:
    """
    robots.txt must not disallow /app.

    A page blocked from crawling can never be read, so its noindex is never
    seen - and Google will happily list the bare URL it found via the links on
    the landing page. Blocking is what causes the problem it looks like it
    prevents.
    """
    if not _built():
        print("SKIP frontend/dist not built")
        return
    with _app(PUBLIC_URL=SITE) as client:
        assert "Disallow: /app" not in client.get("/robots.txt").text
        assert "Disallow: /api/" in client.get("/robots.txt").text
        assert 'content="noindex' in client.get("/app").text


def test_verification_file_is_served_only_when_configured() -> None:
    if not _built():
        print("SKIP frontend/dist not built")
        return
    with _app(PUBLIC_URL=SITE, GOOGLE_SITE_VERIFICATION=TOKEN) as client:
        response = client.get(f"/{TOKEN}")
        assert response.status_code == 200, response.status_code
        # Google checks the body, not just that something answered.
        assert response.text == f"google-site-verification: {TOKEN}", repr(response.text)
        assert client.get("/googledeadbeef.html").status_code == 404

    with _app(PUBLIC_URL=SITE, GOOGLE_SITE_VERIFICATION="") as client:
        assert client.get(f"/{TOKEN}").status_code == 404


def test_token_is_accepted_in_every_shape_search_console_shows_it() -> None:
    from app.config import _normalise_verification as norm

    for raw in ("google1a2b.html", "1a2b", "google1a2b", "google-site-verification: google1a2b.html"):
        assert norm(raw) == "google1a2b.html", f"{raw!r} -> {norm(raw)!r}"

    # A token becomes a route, so anything that is not one must be dropped
    # rather than half-accepted.
    for raw in ("", "   ", "../../etc/passwd", "google../evil.html", "google<script>.html"):
        assert norm(raw) == "", f"{raw!r} -> {norm(raw)!r}"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK  {name}")
