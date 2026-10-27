#!/bin/sh
set -eu

lockfile_hash=$(sha256sum package-lock.json | cut -d ' ' -f 1)
hash_marker=node_modules/.booker-lockfile-hash

if [ ! -f "$hash_marker" ] || [ "$(cat "$hash_marker")" != "$lockfile_hash" ]; then
    npm ci --no-audit --no-fund
    printf '%s\n' "$lockfile_hash" > "$hash_marker"
fi

exec npm run dev -- --host 0.0.0.0