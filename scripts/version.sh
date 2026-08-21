#!/usr/bin/env bash
#
# Single source of truth for the project version.
#
# Every artifact format the pipeline produces (Conan package, DEB, Python wheel,
# Docker tag) derives its version from the git tag through this script, so a
# release is one `git tag vX.Y.Z` away and the four artifacts can never drift.
#
# Usage:
#   scripts/version.sh            # 1.2.3            or 1.2.3.dev4+g1a2b3c4
#   scripts/version.sh --docker   # 1.2.3            or 1.2.3.dev4_g1a2b3c4  ('+' is illegal in tags)
#   scripts/version.sh --tag      # v1.2.3
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
FALLBACK_VERSION="0.1.0"

mode="${1:-plain}"

compute_version() {
    # An explicit override wins: CI can build a detached tree with no tags.
    if [[ -n "${SENSORCORE_VERSION:-}" ]]; then
        printf '%s' "${SENSORCORE_VERSION}"
        return
    fi

    if ! git -C "${REPO_ROOT}" rev-parse --git-dir >/dev/null 2>&1; then
        printf '%s.dev0' "${FALLBACK_VERSION}"
        return
    fi

    local describe
    if describe="$(git -C "${REPO_ROOT}" describe --tags --match 'v[0-9]*' --long --dirty 2>/dev/null)"; then
        # v1.2.3-4-g1a2b3c4[-dirty]
        local dirty=""
        if [[ "${describe}" == *-dirty ]]; then
            dirty=".dirty"
            describe="${describe%-dirty}"
        fi

        local sha="${describe##*-}"          # g1a2b3c4
        local rest="${describe%-*}"          # v1.2.3-4
        local distance="${rest##*-}"         # 4
        local tag="${rest%-*}"               # v1.2.3
        local base="${tag#v}"                # 1.2.3

        if [[ "${distance}" == "0" && -z "${dirty}" ]]; then
            printf '%s' "${base}"
        else
            printf '%s.dev%s+%s%s' "${base}" "${distance}" "${sha}" "${dirty}"
        fi
        return
    fi

    # No tags yet — still produce something monotonic and traceable.
    local sha
    sha="$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
    local count
    count="$(git -C "${REPO_ROOT}" rev-list --count HEAD 2>/dev/null || echo 0)"
    printf '%s.dev%s+g%s' "${FALLBACK_VERSION}" "${count}" "${sha}"
}

version="$(compute_version)"

case "${mode}" in
    plain)
        printf '%s\n' "${version}"
        ;;
    --docker)
        # Docker tags allow [A-Za-z0-9_.-] only.
        printf '%s\n' "${version//+/_}"
        ;;
    --tag)
        printf 'v%s\n' "${version}"
        ;;
    *)
        printf 'usage: %s [--docker|--tag]\n' "$0" >&2
        exit 2
        ;;
esac
