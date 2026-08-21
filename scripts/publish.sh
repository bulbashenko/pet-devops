#!/usr/bin/env bash
#
# Publishes the release artifacts to Artifactory:
#   * the sensorcore Conan package -> Conan repository
#   * the .deb and its checksum    -> generic repository
#
# Without credentials this is a no-op that exits 0. That is deliberate: a fork,
# an outside contributor's pull request, or an expired trial must still produce
# a green build — only the publish step disappears. See the README section
# "What runs without secrets".
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

VERSION="$(./scripts/version.sh)"
ARCH="$(dpkg --print-architecture 2>/dev/null || echo amd64)"
REMOTE_NAME="${CONAN_REMOTE_NAME:-internal}"
GENERIC_REPO="${JFROG_GENERIC_REPO:-pet-devops-generic}"

log() { printf '\n=== %s ===\n' "$*"; }

if [[ -z "${CONAN_REMOTE_URL:-}" || -z "${JFROG_TOKEN:-}" ]]; then
    log "no Artifactory credentials — skipping publish (this is not a failure)"
    exit 0
fi

./scripts/conan_remote.sh

log "uploading sensorcore/${VERSION} to ${REMOTE_NAME}"
conan upload "sensorcore/${VERSION}" --remote "${REMOTE_NAME}" --confirm

deb="dist/sensor-hub_${VERSION}_${ARCH}.deb"
if [[ ! -f "${deb}" ]]; then
    log "no .deb at ${deb} — run 'make deb' first"
    exit 1
fi

# JFROG_URL is the tenant base, e.g. https://acme.jfrog.io/artifactory
if [[ -z "${JFROG_URL:-}" ]]; then
    log "JFROG_URL not set — Conan package uploaded, skipping .deb upload"
    exit 0
fi

target="${JFROG_URL%/}/${GENERIC_REPO}/sensor-hub/${VERSION}/$(basename "${deb}")"
log "uploading $(basename "${deb}") to ${target}"

# Artifactory verifies these against the body it received; a truncated upload
# fails loudly instead of landing a corrupt package in the repository.
sha256="$(sha256sum "${deb}" | cut -d' ' -f1)"
md5="$(md5sum "${deb}" | cut -d' ' -f1)"

http_code="$(curl --silent --show-error --fail-with-body \
    --write-out '%{http_code}' --output /tmp/jfrog-upload.log \
    --header "Authorization: Bearer ${JFROG_TOKEN}" \
    --header "X-Checksum-Sha256: ${sha256}" \
    --header "X-Checksum-Md5: ${md5}" \
    --upload-file "${deb}" "${target}")"

if [[ "${http_code}" != "201" && "${http_code}" != "200" ]]; then
    printf 'upload failed with HTTP %s:\n' "${http_code}" >&2
    cat /tmp/jfrog-upload.log >&2
    exit 1
fi

log "published ${target}"
