"""
The website side of the backend (app/web.py), against a tiny fake build.

These guard things that break silently: a sitemap full of localhost URLs, a
canonical link to the wrong host, a page answering HEAD with 405, an inline
script the CSP blocks - all of them still "work" in a browser test.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import web
from app.services import appdb

BAKED = "http://localhost:8000"
PUBLIC = "https://spots.example.test"

PAGE = """<!doctype html><html><head><link rel="canonical" href="{base}/faq">
<script type="application/ld+json">{{"@type":"FAQPage"}}</script>
<script type="module">console.log("island")</script></head><body>FAQ</body></html>"""


@pytest.fixture()
def client(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    for rel, body in {
        "robots.txt": f"# {BAKED}\nSitemap: {BAKED}/sitemap.xml\n",
        "sitemap.xml": f"<urlset><url><loc>{BAKED}/faq</loc></url></urlset>",
        "index.html": PAGE.format(base=BAKED),
        "faq/index.html": PAGE.format(base=BAKED),
        "404.html": "<html><body>missing</body></html>",
        "impressum/index.html": "<html><body><article><!--@@SERVER_CONTENT@@--></article></body></html>",
        "share-template/index.html": "<html><head><title>@@SHARE_TITLE@@</title></head><body><!--@@SERVER_CONTENT@@--></body></html>",
        "en/share-template/index.html": "<html><head><title>@@SHARE_TITLE@@</title></head><body><!--@@SERVER_CONTENT@@--></body></html>",
        "assets/app.123.js": "console.log(1)",
    }.items():
        (dist / rel).parent.mkdir(parents=True, exist_ok=True)
        (dist / rel).write_text(body, encoding="utf-8")
    content = tmp_path / "content"
    content.mkdir()
    (content / "imprint.de.md").write_text("# Impressum\n\n{{OPERATOR}}\n\nKontakt: {{PROJECT_URL}}\n<!-- operator note -->\n", encoding="utf-8")

    monkeypatch.setattr(web, "DIST", dist)
    monkeypatch.setattr(web, "BAKED_URL", BAKED)
    monkeypatch.setattr(web, "SERVE_URL", PUBLIC)
    monkeypatch.setattr(web.SETTINGS, "content_dir", content)
    monkeypatch.setattr(appdb, "_db", appdb.AppDB(tmp_path / "app.sqlite"))
    web._text.cache_clear()
    from app.main import app

    with TestClient(app) as c:
        yield c
    web._text.cache_clear()


def test_absolute_urls_are_rewritten_to_public_url(client):
    page = client.get("/faq").text
    assert f'href="{PUBLIC}/faq"' in page and BAKED not in page
    assert PUBLIC in client.get("/sitemap.xml").text
    assert client.get("/robots.txt").text.startswith(f"# {PUBLIC}")


def test_head_and_clean_urls(client):
    assert client.head("/").status_code == 200
    redirect = client.get("/faq/", follow_redirects=False)
    assert redirect.status_code == 301 and redirect.headers["location"] == "/faq"


def test_unknown_paths_get_the_html_404(client):
    response = client.get("/no-such-page")
    assert response.status_code == 404 and "missing" in response.text
    assert client.get("/share-template").status_code == 404
    assert client.get("/../backend/app/main.py").status_code == 404


def test_unknown_api_paths_stay_json(client):
    response = client.get("/api/nope")
    assert response.status_code == 404 and response.headers["content-type"].startswith("application/json")


def test_csp_allows_exactly_the_inline_scripts(client):
    csp = client.get("/faq").headers["content-security-policy"]
    assert csp.count("'sha256-") == 1  # the module script, not the JSON-LD block
    assert "'unsafe-inline'" not in csp.split("script-src")[1].split(";")[0]


def test_hashed_assets_are_immutable(client):
    assert "immutable" in client.get("/assets/app.123.js").headers["cache-control"]


def test_legal_page_renders_markdown_without_operator_notes(client):
    page = client.get("/impressum").text
    assert "<h1>Impressum</h1>" in page
    assert "github.com" in page and "operator note" not in page
    # No content file for privacy -> 404, not an empty page.
    assert client.get("/datenschutz").status_code == 404


def test_imprint_takes_name_and_address_from_settings(client, monkeypatch):
    assert "[OPERATOR_NAME / OPERATOR_ADDRESS]" in client.get("/impressum").text
    monkeypatch.setattr(web.SETTINGS, "operator_name", "Erika Muster")
    monkeypatch.setattr(web.SETTINGS, "operator_address", "Hauptstr. 1, 72764 Reutlingen")
    page = client.get("/impressum").text
    assert "<strong>Erika Muster</strong><br" in page and "Hauptstr. 1<br" in page and "72764 Reutlingen" in page


def test_share_page_is_filled_and_escaped(client):
    share_id = appdb.get_db().create_share(
        {
            "spot": {
                "lat": 48.4, "lon": 9.4, "score": 0.91, "solitude": 0.9, "flyability": 0.9, "blocked": False,
                "category": "meadow", "area_name": "<b>Wiese</b>", "distances": {},
                "warnings": [{"level": "warning", "code": "path_near", "params": {"distance_m": 42}, "text": ""}],
                "reasons": [{"code": "far_from_paths", "params": {"distance_m": 420}}],
            },
            "search": {"lat": 48.4, "lon": 9.4, "radius_km": 5, "time_profile": "weekend_afternoon"},
        }
    )
    page = client.get(f"/s/{share_id}", headers={"accept-language": "de-DE"}).text
    assert "Score 91/100" in page
    assert "&lt;b&gt;Wiese&lt;/b&gt;" in page and "<b>Wiese</b>" not in page
    assert "Nächster Weg 420 m entfernt" in page
    assert "Weg 40 m entfernt" in page
    assert "spot=48.40000,9.40000" in page
    assert client.get("/s/doesnotexist").status_code == 404


def test_no_analytics_unless_configured(client, monkeypatch):
    page = client.get("/faq")
    assert "data-website-id" not in page.text
    assert "stats." not in page.headers["content-security-policy"]

    monkeypatch.setattr(web.SETTINGS, "analytics_script_url", "https://stats.example.test/script.js")
    monkeypatch.setattr(web.SETTINGS, "analytics_website_id", "abc-123")
    page = client.get("/faq")
    assert 'data-website-id="abc-123"' in page.text
    csp = page.headers["content-security-policy"]
    assert "https://stats.example.test" in csp.split("script-src")[1].split(";")[0]
    assert "https://stats.example.test" in csp.split("connect-src")[1].split(";")[0]


def test_preview_images(client):
    site = client.get("/og/site-de.png")
    assert site.status_code == 200 and site.headers["content-type"] == "image/png"
    assert site.content[:8] == b"\x89PNG\r\n\x1a\n"

    share_id = appdb.get_db().create_share(
        {
            "spot": {"lat": 48.4, "lon": 9.4, "score": 0.5, "blocked": True, "category": "forest",
                     "area_name": "", "warnings": [], "reasons": [], "distances": {}},
            "search": {"lat": 48.4, "lon": 9.4, "radius_km": 5, "time_profile": "weekend_afternoon"},
        }
    )
    from PIL import Image
    import io

    story = client.get(f"/og/s/{share_id}/story.png")
    assert Image.open(io.BytesIO(story.content)).size == (1080, 1920)
    assert Image.open(io.BytesIO(client.get(f"/og/s/{share_id}.png").content)).size == (1200, 630)
    assert client.get("/og/s/unknown1.png").status_code == 404


def test_reason_without_distance_reads_naturally():
    from app import texts

    assert texts.reason({"code": "far_from_settlement", "params": {}}, "de") == "Kein Wohngebiet in der Nähe"
    assert texts.reason({"code": "far_from_settlement", "params": {"distance_m": 1100}}, "de") == "Wohngebiet 1,1 km entfernt"


def test_unnamed_protected_area_reads_naturally():
    from app import texts

    text = texts.warning({"code": "protected_landscape", "params": {"name": ""}}, "de")
    assert text == "In einem Landschaftsschutzgebiet – prüfe die örtlichen Regeln."
    assert "„Biosphäre“" in texts.warning({"code": "protected_strict", "params": {"name": "Biosphäre"}}, "de")


def _region_fixture(path):
    import json as _json

    spot = {
        "lat": 48.80, "lon": 9.10, "score": 0.9, "category": "meadow", "area_name": "<i>Wiese</i>",
        "place": "Ditzingen",
        "reasons": [{"code": "far_from_paths", "params": {"distance_m": 420}}],
        "warnings": [{"level": "warning", "code": "path_near", "params": {"distance_m": 40}}],
    }
    region = {
        "name": "Stuttgart", "slug": "stuttgart", "lat": 48.78, "lon": 9.18, "state": "Baden-Württemberg",
        "radius_km": 10.0, "time_profile": "weekend_afternoon", "spots": [spot],
        "facts": {"points": 422, "blocked_share": 0.46, "good_spots": 73, "nature_reserves": ["Greutterwald"], "aerodromes": []},
    }
    path.write_text(_json.dumps({"generated_at": "2026-10-24", "data_timestamp": "2026-10-20T20:23:47Z", "regions": [region]}), encoding="utf-8")


@pytest.fixture()
def with_regions(client, tmp_path, monkeypatch):
    from app import region_pages

    _region_fixture(tmp_path / "regions.json")
    monkeypatch.setattr(web, "REGIONS", region_pages.Regions(tmp_path / "regions.json"))
    (web.DIST / "region-template").mkdir(exist_ok=True)
    (web.DIST / "region-template" / "index.html").write_text(
        "<html><head><title>@@REGION_TITLE@@</title><link rel=canonical href='/regionen@@REGION_PATH@@'></head>"
        "<body><!--@@SERVER_CONTENT@@--></body></html>",
        encoding="utf-8",
    )
    web._text.cache_clear()
    return client


def test_region_pages(with_regions):
    page = with_regions.get("/regionen/stuttgart").text
    assert "<title>FPV-Spots rund um Stuttgart" in page
    assert "/regionen/stuttgart" in page
    assert "&lt;i&gt;Wiese&lt;/i&gt; bei Ditzingen" in page
    assert "Greutterwald" in page and '"ItemList"' in page
    assert with_regions.get("/regionen").status_code == 200
    assert with_regions.get("/regionen/atlantis").status_code == 404
    assert with_regions.get("/region-template").status_code == 404


def test_sitemap_lists_regions(with_regions):
    xml = with_regions.get("/sitemap.xml").text
    assert f"{PUBLIC}/regionen/stuttgart</loc>" in xml and f"{PUBLIC}/en/regions/stuttgart</loc>" in xml
    assert "<lastmod>2026-10-24</lastmod>" in xml
