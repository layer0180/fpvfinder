#!/bin/sh
#
# Seeds the config and data directories, then hands over to the CMD.
#
# Why this is needed: config/ and data/ are mount points. Docker copies the
# image content into a *named* volume on first use, but does nothing for bind
# mounts - so with `-v ./mydata:/app/backend/data` the shipped example
# airspace.geojson would silently be missing. Copying here covers both cases,
# and never overwrites a file the user already has.
#
# weights.json is deliberately NOT seeded: the backend generates it from its
# defaults when missing, which keeps a single source of truth (defaults.py).

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

exec "$@"
