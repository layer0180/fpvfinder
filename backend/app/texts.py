"""
The visitor-facing wording of the backend's codes, from shared/i18n - the
same files the finder uses, so a shared link and the app say the same thing.
Only the share page and its preview need it; the API itself returns codes.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from app.config import BACKEND_DIR

SHARED_DIR = BACKEND_DIR.parent / "shared" / "i18n"
LANGS = ("de", "en")


@lru_cache(maxsize=None)
def texts(lang: str) -> dict[str, Any]:
    return json.loads((SHARED_DIR / f"{lang if lang in LANGS else 'de'}.json").read_text(encoding="utf-8"))


def format_distance(metres: float, lang: str) -> str:
    """'820 m' / '1,4 km' - mirrors formatDistance in web/src/finder/i18n.ts."""
    if metres >= 45_000:
        return texts(lang)["far"]
    if metres >= 1000:
        value = f"{metres / 1000:.1f}".rstrip("0").rstrip(".")
        return f"{value.replace('.', ',') if lang == 'de' else value} km"
    return f"{round(metres / 10) * 10:.0f} m"


def category(code: str, lang: str) -> str:
    return texts(lang)["categories"].get(code, code)


def _fill(template: str, params: dict[str, Any], lang: str) -> str:
    def value(match: re.Match[str]) -> str:
        key = match.group(1)
        if key == "distance":
            return format_distance(float(params.get("distance_m", 0)), lang)
        if key == "limit":
            return format_distance(float(params.get("limit_m", 0)), lang)
        if key == "category":
            return category(str(params.get("category", "")), lang)
        if key == "kind":
            kind = str(params.get("kind", ""))
            return texts(lang)["structureKinds"].get(kind, kind)
        return str(params.get(key, ""))

    return re.sub(r"\{(\w+)\}", value, template)


def warning(item: dict[str, Any], lang: str) -> str:
    # Mirrors warningText in web/src/finder/i18n.ts: no OSM name -> own wording.
    unnamed = texts(lang).get("warningsUnnamed", {}).get(item.get("code", ""))
    if unnamed and not item.get("params", {}).get("name"):
        return _fill(unnamed, item.get("params", {}), lang)
    template = texts(lang)["warnings"].get(item.get("code", ""))
    return _fill(template, item.get("params", {}), lang) if template else item.get("text", "")


def reason(item: dict[str, Any], lang: str) -> str:
    # Mirrors reasonText in web/src/finder/i18n.ts: no distance -> "no X nearby".
    far = texts(lang).get("reasonsFar", {}).get(item.get("code", ""))
    if far and "distance_m" not in item.get("params", {}):
        return far
    template = texts(lang)["reasons"].get(item.get("code", ""))
    return _fill(template, item.get("params", {}), lang) if template else item.get("code", "")
