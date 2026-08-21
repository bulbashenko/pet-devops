#!/usr/bin/env bash
#
# Builds both C++ components with Conan 2 + CMake.
#
# sensorcore is built and placed in the local Conan cache with `conan create`
# (so it is a real, versioned package — the same artifact that later gets
# uploaded), and sensor-hub then consumes it exactly the way a downstream team
# would.
#
#   BUILD_TYPE  Release (default) | Debug
#   SKIP_TESTS  set to 1 to skip sensorcore's tests during `conan create`
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

BUILD_TYPE="${BUILD_TYPE:-Release}"
VERSION="$(./scripts/version.sh)"
export SENSORCORE_VERSION="${VERSION}"

CONAN="${CONAN:-conan}"

log() { printf '\n=== %s ===\n' "$*"; }

log "version ${VERSION} (${BUILD_TYPE})"

./scripts/conan_remote.sh

conan_args=(--build=missing -s "build_type=${BUILD_TYPE}")
if [[ "${SKIP_TESTS:-0}" == "1" ]]; then
    conan_args+=(-c "tools.build:skip_test=True")
fi

log "conan create sensorcore/${VERSION}"
"${CONAN}" create cpp/sensorcore --version "${VERSION}" "${conan_args[@]}"

log "building sensor-hub"
"${CONAN}" build cpp/sensor-hub --version "${VERSION}" "${conan_args[@]}"

binary="cpp/sensor-hub/build/${BUILD_TYPE}/sensor-hub"
if [[ ! -x "${binary}" ]]; then
    # cmake_layout drops single-config generators one level up.
    binary="cpp/sensor-hub/build/sensor-hub"
fi

if [[ ! -x "${binary}" ]]; then
    printf 'sensor-hub binary not found after build\n' >&2
    exit 1
fi

log "built ${binary}"
"${binary}" --version >/dev/null 2>&1 || true
