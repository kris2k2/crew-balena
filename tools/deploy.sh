#!/usr/bin/env bash
#
# Push one rendered fleet (tools/fleet.py render) to balenaCloud as a new
# fleet release.
#
#   BALENA_API_TOKEN=... tools/deploy.sh RENDER_DIR [--draft]
#   tools/deploy.sh RENDER_DIR --dry-run     # validate, print, push nothing
#
# RENDER_DIR is <out>/<fleet id>, holding source/ (what balena builds) and
# meta.json (where it goes). The images are not built here: every service is a
# block its own project already published, and the composition references it
# by version, so the builder only resolves `image:` references into a release.
#
# Adapted from crew-printcapture's deploy/balena/deploy.sh fleet push, which
# this replaces; the push flags are the same ones that have been releasing to
# this fleet since the block was introduced.
#
# CREDENTIALS
#
# BALENA_API_TOKEN logs the CLI in, and is the password in the
# --registry-secrets file the builder needs to pull the private blocks from
# bh.cr while it resolves the composition. Logging in replaces whatever CLI
# session is on this machine.
set -euo pipefail

log() { echo "fleet-deploy: $*"; }
die() { echo "fleet-deploy: error: $*" >&2; exit 1; }

[ $# -ge 1 ] || die "usage: tools/deploy.sh RENDER_DIR [--draft|--dry-run]"
RENDER_DIR=$1
shift

DRAFT=false
DRY_RUN=false
while [ $# -gt 0 ]; do
  case "$1" in
    --draft) DRAFT=true; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    *) die "unknown argument: $1" ;;
  esac
done

SOURCE="$RENDER_DIR/source"
META="$RENDER_DIR/meta.json"
[ -f "$SOURCE/docker-compose.yml" ] && [ -f "$SOURCE/balena.yml" ] && [ -f "$META" ] ||
  die "$RENDER_DIR is not a tools/fleet.py render (source/ and meta.json)"

# meta.json is read with python rather than parsed in shell: it is JSON this
# repository wrote, and jq is not guaranteed on every machine this runs on.
meta() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$META" "$1"; }
SLUG=$(meta slug)
VERSION=$(meta version)
DEPLOY=$(meta deploy)
# One "key value" pair per line, for --release-tag.
mapfile -t TAG_LINES < <(python3 -c '
import json, sys
for key, value in json.load(open(sys.argv[1]))["release_tags"]:
    print(key, value)
' "$META")

# The single-writer guard. A fleet with `deploy: false` may still be pushed to
# by something else (crew-printcapture, until the cutover), so nothing here
# pushes to it -- not a merge, and not a manual run either.
[ "$DEPLOY" = "True" ] || die "fleet $SLUG has deploy: false in its manifest; refusing to push"

COMMIT=""
if git rev-parse --verify HEAD >/dev/null 2>&1; then
  COMMIT=$(git rev-parse HEAD)
fi
NOTE="$(meta name) $VERSION${COMMIT:+ (crew-balena $COMMIT)}"

# --release-tag is variadic: keys and values alternate, and it goes LAST on
# the command line so no later flag is read as another tag.
RELEASE_TAG_ARGS=(--release-tag)
for line in "${TAG_LINES[@]}"; do
  RELEASE_TAG_ARGS+=("${line%% *}" "${line#* }")
done
if [ -n "$COMMIT" ]; then
  RELEASE_TAG_ARGS+=(crew-balena "$COMMIT")
fi

log "fleet $SLUG, release $VERSION"
for line in "${TAG_LINES[@]}"; do
  log "  ${line%% *} ${line#* }"
done

if [ "$DRY_RUN" = true ]; then
  log "dry run: nothing pushed"
  exit 0
fi

[ -n "${BALENA_API_TOKEN:-}" ] || die "BALENA_API_TOKEN is not set"
command -v balena >/dev/null 2>&1 || die "the balena CLI is not on PATH"

balena login --token "$BALENA_API_TOKEN" >/dev/null
balena whoami >/dev/null || die "the token was accepted but the session is not usable"

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
SECRETS="$WORK/registry-secrets.yml"
# A YAML single-quoted scalar escapes a quote by doubling it. 0600, and in the
# directory the trap removes, because this file holds the token.
secret_password=$(printf '%s' "$BALENA_API_TOKEN" | sed "s/'/''/g")
(umask 077; cat >"$SECRETS" <<YML
'bh.cr':
  username: 'crew-balena'
  password: '$secret_password'
YML
)

DRAFT_ARGS=()
if [ "$DRAFT" = true ]; then
  DRAFT_ARGS=(--draft)
fi

balena push "$SLUG" \
  --source "$SOURCE" \
  --registry-secrets "$SECRETS" \
  --note "$NOTE" \
  ${DRAFT_ARGS[@]+"${DRAFT_ARGS[@]}"} \
  "${RELEASE_TAG_ARGS[@]}"

if [ "$DRAFT" = true ]; then
  log "released $VERSION to $SLUG as a draft: finalize it in the dashboard before any device takes it"
else
  log "released $VERSION to $SLUG"
fi
