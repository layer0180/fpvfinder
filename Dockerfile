# syntax=docker/dockerfile:1
#
# Single container serving both the API and the built frontend on port 8000.
#
# IMPORTANT - the directory layout inside the image must mirror the repository,
# because the backend resolves paths relative to its own file:
#   backend/app/main.py   -> FRONTEND_DIST = <parent.parent.parent>/frontend/dist
#   backend/app/config.py -> BACKEND_DIR   = <parent.parent>
# Hence /app/backend/... and /app/frontend/dist. Do not flatten this.

# ---------------------------------------------------------------------------
# Stage 1: build the frontend
# ---------------------------------------------------------------------------
FROM node:22-alpine AS frontend

# The static marketing pages need an absolute base URL: canonical, hreflang,
# Open Graph images and sitemap.xml are all meaningless (or actively wrong) as
# relative paths.
#
# You normally do NOT need this. A published image is built once and deployed
# under a domain the build could not know, so the runtime PUBLIC_URL setting
# rewrites these URLs on the way out instead - see backend/app/main.py. Baking
# one in only helps if you build the image yourself for a fixed domain:
#
#     docker build --build-arg SITE_URL=https://fpvfinder.example.com -t fpvfinder .
#
# Either way PUBLIC_URL wins at runtime, and the startup log states which
# address is actually being advertised to search engines.
ARG SITE_URL=""
ENV SITE_URL=$SITE_URL

WORKDIR /build

# Copy the manifests first so the dependency layer stays cached when only
# source files change.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# ---------------------------------------------------------------------------
# Stage 2: runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# These labels are what links the package to the repository on GHCR - without
# org.opencontainers.image.source the package is not associated with the repo
# and does not inherit its visibility settings.
LABEL org.opencontainers.image.source="https://github.com/Layer0180/fpvfinder"
LABEL org.opencontainers.image.description="Finds FPV flying spots with few people around, from OpenStreetMap and the Strava heatmap"
LABEL org.opencontainers.image.licenses="AGPL-3.0-only"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app/backend

# Dependencies first, again for layer caching. shapely, numpy and Pillow all
# ship manylinux wheels for amd64 and arm64, so no compiler is needed.
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY backend/app ./app
COPY backend/tests ./tests

# Imprint / privacy / funding templates. Not a volume: mount your own directory
# over it (see docker-compose.yml) to fill in your details without rebuilding.
COPY backend/content ./content

# Built frontend from stage 1, at the location main.py expects
COPY --from=frontend /build/dist /app/frontend/dist

# Seed files. These are kept outside the mount points on purpose: when a volume
# is mounted over config/ or data/, the entrypoint copies them in only if the
# target does not exist yet. Docker seeds *named* volumes by itself, but not
# bind mounts - this covers both.
COPY backend/data/airspace.geojson /app/seed/data/airspace.geojson
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Run as a non-root user. Port 8000 is unprivileged, so nothing else is needed.
RUN useradd --system --create-home --uid 10001 appuser \
    && mkdir -p /app/backend/config /app/backend/data \
    && chown -R appuser:appuser /app
USER appuser

VOLUME ["/app/backend/data", "/app/backend/config"]

EXPOSE 8000

# python instead of curl: the slim image has no curl, and adding it just for a
# health check would be wasteful.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
