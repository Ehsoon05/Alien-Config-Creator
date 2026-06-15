#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/opt/alien-config-creator
cd "$APP_DIR"
exec 9>/tmp/alien-config-creator-update.lock
flock -n 9 || exit 0

git fetch origin main
local_rev="$(git rev-parse HEAD)"
remote_rev="$(git rev-parse FETCH_HEAD)"
[ "$local_rev" = "$remote_rev" ] && exit 0
[ "$(git merge-base HEAD FETCH_HEAD)" = "$local_rev" ] || exit 1

git merge --ff-only FETCH_HEAD
"$APP_DIR/.venv/bin/pip" install -r requirements.txt
"$APP_DIR/.venv/bin/pip" install --no-deps "$APP_DIR"
systemctl restart alien-config-creator.service
