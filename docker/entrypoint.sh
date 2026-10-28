#!/bin/sh
#
# Seeds the config and data directories, fetches the OSM tile store if one is
# configured, then hands over to the CMD.
#
# Why seeding is needed: config/ and data/ are mount points. Docker copies the
# image content into a *named* volume on first use, but does nothing for bind
# mounts - so with `-v ./mydata:/app/backend/data` the shipped example
# airspace.geojson would silently be missing. Copying here covers both cases,
# and never overwrites a file the user already has.
#
# weights.json is deliberately NOT seeded: it holds only the weights changed
# in the UI, everything else comes from app/scoring/defaults.py.

set -e

seed_file() {
    src="$1"
    dest="$2"
    if [ -f "$src" ] && [ ! -e "$dest" ]; then
        mkdir -p "$(dirname "$dest")"
        cp "$src" "$dest"
        echo "[entrypoint] seeded $dest"
    fi
}

seed_file /app/seed/data/airspace.geojson /app/backend/data/airspace.geojson

mkdir -p /app/backend/data /app/backend/config

# OSM_STORE_URL / REGIONS_URL set -> download the prebuilt OSM store and the
# region pages when missing or too old.
# Never fatal: see app/osm/fetch.py.
if [ -n "$OSM_STORE_URL" ] || [ -n "$REGIONS_URL" ]; then
    python -m app.osm.fetch
fi

exec "$@"
