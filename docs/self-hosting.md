# Self-hosting and development

## Run it

```bash
cp .env.example .env            # domain, map data URLs, limits
docker compose up -d            # http://localhost:8000
```

On a server with TLS (Caddy, Let's Encrypt), set `DOMAIN` and `ACME_EMAIL` in
`.env`, then:

```bash
docker compose -f docker-compose.yml -f docker-compose.caddy.yml up -d
```

The defaults fit a **2 GB / 1 CPU** machine: one search at a time, radius up to
10 km (`SEARCH_MAX_CONCURRENT`, `MAX_RADIUS_KM`).

**Updates:** `docker compose pull && docker compose up -d`. The image is
published to `ghcr.io/layer0180/fpvfinder` for every release tag (`2.0.0`,
`2.0`, `2`, `latest`).

**Before going public:** set `OPERATOR_NAME`, `OPERATOR_ADDRESS` and
`CONTACT_EMAIL` in `.env` – the imprint (§ 5 DDG) reads them from there, so they
never end up in git. For texts of your own, mount `backend/content` (see the
commented volume in `docker-compose.yml`).

## Map data

Searches read OpenStreetMap data from a local **tile store** (one SQLite file,
~1.5 GB for Germany), so they neither wait for nor depend on the public Overpass
servers. With `OSM_STORE_URL` set, the container downloads it on first start and
refreshes it on a restart once it is older than `OSM_STORE_MAX_AGE_DAYS`.

The store is rebuilt monthly by [`.github/workflows/osm-data.yml`](../.github/workflows/osm-data.yml)
from the Geofabrik extract and published as the release `osm-data`; `.env.example`
already points there. To build one yourself (needs ~10 GB of RAM or disk for the
node index, about an hour):

```bash
cd backend
pip install -r requirements-import.txt
python -m app.osm.importer germany-latest.osm.pbf --poly germany.poly \
    --out data/osm-store.sqlite --index sparse_mem_array
```

Without a store every search falls back to Overpass (`OSM_LIVE_FALLBACK`).

## Region pages

`/regionen/<city>` shows the best spots around 84 large German cities
([`shared/regions/cities.json`](../shared/regions/cities.json)). They are computed
offline after each import (`python -m app.regions`, part of the monthly workflow)
and published as `regions.json` next to the store; `REGIONS_URL` makes the
container fetch it like the store. A city only gets a page with at least three
spots scoring 70 or more.

## Options

| Variable | |
|---|---|
| `PUBLIC_MODE` | Disables endpoints that change server-wide state. On for a public instance. |
| `STRAVA_ENABLED` | The Strava heatmap. Off by default on a public instance; signposted hiking and cycling routes from OSM take its place. |
| `ANALYTICS_*` | Self-hosted [Umami](https://umami.is) without cookies: `docker compose --profile analytics up -d`. |
| `MAP_STYLE_URL`, `PHOTON_URL`, `GEOCODE_COUNTRY` | Map style and place search. |
| `OPERATOR_NAME`, `OPERATOR_ADDRESS`, `CONTACT_EMAIL` | Imprint details. The address takes comma-separated lines. |
| `DONATE_URL`, `DONATE_LABEL` | Where the "support this project" links point to. |

All variables with comments: [`.env.example`](../.env.example).

## What is in it

| | |
|---|---|
| `backend/` | FastAPI. Scoring (`app/scoring/`), OSM store and importer (`app/osm/`), search jobs with a result cache, share links, preview images (`app/cards.py`), and serving of the website (`app/web.py`) |
| `web/` | Astro: static pages and guides (`src/content/guides`) in German and English, and the finder as a React island with MapLibre |
| `shared/` | Wording for everything the backend returns as a code (`i18n/`), and the city list for region pages |

**Video mode** for screen recordings: `/app?present=1&lat=…&lon=…&r=5&n=3` – or the
🎬 button above a result list.

## Develop

```bash
# backend
cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements-import.txt pytest
.venv/Scripts/python -m pytest tests
.venv/Scripts/python -m uvicorn app.main:app --port 8000     # serves web/dist when built

# website
cd web && npm ci
npm run build          # into web/dist, served by the backend
npm run dev            # Astro dev server; API calls need the backend on :8000
npx playwright test    # e2e on Android, iPhone (WebKit), Chrome and Firefox
                       # against a running backend (BASE_URL; PW_CHANNEL=msedge)
```

Optional pre-commit hook that blocks committed credentials:
`git config core.hooksPath tools`.

## Coming from v1

- `.env` files and the Docker volumes keep working. New: `OSM_STORE_URL`,
  `REGIONS_URL`, `OSM_LIVE_FALLBACK`, `MAP_STYLE_URL`, `PHOTON_URL`,
  `GEOCODE_COUNTRY`, `STRAVA_ENABLED`, `ANALYTICS_*`.
- The Content-Security-Policy moved from the Caddyfile into the app.

## Licences

Code: [AGPL-3.0](../LICENSE). Because this is served over a network, § 13 also
requires anyone running a *modified* version to offer its source to its users.

Map data © OpenStreetMap contributors, [ODbL](https://www.openstreetmap.org/copyright).
The OSM tile store is a derivative database and is distributed under the ODbL as
well. Map tiles: OpenFreeMap / OpenMapTiles. Weather: Open-Meteo (CC BY 4.0).
