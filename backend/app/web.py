"""
Serves the built website (web/dist) next to the API.

Everything a page needs that is only known at runtime happens here:

  * Absolute URLs. The build bakes a placeholder base URL into canonical links,
    hreflang, Open Graph tags and the sitemap; it is swapped for PUBLIC_URL on
    the way out, because a published image cannot know its domain.
  * Pages with server-side content: imprint, privacy and support come from
    Markdown files the operator can mount (backend/content), and /s/<id> is a
    shared spot with its own title, description and preview image.
  * Headers: caching per file type, HEAD for every page, a real 404 page, and
    a Content-Security-Policy that allows exactly the inline scripts of each
    page by hash instead of 'unsafe-inline'.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from markdown_it import MarkdownIt

from app import cards, region_pages, texts
from app.config import BACKEND_DIR, SETTINGS
from app.services.appdb import get_db

DIST = BACKEND_DIR.parent / "web" / "dist"
BUILD_FALLBACK_URL = "http://localhost:8000"
SERVER_CONTENT = "<!--@@SERVER_CONTENT@@-->"

# Clean path -> (content file stem, language). The support page shows funding.md.
LEGAL_PAGES = {
    "impressum": ("imprint", "de"),
    "datenschutz": ("privacy", "de"),
    "unterstuetzen": ("funding", "de"),
    "en/imprint": ("imprint", "en"),
    "en/privacy": ("privacy", "en"),
    "en/support": ("funding", "en"),
}

# Build-internal pages that must not be reachable under their own name.
HIDDEN = {"share-template", "en/share-template", "region-template", "en/region-template", "404"}

REGIONS = region_pages.Regions(SETTINGS.data_dir / "regions.json")

TEXT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".xml": "application/xml; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".webmanifest": "application/manifest+json",
}

router = APIRouter(include_in_schema=False)
_markdown = MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": True}).enable("table")


# ---------------------------------------------------------------------------
# Base URL rewriting
# ---------------------------------------------------------------------------
def _baked_base_url() -> str:
    """robots.txt starts with "# <url>" - the address this build was made for."""
    robots = DIST / "robots.txt"
    if robots.exists():
        first = robots.read_text(encoding="utf-8").partition("\n")[0].strip()
        if first.startswith("#") and "://" in first:
            return first.lstrip("#").strip().rstrip("/")
    return BUILD_FALLBACK_URL


BAKED_URL = _baked_base_url()
SERVE_URL = SETTINGS.public_url.rstrip("/") or BAKED_URL


@lru_cache(maxsize=256)
def _text(relative: str) -> str:
    """A text file from dist/, with the base URL rewritten (cached; dist is immutable)."""
    body = (DIST / relative).read_text(encoding="utf-8")
    return body.replace(BAKED_URL, SERVE_URL) if SERVE_URL != BAKED_URL else body


# ---------------------------------------------------------------------------
# Content-Security-Policy
# ---------------------------------------------------------------------------
_INLINE_SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)([^>]*)>(.*?)</script>", re.S | re.I)


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else ""


@lru_cache(maxsize=256)
def _csp_for(body: str) -> str:
    hashes = []
    for attrs, code in _INLINE_SCRIPT.findall(body):
        # JSON-LD and other data blocks never execute, so CSP ignores them.
        if "application/ld+json" in attrs or "application/json" in attrs:
            continue
        digest = base64.b64encode(hashlib.sha256(code.encode("utf-8")).digest()).decode()
        hashes.append(f"'sha256-{digest}'")
    map_origin = _origin(SETTINGS.map_style_url)
    stats_origin = _origin(SETTINGS.analytics_script_url) if SETTINGS.analytics_enabled else ""
    directives = {
        "default-src": "'self'",
        "script-src": " ".join(["'self'", *hashes, stats_origin]),
        # MapLibre and React set style attributes; that is CSS, not code.
        "style-src": "'self' 'unsafe-inline'",
        "img-src": f"'self' data: blob: {map_origin}",
        "connect-src": f"'self' {map_origin} https://api.open-meteo.com {stats_origin}",
        "worker-src": "'self' blob:",
        "object-src": "'none'",
        "base-uri": "'self'",
        "form-action": "'self'",
        "frame-ancestors": "'self'",
    }
    return "; ".join(f"{k} {v}".strip() for k, v in directives.items())


def _with_analytics(body: str) -> str:
    if not SETTINGS.analytics_enabled:
        return body
    tag = (
        f'<script defer src="{html.escape(SETTINGS.analytics_script_url)}" '
        f'data-website-id="{html.escape(SETTINGS.analytics_website_id)}"></script>'
    )
    return body.replace("</head>", f"{tag}</head>", 1)


def _html(body: str, status: int = 200) -> Response:
    body = _with_analytics(body)
    return Response(
        content=body,
        status_code=status,
        media_type=TEXT_TYPES[".html"],
        headers={"Content-Security-Policy": _csp_for(body), "Cache-Control": "no-cache"},
    )


# ---------------------------------------------------------------------------
# Server-filled pages
# ---------------------------------------------------------------------------
def _analytics_section(lang: str) -> str:
    """content/analytics.<lang>.md when statistics are switched on, else nothing."""
    if not SETTINGS.analytics_enabled:
        return ""
    path = SETTINGS.content_dir / f"analytics.{lang}.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _operator_block() -> str:
    """Name and address for the imprint, one line each; a visible gap when unset."""
    if not SETTINGS.operator_name:
        return "**[OPERATOR_NAME / OPERATOR_ADDRESS]**"
    lines = [f"**{SETTINGS.operator_name}**"] + [part.strip() for part in SETTINGS.operator_address.split(",") if part.strip()]
    # Two trailing spaces: a Markdown line break inside one paragraph.
    return "  \n".join(lines)


def _legal_markdown(stem: str, lang: str) -> str | None:
    """content/<stem>.<lang>.md, else content/<stem>.md; None when missing or empty."""
    for name in (f"{stem}.{lang}.md", f"{stem}.md"):
        path = SETTINGS.content_dir / name
        if path.exists() and path.read_text(encoding="utf-8").strip():
            text = path.read_text(encoding="utf-8")
            # Operator notes are HTML comments; never show them to visitors.
            text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
            for key, value in {
                "PROJECT_URL": SETTINGS.project_url,
                "CONTACT_EMAIL": SETTINGS.contact_email or SETTINGS.project_url,
                "OPERATOR": _operator_block(),
                "PUBLIC_URL": SERVE_URL,
                "DONATE_URL": SETTINGS.donate_url or SETTINGS.project_url,
                # The privacy notice must describe what actually runs.
                "ANALYTICS_SECTION": _analytics_section(lang),
            }.items():
                text = text.replace("{{" + key + "}}", value)
            return text
    return None


def _legal_page(path: str) -> Response:
    stem, lang = LEGAL_PAGES[path]
    markdown = _legal_markdown(stem, lang)
    if markdown is None:
        return _not_found()
    body = _text(f"{path}/index.html").replace(SERVER_CONTENT, _markdown.render(markdown))
    return _html(body)


def _share_lang(request: Request) -> str:
    """
    German unless the visitor clearly prefers English. The link previews in
    chat apps are fetched by crawlers that send English or nothing at all, and
    the people reading those previews are mostly German.
    """
    accept = request.headers.get("accept-language", "").lower().lstrip()
    return "en" if accept.startswith("en") else "de"


def _share_page(share_id: str, request: Request) -> Response:
    share = get_db().get_share(share_id) if re.fullmatch(r"[a-z0-9]{6,12}", share_id) else None
    if share is None:
        return _not_found()
    lang = _share_lang(request)
    t = texts.texts(lang)["share"]
    spot, search = share["spot"], share["search"]
    score = round(spot["score"] * 100)
    cat = texts.category(spot["category"], lang)
    name = spot.get("area_name") or cat
    reasons = [texts.reason(r, lang) for r in spot.get("reasons", [])]
    warnings = [(w.get("level", "info"), texts.warning(w, lang)) for w in spot.get("warnings", [])]
    esc = html.escape

    title = t["title"].replace("{category}", name).replace("{score}", str(score))
    description = t["description"].replace("{score}", str(score)).replace("{reasons}", ", ".join(reasons[:2]) or cat)
    step = "blocked" if spot["blocked"] else str(min(4, int(spot["score"] * 5)))
    app_path = "/app" if lang == "de" else "/en/app"
    finder = (
        f"{app_path}?lat={search['lat']:.4f}&lon={search['lon']:.4f}&r={search['radius_km']:g}"
        f"&spot={spot['lat']:.5f},{spot['lon']:.5f}&utm_source=share"
    )
    route = f"https://www.google.com/maps/dir/?api=1&destination={spot['lat']:.6f},{spot['lon']:.6f}"

    card = [
        '<div class="share-card">',
        '<div class="share-head">',
        f'<div class="share-score" style="--ring:var(--score-{step});--p:{score}%"><span>{"✕" if spot["blocked"] else score}</span></div>',
        f"<div><h1>{esc(name)}</h1><p>{esc(cat)} · {t['blocked'] if spot['blocked'] else f'{score}/100 ' + t['points']}</p></div>",
        "</div>",
    ]
    if reasons:
        card.append(f"<h2>{t['why']}</h2><ul>{''.join(f'<li>{esc(r)}</li>' for r in reasons)}</ul>")
    card.append(f"<h2>{t['watch']}</h2>")
    if warnings:
        items = "".join(f'<li class="warning warning-{esc(level)}">{esc(text)}</li>' for level, text in warnings)
        card.append(f'<ul style="padding:0">{items}</ul>')
    else:
        card.append(f"<p>{t['noWarnings']}</p>")
    card.append(
        f'<div class="share-actions"><a class="btn btn-primary" href="{esc(finder)}">{t["open"]}</a>'
        f'<a class="btn" href="{esc(route)}" rel="noopener">{t["route"]}</a></div>'
        f'<p class="share-note">{t["note"]}</p></div>'
    )

    template = "share-template/index.html" if lang == "de" else "en/share-template/index.html"
    body = (
        _text(template)
        .replace("@@SHARE_TITLE@@", esc(title))
        .replace("@@SHARE_DESCRIPTION@@", esc(description))
        .replace("@@SHARE_ID@@", share_id)
        .replace(SERVER_CONTENT, "".join(card))
    )
    return _html(body)


# ---------------------------------------------------------------------------
# Preview images
# ---------------------------------------------------------------------------
def _host() -> str:
    return urlsplit(SERVE_URL).netloc or "localhost"


@lru_cache(maxsize=4)
def _site_card(lang: str) -> bytes:
    return cards.site_card(lang, _host())


@lru_cache(maxsize=256)
def _spot_card(share_id: str, lang: str, story: bool) -> bytes | None:
    # A share never changes, so its images can be cached for good.
    share = get_db().get_share(share_id)
    return cards.spot_card(share, lang, _host(), story=story) if share else None


def _image(data: bytes) -> Response:
    return Response(data, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


def _og(path: str, request: Request) -> Response:
    """/og/site-<lang>.png, /og/s/<id>.png and /og/s/<id>/story.png"""
    if match := re.fullmatch(r"og/site-(de|en)\.png", path):
        return _image(_site_card(match.group(1)))
    if match := re.fullmatch(r"og/s/([a-z0-9]{6,12})(\.png|/story\.png)", path):
        data = _spot_card(match.group(1), _share_lang(request), story=match.group(2) != ".png")
        if data:
            return _image(data)
    return _not_found()


# ---------------------------------------------------------------------------
# Region pages (data/regions.json, see app/regions.py)
# ---------------------------------------------------------------------------
def _region_response(lang: str, slug: str | None) -> Response:
    regions = REGIONS.load()
    if slug is None:
        page = region_pages.index_page(regions.data, lang)
        items = [
            {"@type": "ListItem", "position": i, "name": r["name"], "url": f"{SERVE_URL}{region_pages.REGION_PATH[lang]}/{r['slug']}"}
            for i, r in enumerate(regions.data["regions"], 1)
        ]
    else:
        region = regions.by_slug.get(slug)
        if region is None:
            return _not_found()
        page = region_pages.region_page(region, regions.data["regions"], regions.data, lang)
        items = [
            {
                "@type": "ListItem",
                "position": i,
                "item": {
                    "@type": "Place",
                    "name": s.get("area_name") or texts.category(s["category"], lang),
                    "geo": {"@type": "GeoCoordinates", "latitude": s["lat"], "longitude": s["lon"]},
                },
            }
            for i, s in enumerate(region["spots"], 1)
        ]
    # Structured data goes into the body: the head is fixed by the template.
    json_ld = json.dumps({"@context": "https://schema.org", "@type": "ItemList", "itemListElement": items}, ensure_ascii=False)
    # "</" inside the JSON must not close the script element.
    safe_json = json_ld.replace("</", "<\\/")
    body_html = page["body"] + f'<script type="application/ld+json">{safe_json}</script>'
    template = "region-template/index.html" if lang == "de" else "en/region-template/index.html"
    body = (
        _text(template)
        .replace("@@REGION_TITLE@@", html.escape(page["title"]))
        .replace("@@REGION_DESCRIPTION@@", html.escape(page["description"]))
        .replace("@@REGION_PATH@@", page["path"])
        .replace(SERVER_CONTENT, body_html)
    )
    return _html(body)


def _sitemap_with_regions() -> str:
    """The built sitemap plus one entry per region page in both languages."""
    body = _text("sitemap.xml")
    regions = REGIONS.load()
    if not regions.by_slug:
        return body
    lastmod = regions.data.get("generated_at", "")
    entries = []
    for path in ["", *(f"/{slug}" for slug in regions.by_slug)]:
        de, en = f"{SERVE_URL}/regionen{path}", f"{SERVE_URL}/en/regions{path}"
        links = "\n".join(
            f'    <xhtml:link rel="alternate" hreflang="{code}" href="{href}"/>'
            for code, href in (("de", de), ("en", en), ("x-default", de))
        )
        for loc in (de, en):
            entries.append(f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{lastmod}</lastmod>\n{links}\n  </url>")
    return body.replace("</urlset>", "\n".join(entries) + "\n</urlset>")


def _not_found() -> Response:
    if (DIST / "404.html").exists():
        return _html(_text("404.html"), status=404)
    return Response("Not found", status_code=404, media_type="text/plain")


# ---------------------------------------------------------------------------
# Catch-all
# ---------------------------------------------------------------------------
def _resolve(path: str) -> Path | None:
    """Clean URL -> file in dist, refusing anything that escapes it."""
    for candidate in (DIST / path / "index.html", DIST / path):
        try:
            candidate.resolve().relative_to(DIST.resolve())
        except ValueError:
            return None
        if candidate.is_file():
            return candidate
    return None


@router.api_route("/{path:path}", methods=["GET", "HEAD"])
async def serve(path: str, request: Request) -> Response:
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Unknown API endpoint.")
    if not DIST.exists():
        # Development: the site runs on the Astro dev server instead.
        return RedirectResponse("/docs")

    # One spelling per page: /faq, not /faq/ or /faq/index.html.
    clean = path.removesuffix("index.html").rstrip("/")
    if clean != path:
        query = f"?{request.url.query}" if request.url.query else ""
        return RedirectResponse(f"/{clean}{query}", status_code=301)

    if path.startswith("s/"):
        return _share_page(path[2:], request)
    if path.startswith("og/"):
        return _og(path, request)
    if path in ("regionen", "en/regions"):
        return _region_response("de" if path == "regionen" else "en", None)
    if path.startswith(("regionen/", "en/regions/")):
        lang = "de" if path.startswith("regionen/") else "en"
        return _region_response(lang, path.rsplit("/", 1)[1])
    if path == "sitemap.xml" and (DIST / "sitemap.xml").exists():
        return Response(_sitemap_with_regions(), media_type=TEXT_TYPES[".xml"], headers={"Cache-Control": "public, max-age=3600"})
    if path in LEGAL_PAGES:
        return _legal_page(path)
    if path in HIDDEN:
        return _not_found()

    target = _resolve(path)
    if target is None:
        return _not_found()

    relative = target.relative_to(DIST).as_posix()
    suffix = target.suffix
    if suffix == ".html":
        return _html(_text(relative))
    if suffix in TEXT_TYPES:
        return Response(_text(relative), media_type=TEXT_TYPES[suffix], headers={"Cache-Control": "public, max-age=3600"})
    # Hashed build output never changes under the same name.
    cache = "public, max-age=31536000, immutable" if relative.startswith("assets/") else "public, max-age=86400"
    return FileResponse(target, headers={"Cache-Control": cache})
