"""
Images: the site's preview cards, a card per shared spot, and the app icons.

    GET /og/site-de.png        1200x630 preview of the site
    GET /og/s/<id>.png         1200x630 preview of a shared spot
    GET /og/s/<id>/story.png   1080x1920 story card (TikTok, Instagram)
    python -m app.cards icons web/public/icons

The map on a spot card is drawn from the OSM data the search uses anyway -
forest, water, fields, roads, paths around the spot - so it needs no map
tiles from anyone, looks the same everywhere, and costs a few milliseconds.
Without a local OSM store the card simply has a plain background.
"""

from __future__ import annotations

import io
import math
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from app import texts
from app.osm.codec import latlon

# Brand colours, from web/src/styles/global.css (dark theme).
BG = (12, 16, 21)
SURFACE = (21, 27, 34)
TEXT = (232, 237, 242)
MUTED = (154, 166, 178)
ACCENT = (255, 138, 61)
SCORE = [(69, 48, 127), (47, 98, 168), (29, 143, 135), (76, 171, 74), (181, 211, 52)]
BLOCKED = (138, 146, 156)

# Map palette - muted, so pin and text stay in front.
MAP = {
    "land": (30, 38, 34),
    "forest": (34, 64, 44),
    "field": (44, 48, 36),
    "water": (34, 62, 96),
    "built": (52, 52, 58),
    "road": (120, 128, 138),
    "path": (150, 128, 96),
    "building": (78, 80, 88),
}

FONT_PATHS = {
    True: [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ],
    False: [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ],
}


@lru_cache(maxsize=32)
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for path in FONT_PATHS[bold]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def score_colour(score: float, blocked: bool) -> tuple[int, int, int]:
    return BLOCKED if blocked else SCORE[min(4, int(score * 5))]


def png(image: Image.Image) -> bytes:
    out = io.BytesIO()
    image.save(out, "PNG", optimize=True)
    return out.getvalue()


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------
def draw_logo(draw: ImageDraw.ImageDraw, cx: float, cy: float, size: float, colour=ACCENT, dot=TEXT) -> None:
    """The quad mark from BrandMark.astro, scaled from its 32-unit viewBox."""
    k = size / 32
    w = max(2, round(2.4 * k))
    draw.line([(cx - 7 * k, cy - 7 * k), (cx + 7 * k, cy + 7 * k)], fill=colour, width=w)
    draw.line([(cx + 7 * k, cy - 7 * k), (cx - 7 * k, cy + 7 * k)], fill=colour, width=w)
    for dx, dy in ((-9, -9), (9, -9), (-9, 9), (9, 9)):
        r = 5 * k
        draw.ellipse([cx + dx * k - r, cy + dy * k - r, cx + dx * k + r, cy + dy * k + r], outline=colour, width=w)
    r = 3.4 * k
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=dot)


# Check marks and crosses are drawn, not typed: many fonts lack U+2713/U+2715
# and Pillow renders a missing glyph as an empty box.
def draw_check(draw: ImageDraw.ImageDraw, x: float, y: float, size: float, colour) -> None:
    w = max(3, round(size * 0.16))
    draw.line([(x, y + size * 0.55), (x + size * 0.38, y + size * 0.9), (x + size, y + size * 0.15)], fill=colour, width=w, joint="curve")


def draw_cross(draw: ImageDraw.ImageDraw, cx: float, cy: float, size: float, colour) -> None:
    w = max(3, round(size * 0.14))
    h = size / 2
    draw.line([(cx - h, cy - h), (cx + h, cy + h)], fill=colour, width=w)
    draw.line([(cx + h, cy - h), (cx - h, cy + h)], fill=colour, width=w)


def draw_ring(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float, score: float, blocked: bool) -> None:
    width = max(6, round(r * 0.18))
    box = [cx - r, cy - r, cx + r, cy + r]
    draw.ellipse(box, outline=SURFACE, width=width)
    if blocked:
        draw_cross(draw, cx, cy, r * 0.7, TEXT)
        return
    draw.arc(box, -90, -90 + 360 * score, fill=score_colour(score, blocked), width=width)
    draw.text((cx, cy), str(round(score * 100)), font=font(round(r * 0.9), True), fill=TEXT, anchor="mm")


