# Changelog

## 2.0.0 – 2026-10-24

A complete rebuild, focused on mobile use, search engines and small servers.

### New
- **Finder for phone and desktop:** bottom sheet on phones, sidebar on desktop,
  top-10 list with numbered pins, deep links, German and English.
- **Spot details:** the reasons behind every spot, warnings, a flight-weather
  light (wind, rain, Kp index), route, share link, story image (1080×1920),
  GPX export and a direct dipul link for the airspace check.
- **Local OpenStreetMap store for Germany:** searches no longer depend on the
  public Overpass servers. Rebuilt monthly by a GitHub workflow and downloaded
  by the container (`OSM_STORE_URL`).
- **Region pages** for 84 large German cities and **nine guides** (where to fly,
  A1/A2/A3, drone licence, geozones, nature reserves, fields, insurance,
  checklist) – static, fast, with structured data.
- **Result cache and share links:** identical searches answer in under a second.
- **Video mode** (`/app?present=1&…`) for 9:16 screen recordings.
- Optional self-hosted **Umami** statistics without cookies.

### Changed
- Frontend rebuilt with Astro, React and MapLibre; Lighthouse 100 on the static pages.
- Germany only. Defaults sized for a 2 GB / 1 CPU server
  (one search at a time, radius up to 10 km).
- The **Strava heatmap is off on public instances**; signposted hiking and
  cycling routes from OSM take its place. `STRAVA_ENABLED=true` turns it back on.
- Place search via Photon with Nominatim as fallback.
- Content-Security-Policy is set by the app, per page, without `unsafe-inline`.
- Natura 2000 sites (FFH and bird protection areas) now rule a spot out, as
  § 21h LuftVO requires; v1 only warned. Every spot names the kind of area it
  lies in (nature reserve, national park, bird protection, FFH), and under
  "Expert" they can be included in the results – always with a red note. Heritage and water protection zones no
  longer show up as landscape protection areas.

### Upgrading from 1.x
- `.env` and the Docker volumes (`fpvfinder-data`, `fpvfinder-config`) keep working.
- Set `OSM_STORE_URL` and `REGIONS_URL` (see `.env.example`), then
  `docker compose pull && docker compose up -d`.
- The old `frontend/` and the PowerShell start scripts are gone; see [docs/self-hosting.md](docs/self-hosting.md)
  for the development setup.
