#!/usr/bin/env bash
# Deploy the built static site (dist/) to the Qortium web seeds that serve
# https://qortium.app via Caddy. The site is served as plain static files,
# independent of the Qortium node (which stays on its API port).
#
# Each seed serves /var/www/qortium, owned by the unprivileged `qortium` user,
# so deploys need no root -- just the qortium SSH key.
#
# IMPORTANT: Caddy runs as a separate `caddy` user, so the files MUST be
# world-readable. The local umask is 007 (a plain copy lands 770/660 and Caddy
# returns 403), so we force 755/644 on transfer with --chmod. Do NOT remove it.
#
# Usage:
#   scripts/deploy-site.sh               # build, then deploy to all seeds
#   scripts/deploy-site.sh --no-build    # deploy the current dist/ as-is
#   scripts/deploy-site.sh regxa         # one seed only (regxa | netcup)
#   scripts/deploy-site.sh netcup --no-build
#
# Requires: rsync, the `npm run build` toolchain, and SSH aliases
# qortium-regxa / qortium-netcup (see ~/.ssh/config).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEBROOT="/var/www/qortium"
ALL_SEEDS="regxa netcup"

# Resolve a seed name to its SSH alias (kept bash-3.2 safe -- no associative arrays).
seed_host() {
  case "$1" in
    regxa)  echo "qortium-regxa" ;;
    netcup) echo "qortium-netcup" ;;
    *)      return 1 ;;
  esac
}

build=1
targets=""
for arg in "$@"; do
  case "$arg" in
    --no-build)   build=0 ;;
    regxa|netcup) targets="$targets $arg" ;;
    -h|--help)    sed -n '2,24p' "$0"; exit 0 ;;
    *)            echo "unknown arg: $arg (use regxa | netcup | --no-build)" >&2; exit 2 ;;
  esac
done
[ -z "$targets" ] && targets="$ALL_SEEDS"

cd "$REPO_ROOT"
if [ "$build" -eq 1 ]; then
  echo "==> building (npm run build)"
  npm run build
fi
[ -f dist/index.html ] || { echo "ERROR: dist/index.html missing -- build first" >&2; exit 1; }

for t in $targets; do
  host="$(seed_host "$t")"
  echo "==> deploying to $t ($host):$WEBROOT"
  rsync -avz --delete --chmod=D755,F644 -e ssh dist/ "$host:$WEBROOT/"
  n="$(ssh "$host" "ls -1 $WEBROOT 2>/dev/null | wc -l" 2>/dev/null || echo '?')"
  echo "    ok: $n entries now in $WEBROOT on $t"
done
echo "==> done: deployed to:$targets"
