# Changelog

## 2.0.1 – 2026-10-28

### New
- **Spot flight video:** a "Video" button on every spot opens a camera flight
  for short vertical videos - Germany with the spot pulsing, down to the town,
  a tilted approach and one orbit while the score counts up, then the site's
  address. The flight is preloaded behind a cover, so a screen recording shows
  no half-loaded map. `clean=1` leaves out all text, `title=` sets an own
  headline.

- **Region pages for every town of 30,000 or more** - some 380 instead of 84,
  from OSM (`python -m app.cities`; published slugs never change). Where the
  circles of neighbouring towns overlap, each page lists different spots, and
  "Nearby regions" now links the closest pages across state borders. The
  workflow computes them in a job of its own, searches in parallel, and can
  recompute just the pages ("regions only").
- **Golden hour and wind direction** for every spot: the next golden hour with
  the direction the light comes from, worked out in the browser, and where the
  wind blows from - in the weather section and as an arrow on the map.
- **OSM data updates itself:** the running server asks the release every
  `OSM_REFRESH_HOURS` (6) whether a newer store or regions file exists, by its
  date, downloads it next to the old one and swaps it in without a restart.
  Searches keep running; a full disk or an unusable file keeps the old data
  and is not fetched again until the next release.

### Changed
- **Scoring follows each release:** a public instance no longer reads
  `config/weights.json` (`USE_WEIGHTS_FILE=true` turns it back on), and a
  private one saves only the weights changed in the UI. Before, the first start
  wrote every default into that file and froze them for all later releases.
- **Quieter log:** expected search failures (outside the covered region, OSM
  unreachable) are one line instead of a traceback.
- `OSM_STORE_MAX_AGE_DAYS` defaults to 35 when unset (was: never refresh).
- **Video modes keep clear of TikTok's overlays:** cards and the outro moved
  out of the caption at the bottom and the button column on the right; the
  close button and the replay hint stay hidden while a take runs.
- **Video modes use the finder's own search** (time profile, grid, balance,
  protected areas), so they answer from the result cache and show the same
  scores as the list.

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
