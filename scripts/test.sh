#!/usr/bin/env bash
#
# Runs every test suite and writes JUnit XML into reports/ so that both Jenkins
# (junit step) and GitHub Actions (test summary) can render the same results.
#
#   SUITE=all|cpp|python   which suites to run (default: all)
#   INTEGRATION=1          also run the container-backed integration tests
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

SUITE="${SUITE:-all}"
BUILD_TYPE="${BUILD_TYPE:-Release}"
REPORTS="${REPO_ROOT}/reports"
mkdir -p "${REPORTS}"

log() { printf '\n=== %s ===\n' "$*"; }

# `find` on a missing directory exits non-zero, which `set -o pipefail` would
# turn into a script abort — so absence is reported as an empty string instead.
find_test_binary() {
    find cpp/sensorcore/build -name sensorcore_tests -type f -perm -u+x 2>/dev/null | head -1 || true
}

run_cpp_tests() {
    log "C++ unit tests (GTest)"

    local test_binary
    test_binary="$(find_test_binary)"

    if [[ -z "${test_binary}" ]]; then
        # `conan create` builds and runs the tests in the Conan cache; for a
        # standalone JUnit report we need a local build tree.
        log "no local test binary — building sensorcore standalone"
        ./scripts/conan_remote.sh
        conan build cpp/sensorcore --version "$(./scripts/version.sh)" \
            --build=missing -s "build_type=${BUILD_TYPE}"
        test_binary="$(find_test_binary)"
    fi

    if [[ -z "${test_binary}" ]]; then
        printf 'sensorcore_tests binary not found after build\n' >&2
        return 1
    fi

    "${test_binary}" "--gtest_output=xml:${REPORTS}/gtest-sensorcore.xml"
}

run_python_tests() {
    log "Python tests (pytest)"

    # hatchling reads the package version from a generated file; installing the
    # package for the test run needs it to be there.
    ./scripts/version.sh --write-python >/dev/null

    local marker=(-m "not integration")
    if [[ "${INTEGRATION:-0}" == "1" ]]; then
        marker=()
        log "including integration tests (image: ${SENSOR_HUB_IMAGE:-sensor-hub:local})"
    fi

    uv run --project python/sensorctl --extra test -- \
        pytest python/sensorctl/tests \
        "${marker[@]}" \
        --junitxml="${REPORTS}/pytest-sensorctl.xml" \
        --cov=sensorctl --cov-report=term-missing
}

case "${SUITE}" in
    all)    run_cpp_tests; run_python_tests ;;
    cpp)    run_cpp_tests ;;
    python) run_python_tests ;;
    *)      printf 'unknown SUITE=%s\n' "${SUITE}" >&2; exit 2 ;;
esac

log "reports written to ${REPORTS}"
ls -1 "${REPORTS}"
