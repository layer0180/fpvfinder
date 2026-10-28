"""
HTML for the region pages, from data/regions.json (see app/regions.py).

Rendered by the server rather than at build time because the data changes
monthly with the OSM import, independently of the site build. Everything that
comes from OSM (names) is escaped.
"""

from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any

from app import texts

GUIDE_PATH = {"de": "/ratgeber/wo-darf-ich-fpv-fliegen", "en": "/en/guides/where-to-fly-fpv-germany"}
REGION_PATH = {"de": "/regionen", "en": "/en/regions"}
APP_PATH = {"de": "/app", "en": "/en/app"}
SCORE_HEX = ["#45307f", "#2f62a8", "#1d8f87", "#4cab4a", "#b5d334"]

esc = html.escape


class Regions:
    """regions.json, reloaded when the file changes (the monthly refresh)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._mtime = -1.0
        self.data: dict[str, Any] = {"regions": []}
        self.by_slug: dict[str, dict[str, Any]] = {}

    def load(self) -> "Regions":
        try:
            mtime = self.path.stat().st_mtime
        except FileNotFoundError:
            self.data, self.by_slug, self._mtime = {"regions": []}, {}, -1.0
            return self
        if mtime != self._mtime:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            self.by_slug = {r["slug"]: r for r in self.data.get("regions", [])}
            self._mtime = mtime
        return self


def _fill(template: str, **values: Any) -> str:
    for key, value in values.items():
        template = template.replace("{" + key + "}", str(value))
    return template


def _number(value: float, lang: str) -> str:
    text = f"{value:,.0f}"
    return text.replace(",", ".") if lang == "de" else text


def _map_svg(region: dict[str, Any], spots: list[dict[str, Any]]) -> str:
    """Radius, city centre and numbered spots - positions to scale, no tiles."""
    size, pad = 320, 24
    r_px = size / 2 - pad
    km_per_deg_lat = 111.32
    km_per_deg_lon = 111.32 * math.cos(math.radians(region["lat"]))
    parts = [
        f'<svg class="region-map" viewBox="0 0 {size} {size}" role="img" aria-label="{esc(region["name"])}">',
        f'<circle class="r-area" cx="{size / 2}" cy="{size / 2}" r="{r_px}"/>',
        f'<circle class="r-city" cx="{size / 2}" cy="{size / 2}" r="4"/>',
        f'<text class="r-label" x="{size / 2}" y="{size / 2 - 10}" text-anchor="middle">{esc(region["name"])}</text>',
    ]
    for n, spot in enumerate(spots, 1):
        dx = (spot["lon"] - region["lon"]) * km_per_deg_lon / region["radius_km"] * r_px
        dy = (spot["lat"] - region["lat"]) * km_per_deg_lat / region["radius_km"] * r_px
        x, y = size / 2 + dx, size / 2 - dy
        colour = SCORE_HEX[min(4, int(spot["score"] * 5))]
        parts.append(f'<circle class="r-pin" cx="{x:.1f}" cy="{y:.1f}" r="11" fill="{colour}"/>')
        parts.append(f'<text class="r-n" x="{x:.1f}" y="{y + 4.5:.1f}" text-anchor="middle">{n}</text>')
    parts.append("</svg>")
    return "".join(parts)


def region_page(region: dict[str, Any], all_regions: list[dict[str, Any]], data: dict[str, Any], lang: str) -> dict[str, str]:
    """-> title, description, path and body HTML for one region."""
    t = texts.texts(lang)["regionPage"]
    facts = region["facts"]
    r = _number(region["radius_km"], lang)
    spots = region["spots"]

    body = [
        f'<p class="breadcrumb"><a href="{"/" if lang == "de" else "/en"}">{"Start" if lang == "de" else "Home"}</a> › '
        f'<a href="{REGION_PATH[lang]}">{"Regionen" if lang == "de" else "Regions"}</a></p>',
        f"<h1>{esc(_fill(t['h1'], city=region['name']))}</h1>",
        f'<p class="lead">{esc(_fill(t["lead"], r=r, city=region["name"], points=_number(facts["points"], lang), good=_number(facts["good_spots"], lang), blocked=round(facts["blocked_share"] * 100)))}</p>',
        _map_svg(region, spots),
        f"<h2>{t['spotsH2']}</h2>",
        '<ol class="region-spots">',
    ]
    for n, spot in enumerate(spots, 1):
        name = spot.get("area_name") or texts.category(spot["category"], lang)
        where = _fill(t["near"], place=spot["place"]) if spot.get("place") else ""
        score = round(spot["score"] * 100)
        reasons = "".join(f"<li>{esc(texts.reason(x, lang))}</li>" for x in spot["reasons"])
        watch = [texts.warning(w, lang) for w in spot["warnings"] if w.get("level") == "warning"]
        finder = (
            f"{APP_PATH[lang]}?lat={region['lat']:.4f}&lon={region['lon']:.4f}&r={region['radius_km']:g}"
            f"&spot={spot['lat']:.5f},{spot['lon']:.5f}&utm_source=region"
        )
        route = f"https://www.google.com/maps/dir/?api=1&destination={spot['lat']:.6f},{spot['lon']:.6f}"
        body.append(
            "<li>"
            f'<h3><span class="result-rank" data-step="{min(4, int(spot["score"] * 5))}">{n}</span>'
            f"{esc(name)} {esc(where)}<span class=\"r-score\">{score}/100</span></h3>"
            f"<ul>{reasons}</ul>"
            + (f'<p class="r-watch">{t["watch"]} {esc(" ".join(watch))}</p>' if watch else "")
            + f'<p class="r-links"><a class="btn btn-primary" href="{esc(finder)}">{t["open"]}</a>'
            f'<a class="btn" href="{esc(route)}" rel="noopener">{t["route"]}</a></p>'
            "</li>"
        )
    body.append("</ol>")

    body.append(f"<h2>{t['areaH2']}</h2>")
    if facts["nature_reserves"]:
        names = ", ".join(facts["nature_reserves"][:4])
        body.append(f"<p>{esc(_fill(t['reserves'], names=names))}</p>")
    if facts["aerodromes"]:
        names = ", ".join(facts["aerodromes"][:4])
        body.append(f"<p>{esc(_fill(t['aerodromes'], names=names))}</p>")
    body.append(f'<p>{t["always"]} <a href="{GUIDE_PATH[lang]}">{t["guides"]}</a></p>')

    # The nearest pages, across state borders: Mainz links to Wiesbaden.
    others = [x for x in all_regions if x["slug"] != region["slug"]]
    neighbours = sorted(others, key=lambda x: (x["lat"] - region["lat"]) ** 2 + ((x["lon"] - region["lon"]) * 0.65) ** 2)[:8]
    if neighbours:
        body.append(f"<h2>{esc(t['otherH2'])}</h2><ul>")
        body.extend(f'<li><a href="{REGION_PATH[lang]}/{x["slug"]}">{esc(x["name"])}</a></li>' for x in neighbours)
        body.append("</ul>")

    body.append(f'<p><a class="btn" href="{APP_PATH[lang]}">{t["searchOwn"]}</a></p>')
    body.append(f'<p class="muted">{esc(_fill(t["dataNote"], date=data.get("generated_at", ""), data=(data.get("data_timestamp") or "")[:10]))}</p>')

    return {
        "title": _fill(t["title"], city=region["name"]),
        "description": _fill(t["description"], good=facts["good_spots"], r=r, city=region["name"]),
        "path": f"/{region['slug']}",
        "body": "".join(body),
    }


def index_page(data: dict[str, Any], lang: str) -> dict[str, str]:
    t = texts.texts(lang)["regionPage"]
    regions = sorted(data.get("regions", []), key=lambda r: (r["state"], r["name"]))
    body = [f"<h1>{t['indexH1']}</h1>", f'<p class="lead">{t["indexLead"]}</p>']
    state = None
    for region in regions:
        if region["state"] != state:
            if state is not None:
                body.append("</ul>")
            state = region["state"]
            body.append(f'<h2>{esc(state)}</h2><ul class="region-index">')
        good = _fill(t["goodSpots"], n=_number(region["facts"]["good_spots"], lang))
        body.append(f'<li><a href="{REGION_PATH[lang]}/{region["slug"]}">{esc(region["name"])}</a> <span class="muted">· {good}</span></li>')
    if state is not None:
        body.append("</ul>")
    if not regions:
        body.append(f'<p>{t["empty"]}</p><p><a class="btn btn-primary" href="{APP_PATH[lang]}">{t["searchOwn"]}</a></p>')
    return {
        "title": t["indexTitle"],
        "description": _fill(t["indexDescription"], count=len(regions)),
        "path": "",
        "body": "".join(body),
    }