def wrap(text: str, fnt: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines: list[str] = []
    line = ""
    for word in text.split():
        probe = f"{line} {word}".strip()
        if fnt.getlength(probe) <= width:
            line = probe
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


# ---------------------------------------------------------------------------
# Map from OSM elements
# ---------------------------------------------------------------------------
FOREST = {"forest", "wood", "scrub", "orchard"}
FIELDS = {"farmland", "meadow", "grassland", "grass", "heath", "vineyard"}
BUILT = {"residential", "industrial", "commercial", "retail", "farmyard"}
MAJOR_ROADS = {"motorway", "trunk", "primary", "secondary", "tertiary"}


def _kind(tags: dict[str, str]) -> str | None:
    if tags.get("natural") in ("water", "wetland") or tags.get("landuse") in ("basin", "reservoir"):
        return "water"
    if tags.get("landuse") in FOREST or tags.get("natural") in FOREST:
        return "forest"
    if tags.get("landuse") in FIELDS or tags.get("natural") in FIELDS:
        return "field"
    if tags.get("landuse") in BUILT:
        return "built"
    return None


def draw_map(img: Image.Image, box: tuple[int, int, int, int], lat: float, lon: float, metres: float) -> bool:
    """
    Paints the OSM surroundings of (lat, lon) into ``box`` of ``img``, the box
    spanning ``metres`` horizontally. Returns False when there is no data.
    """
    from app.osm.store import get_store

    store = get_store()
    if store is None:
        return False
    x0, y0, x1, y1 = box
    width, height = x1 - x0, y1 - y0
    scale = width / metres
    cos_lat = math.cos(math.radians(lat))
    half_lat = (height / scale) / 2 / 111_320
    half_lon = (metres / 2) / (111_320 * cos_lat)
    deg = store.tile_deg
    elements: dict[tuple[str, int], dict[str, Any]] = {}
    for iy in range(math.floor((lat - half_lat) / deg), math.floor((lat + half_lat) / deg) + 1):
        for ix in range(math.floor((lon - half_lon) / deg), math.floor((lon + half_lon) / deg) + 1):
            for el in store.get(ix, iy) or []:
                elements[(el["type"], el["id"])] = el
    if not elements:
        return False

    # Draw at 2x and scale down: Pillow has no anti-aliasing for polygons.
    ss = 2
    layer = Image.new("RGB", (width * ss, height * ss), MAP["land"])
    d = ImageDraw.Draw(layer)

    def xy(p: dict[str, float]) -> tuple[float, float]:
        return (
            ((p["lon"] - lon) * 111_320 * cos_lat * scale + width / 2) * ss,
            (height / 2 - (p["lat"] - lat) * 111_320 * scale) * ss,
        )

    def line(geometry: Any) -> list[tuple[float, float]]:
        lats, lons = latlon(geometry)
        xs = ((lons - lon) * 111_320 * cos_lat * scale + width / 2) * ss
        ys = (height / 2 - (lats - lat) * 111_320 * scale) * ss
        return list(zip(xs.tolist(), ys.tolist()))

    def rings(el: dict[str, Any]) -> list[list[tuple[float, float]]]:
        if "geometry" in el:
            return [line(el["geometry"])]
        return [line(m["geometry"]) for m in el.get("members", []) if m.get("geometry") is not None]

    # Areas first, in painting order, then lines on top.
    for kind in ("field", "built", "forest", "water"):
        for el in elements.values():
            if _kind(el.get("tags", {})) != kind:
                continue
            for ring in rings(el):
                if len(ring) >= 4 and ring[0] == ring[-1]:
                    d.polygon(ring, fill=MAP[kind])
    for el in elements.values():
        tags = el.get("tags", {})
        if "center" in el and "building" in tags:
            x, y = xy(el["center"])
            r = 3 * ss
            d.rectangle([x - r, y - r, x + r, y + r], fill=MAP["building"])
    for el in elements.values():
        tags = el.get("tags", {})
        highway = tags.get("highway")
        if not highway or "geometry" not in el:
            continue
        points = line(el["geometry"])
        if highway in MAJOR_ROADS:
            d.line(points, fill=MAP["road"], width=7 * ss, joint="curve")
        elif highway in ("unclassified", "residential", "service", "living_street"):
            d.line(points, fill=MAP["road"], width=4 * ss, joint="curve")
        else:
            d.line(points, fill=MAP["path"], width=2 * ss)
    img.paste(layer.resize((width, height), Image.LANCZOS), (x0, y0))
    return True


def draw_pin(draw: ImageDraw.ImageDraw, x: float, y: float, r: float, colour) -> None:
    draw.ellipse([x - r * 2.2, y - r * 2.2, x + r * 2.2, y + r * 2.2], outline=ACCENT, width=max(3, round(r * 0.25)))
    draw.ellipse([x - r, y - r, x + r, y + r], fill=colour, outline=BG, width=max(2, round(r * 0.2)))


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------
SITE_COPY = {
    "de": ("Finde FPV-Spots, an denen dir niemand zuschaut", "Kostenlos · ohne Anmeldung · ganz Deutschland"),
    "en": ("Find FPV spots where nobody is watching", "Free · no sign-up · all of Germany"),
}


def site_card(lang: str, host: str) -> bytes:
    title, sub = SITE_COPY.get(lang, SITE_COPY["de"])
    img = Image.new("RGB", (1200, 630), BG)
    d = ImageDraw.Draw(img)
    # A row of score pins as a quiet motif on the right.
    for i, (x, y) in enumerate([(930, 170), (1060, 300), (880, 380), (1010, 470), (1110, 140)]):
        draw_pin(d, x, y, 22 - i * 2, SCORE[4 - i % 3])
    draw_logo(d, 110, 120, 84)
    d.text((170, 120), "FPV Flying Spot Finder", font=font(36, True), fill=TEXT, anchor="lm")
    y = 230
    for line in wrap(title, font(64, True), 700):
        d.text((80, y), line, font=font(64, True), fill=TEXT)
        y += 76
    d.text((80, y + 24), sub, font=font(30), fill=ACCENT)
    d.text((80, 570), host, font=font(26), fill=MUTED)
    return png(img)


def spot_card(share: dict[str, Any], lang: str, host: str, story: bool = False) -> bytes:
    spot = share["spot"]
    t = texts.texts(lang)["share"]
    score, blocked = float(spot["score"]), bool(spot["blocked"])
    name = spot.get("area_name") or texts.category(spot["category"], lang)
    reasons = [texts.reason(r, lang) for r in spot.get("reasons", [])][:3]

    if story:
        w, h = 1080, 1920
        img = Image.new("RGB", (w, h), BG)
        d = ImageDraw.Draw(img)
        map_box = (0, 0, w, 1180)
        has_map = draw_map(img, map_box, spot["lat"], spot["lon"], 1400)
        d = ImageDraw.Draw(img)
        if has_map:
            draw_pin(d, w / 2, 590, 26, score_colour(score, blocked))
        # Fade the map into the text area.
        fade = Image.new("L", (1, 220))
        for i in range(220):
            fade.putpixel((0, i), int(255 * (i / 219) ** 1.6))
        img.paste(Image.new("RGB", (w, 220), BG), (0, 960), fade.resize((w, 220)))
        d = ImageDraw.Draw(img)
        draw_logo(d, 96, 110, 72)
        d.text((150, 110), "FPV Spot Finder", font=font(40, True), fill=TEXT, anchor="lm")
        draw_ring(d, 170, 1300, 110, score, blocked)
        y = 1220
        for line in wrap(name, font(64, True), 690)[:2]:
            d.text((330, y), line, font=font(64, True), fill=TEXT)
            y += 74
        d.text((330, y + 8), f"{round(score * 100)}/100 {t['points']}", font=font(40), fill=MUTED)
        y = 1480
        for reason in reasons:
            draw_check(d, 80, y + 10, 38, SCORE[4])
            for j, line in enumerate(wrap(reason, font(44), 880)[:2]):
                d.text((140, y + j * 54), line, font=font(44), fill=TEXT)
            y += 54 * min(2, len(wrap(reason, font(44), 880))) + 26
        d.text((w / 2, 1830), host, font=font(38, True), fill=ACCENT, anchor="mm")
        return png(img)

    w, h = 1200, 630
    img = Image.new("RGB", (w, h), BG)
    has_map = draw_map(img, (620, 0, 1200, 630), spot["lat"], spot["lon"], 1100)
    d = ImageDraw.Draw(img)
    if has_map:
        draw_pin(d, 910, 315, 18, score_colour(score, blocked))
    draw_logo(d, 84, 80, 56)
    d.text((126, 80), "FPV Spot Finder", font=font(30, True), fill=TEXT, anchor="lm")
    draw_ring(d, 150, 245, 82, score, blocked)
    y = 180
    for line in wrap(name, font(48, True), 330)[:2]:
        d.text((262, y), line, font=font(48, True), fill=TEXT)
        y += 56
    d.text((262, y + 4), f"{round(score * 100)}/100 {t['points']}", font=font(28), fill=MUTED)
    y = 380
    for reason in reasons:
        line = wrap(reason, font(30), 500)[0]
        draw_check(d, 68, y + 8, 26, SCORE[4])
        d.text((108, y), line, font=font(30), fill=TEXT)
        y += 46
    d.text((68, 572), host, font=font(26), fill=ACCENT)
    return png(img)


# ---------------------------------------------------------------------------
# App icons
# ---------------------------------------------------------------------------
def icon(size: int, maskable: bool = False) -> bytes:
    img = Image.new("RGB", (size, size), BG)
    d = ImageDraw.Draw(img)
    # Maskable icons get cropped to a circle by some launchers: keep the mark
    # inside the central 80 % "safe zone".
    draw_logo(d, size / 2, size / 2, size * (0.56 if maskable else 0.78))
    return png(img)


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "icons":
        out = Path(argv[1])
        out.mkdir(parents=True, exist_ok=True)
        for name, data in {
            "icon-180.png": icon(180),
            "icon-192.png": icon(192),
            "icon-512.png": icon(512),
            "icon-maskable-512.png": icon(512, maskable=True),
        }.items():
            (out / name).write_bytes(data)
            print(f"wrote {out / name}")
        return 0
    print("usage: python -m app.cards icons <directory>")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
