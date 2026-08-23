#!/usr/bin/env bash
#
# Builds the sensorctl wheel and sdist into dist/.
#
# The version is written into src/sensorctl/_version.py from scripts/version.sh
# before building. hatch-vcs would read the git tag directly, but it derives its
# own version from it — off a tag it guesses the *next* release, so the wheel
# would come out 0.1.1.dev0 while the .deb built from the same commit said
# 0.1.0.dev0. One source of truth means one string, not two conventions that
# happen to agree on release commits.
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

log() { printf '\n=== %s ===\n' "$*"; }

VERSION="$(./scripts/version.sh --write-python)"
log "version ${VERSION}"

log "building wheel and sdist"
uv build --project python/sensorctl --out-dir dist

log "built"
ls -1 dist/sensorctl-*"${VERSION}"* 2>/dev/null || {
    printf 'no artifact carrying version %s landed in dist/\n' "${VERSION}" >&2
    exit 1
}
