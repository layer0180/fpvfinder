# syntax=docker/dockerfile:1
#
# One container serving the API and the built website on port 8000.
#
# The directory layout inside the image mirrors the repository, because the
# backend resolves paths relative to its own files:
#   backend/app/config.py -> BACKEND_DIR = /app/backend
#   backend/app/web.py    -> /app/web/dist
#   backend/app/texts.py  -> /app/shared/i18n
# Do not flatten this.
#
# Targets:
#   runtime (default, last stage)  the server
#   importer           runtime + osmium, for building an OSM tile store:
#     docker build --target importer -t fpvfinder-importer .
#     docker run --rm -v "$PWD/osm:/osm" fpvfinder-importer \
#       python -m app.osm.importer /osm/germany-latest.osm.pbf --poly /osm/germany.poly \
#       --out /osm/osm-store.sqlite --index sparse_file_array,/osm/nodes.idx
#   Germany needs ~10 GB of RAM or disk for the node index and about an hour -
#   run it on a workstation or let the monthly workflow do it, never on a
#   small server.

# ---------------------------------------------------------------------------
# Stage 1: the website
# ---------------------------------------------------------------------------
FROM node:24-alpine AS web

# Absolute base URL baked into canonical links, hreflang, Open Graph and the
# sitemap. Normally leave it empty: PUBLIC_URL rewrites these at runtime
# (backend/app/web.py), so one published image serves any domain.
ARG SITE_URL=""
ENV SITE_URL=$SITE_URL ASTRO_TELEMETRY_DISABLED=1

WORKDIR /build/web
# Manifests first so the dependency layer stays cached when only sources change.
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY shared/ /build/shared/
COPY web/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: the application (shared by both targets below)
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS app

LABEL org.opencontainers.image.source="https://github.com/Layer0180/fpvfinder"
LABEL org.opencontainers.image.description="Finds quiet FPV flying spots in Germany from OpenStreetMap"
LABEL org.opencontainers.image.licenses="AGPL-3.0-only"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app/backend

# A real font for the preview and story images (backend/app/cards.py).
RUN apt-get update     && apt-get install -y --no-install-recommends fonts-dejavu-core     && rm -rf /var/lib/apt/lists/*

# shapely, numpy, Pillow and zstandard all ship manylinux wheels for amd64 and
# arm64, so no compiler is needed.
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/tests ./tests
# Imprint / privacy / support texts. Mount your own directory over it to fill
# in your details without rebuilding (see docker-compose.yml).
COPY backend/content ./content
COPY shared /app/shared
COPY --from=web /build/web/dist /app/web/dist

# Seed files live outside the mount points; the entrypoint copies them in only
# when missing. Docker seeds named volumes by itself, but not bind mounts.
COPY backend/data/airspace.geojson /app/seed/data/airspace.geojson
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

RUN useradd --system --create-home --uid 10001 appuser \
    && mkdir -p /app/backend/config /app/backend/data \
    && chown -R appuser:appuser /app
USER appuser

VOLUME ["/app/backend/data", "/app/backend/config"]
EXPOSE 8000

# python instead of curl: the slim image has no curl.
# start-period covers the first download of the OSM store (~1.5 GB).
HEALTHCHECK --interval=30s --timeout=5s --start-period=600s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
# One worker: searches are CPU-bound and limited to one at a time on a small
# server anyway, and a second process would double the memory floor.
# No --proxy-headers: X-Forwarded-For is honoured by the app itself, and only
# with TRUST_PROXY=true (app/limits.py) - trusting it blindly here would let
# anyone pick their own rate-limit identity.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------------------------------------------------------------------------
# Optional: the OSM importer (built only with --target importer)
# ---------------------------------------------------------------------------
FROM app AS importer
USER root
COPY backend/requirements-import.txt ./
RUN pip install --no-cache-dir -r requirements-import.txt
USER appuser
CMD ["python", "-m", "app.osm.importer", "--help"]

# ---------------------------------------------------------------------------
# Default target - must stay the last stage, `docker build .` builds this one.
# ---------------------------------------------------------------------------
FROM app AS runtime
