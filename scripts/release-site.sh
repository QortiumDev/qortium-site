#!/usr/bin/env bash
# Build once, then roll the same dist/ out to selected Qortium website targets.
# No target runs unless explicitly selected.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'USAGE'
Usage:
  scripts/release-site.sh --previewnet [--no-build] [--dry-run]
  scripts/release-site.sh --mainnet [--wallet PATH] [--password-file PATH] [--yes]
  scripts/release-site.sh --vps [--no-build]
  scripts/release-site.sh --all [--yes]

Targets:
  --previewnet       Publish dist/ to previewnet QDN using scripts/publish-qdn.mjs.
  --mainnet          Publish dist/ to Qortal MAINNET QDN. Requires confirmation.
  --vps              Deploy dist/ to qortium.app using scripts/deploy-site.sh --no-build.
  --all              Select previewnet, mainnet, and VPS.

Options:
  --no-build         Reuse the current dist/ instead of building first.
  --dry-run          Print commands only; run nothing.
  --yes              Skip the mainnet confirmation prompt.
  --wallet PATH      Mainnet Qortal wallet backup path. Defaults to QORTAL_WALLET.
  --password-file PATH
                     Mainnet wallet password file. Defaults to QORTAL_PASSWORD_FILE.
  -h, --help         Show this help.

With no target flags, this help is printed and nothing is published or deployed.
USAGE
}

quote_cmd() {
  local arg
  printf '%q' "$1"
  shift || true
  for arg in "$@"; do
    printf ' %q' "$arg"
  done
  printf '\n'
}

run_cmd() {
  echo "==> $(quote_cmd "$@")"
  "$@"
}

require_dist() {
  [ -f "$REPO_ROOT/dist/index.html" ] || {
    echo "ERROR: dist/index.html missing -- build first or omit --no-build." >&2
    exit 1
  }
}

previewnet=0
mainnet=0
vps=0
build=1
dry_run=0
yes=0
mainnet_wallet="${QORTAL_WALLET:-}"
mainnet_password_file="${QORTAL_PASSWORD_FILE:-}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --previewnet) previewnet=1 ;;
    --mainnet) mainnet=1 ;;
    --vps) vps=1 ;;
    --all) previewnet=1; mainnet=1; vps=1 ;;
    --no-build) build=0 ;;
    --dry-run) dry_run=1 ;;
    --yes) yes=1 ;;
    --wallet)
      shift
      [ "$#" -gt 0 ] || { echo "ERROR: --wallet requires a path." >&2; exit 2; }
      mainnet_wallet="$1"
      ;;
    --wallet=*) mainnet_wallet="${1#*=}" ;;
    --password-file)
      shift
      [ "$#" -gt 0 ] || { echo "ERROR: --password-file requires a path." >&2; exit 2; }
      mainnet_password_file="$1"
      ;;
    --password-file=*) mainnet_password_file="${1#*=}" ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown arg: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

if [ "$previewnet" -eq 0 ] && [ "$mainnet" -eq 0 ] && [ "$vps" -eq 0 ]; then
  usage
  exit 0
fi

cd "$REPO_ROOT"

preview_status="not selected"
mainnet_status="not selected"
vps_status="not selected"
[ "$previewnet" -eq 1 ] && preview_status="pending"
[ "$mainnet" -eq 1 ] && mainnet_status="pending"
[ "$vps" -eq 1 ] && vps_status="pending"

if [ "$dry_run" -eq 1 ]; then
  echo "==> dry run: no commands will be run"
  if [ "$build" -eq 1 ]; then
    quote_cmd npm run build
  fi
  if [ "$previewnet" -eq 1 ]; then
    quote_cmd node scripts/publish-qdn.mjs
    preview_status="dry-run"
  fi
  if [ "$mainnet" -eq 1 ]; then
    wallet_arg="${mainnet_wallet:-\$QORTAL_WALLET}"
    password_arg="${mainnet_password_file:-\$QORTAL_PASSWORD_FILE}"
    quote_cmd python3 tools/publish_qdn.py \
      --node https://ext-node.qortal.link \
      --service WEBSITE \
      --name Qortium \
      --identifier default \
      --path dist \
      --title "Qortium Website" \
      --description "https://qortium.app" \
      --category CRYPTOCURRENCY \
      --fee 0.01 \
      --wallet "$wallet_arg" \
      --password-file "$password_arg"
    mainnet_status="dry-run"
  fi
  if [ "$vps" -eq 1 ]; then
    quote_cmd bash scripts/deploy-site.sh --no-build
    vps_status="dry-run"
  fi
else
  if [ "$build" -eq 1 ]; then
    run_cmd npm run build
  fi
  require_dist

  if [ "$previewnet" -eq 1 ]; then
    run_cmd node scripts/publish-qdn.mjs
    preview_status="published"
  fi

  if [ "$mainnet" -eq 1 ]; then
    if [ "$yes" -ne 1 ]; then
      echo "MAINNET QDN publish spends 0.01 QORT and broadcasts a real transaction."
      printf 'Type "yes" to continue: '
      if ! IFS= read -r confirm || [ "$confirm" != "yes" ]; then
        echo "==> mainnet skipped"
        mainnet_status="skipped"
      fi
    fi

    if [ "$mainnet_status" = "pending" ]; then
      [ -n "$mainnet_wallet" ] || {
        echo "ERROR: mainnet requires QORTAL_WALLET or --wallet." >&2
        exit 1
      }
      [ -n "$mainnet_password_file" ] || {
        echo "ERROR: mainnet requires QORTAL_PASSWORD_FILE or --password-file." >&2
        exit 1
      }
      run_cmd python3 tools/publish_qdn.py \
        --node https://ext-node.qortal.link \
        --service WEBSITE \
        --name Qortium \
        --identifier default \
        --path dist \
        --title "Qortium Website" \
        --description "https://qortium.app" \
        --category CRYPTOCURRENCY \
        --fee 0.01 \
        --wallet "$mainnet_wallet" \
        --password-file "$mainnet_password_file"
      mainnet_status="published"
    fi
  fi

  if [ "$vps" -eq 1 ]; then
    run_cmd bash scripts/deploy-site.sh --no-build
    vps_status="deployed"
  fi
fi

echo "==> release summary"
echo "    previewnet: $preview_status"
echo "    mainnet:    $mainnet_status"
echo "    vps:        $vps_status"
