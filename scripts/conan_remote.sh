#!/usr/bin/env bash
#
# Configures the Conan client: a default profile plus, when credentials are
# present, the internal Artifactory remote.
#
# The remote is deliberately driven by environment variables rather than baked
# into a committed conan config. That keeps the same script working for a local
# developer (no remote at all -> conancenter only), for a fork's CI run (no
# secrets -> publish steps skip), and for the release pipeline (full access).
#
#   CONAN_REMOTE_NAME  default: internal
#   CONAN_REMOTE_URL   e.g. https://<tenant>.jfrog.io/artifactory/api/conan/conan-local
#   JFROG_USER         Artifactory user / e-mail
#   JFROG_TOKEN        Artifactory identity token
#
# Exit code is always 0: "no remote configured" is a normal state, not a failure.
set -euo pipefail

CONAN="${CONAN:-conan}"
REMOTE_NAME="${CONAN_REMOTE_NAME:-internal}"
REMOTE_URL="${CONAN_REMOTE_URL:-}"

log() { printf '[conan-remote] %s\n' "$*"; }

# Create a default profile if the machine has none (fresh container, fresh CI).
if ! "${CONAN}" profile path default >/dev/null 2>&1; then
    log "detecting default profile"
    "${CONAN}" profile detect --force >/dev/null
fi

# Ubuntu 24.04 ships GCC 13, whose default ABI is the modern one.
"${CONAN}" profile show -pr default >/dev/null

if [[ -z "${REMOTE_URL}" ]]; then
    log "CONAN_REMOTE_URL is not set — using conancenter only (publish steps will be skipped)"
    exit 0
fi

if "${CONAN}" remote list | grep -q "^${REMOTE_NAME}:"; then
    log "updating remote ${REMOTE_NAME}"
    "${CONAN}" remote update "${REMOTE_NAME}" --url "${REMOTE_URL}"
else
    log "adding remote ${REMOTE_NAME} -> ${REMOTE_URL}"
    "${CONAN}" remote add "${REMOTE_NAME}" "${REMOTE_URL}"
fi

if [[ -n "${JFROG_USER:-}" && -n "${JFROG_TOKEN:-}" ]]; then
    log "authenticating as ${JFROG_USER}"
    "${CONAN}" remote login "${REMOTE_NAME}" "${JFROG_USER}" --password "${JFROG_TOKEN}"
else
    log "remote configured read-only (JFROG_USER/JFROG_TOKEN not set)"
fi
