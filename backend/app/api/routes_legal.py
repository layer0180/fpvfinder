"""
Imprint, privacy notice and the donation transparency text.

These are plain Markdown files under ``backend/content/`` rather than compiled
into the frontend, so that the operator can change their wording by editing a
file (or mounting one into the container) without rebuilding anything.

English only. These three texts are legal statements about one specific
deployment, and a translation is a second wording of the same obligation that
has to be kept in step with the first - the app itself is English throughout,
so the second wording earned nothing and could only drift.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import SETTINGS

router = APIRouter(prefix="/api/legal", tags=["legal"])

# Whitelist: the page name ends up in a filename, so it may not be free-form.
PAGES = ("imprint", "privacy", "funding")


def _path_for(page: str):
    """``content/<page>.md`` - the component is whitelisted above."""
    return SETTINGS.content_dir / f"{page}.md"


def _resolve(page: str):
    """The file, or None when it is missing or empty."""
    path = _path_for(page)
    if path.exists() and path.read_text(encoding="utf-8").strip():
        return path
    return None


@router.get("", summary="Which legal pages are available")
async def list_pages() -> dict[str, object]:
    return {
        "pages": {page: _resolve(page) is not None for page in PAGES},
        "donate_url": SETTINGS.donate_url,
        "donate_label": SETTINGS.donate_label,
        "contact_email": SETTINGS.contact_email,
        "project_url": SETTINGS.project_url,
    }


@router.get("/{page}", summary="Markdown source of a legal page")
async def read_page(page: str) -> dict[str, str]:
    if page not in PAGES:
        raise HTTPException(status_code=404, detail=f"Unknown page. Available: {', '.join(PAGES)}")

    path = _resolve(page)
    if path is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No content for '{page}'. Create backend/content/{page}.md "
                "to enable this page."
            ),
        )

    text = path.read_text(encoding="utf-8")

    # Small conveniences so the templates do not have to be edited in two places.
    # The repository is the contact route, so the templates never need personal
    # details. CONTACT_EMAIL stays supported but falls back to the project URL
    # rather than printing "(not configured)" at a visitor.
    text = text.replace("{{PROJECT_URL}}", SETTINGS.project_url)
    text = text.replace("{{CONTACT_EMAIL}}", SETTINGS.contact_email or SETTINGS.project_url)
    text = text.replace("{{PUBLIC_URL}}", SETTINGS.public_url or SETTINGS.project_url)
    text = text.replace("{{DONATE_URL}}", SETTINGS.donate_url or SETTINGS.project_url)

    return {"page": page, "markdown": text}
