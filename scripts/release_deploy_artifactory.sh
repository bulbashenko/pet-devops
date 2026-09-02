#!/usr/bin/env bash
#
# Deploy an already-published version by pulling its prebuilt .deb from
# Artifactory — no rebuild. This is the "real" rollback: the artifact that was
# released is the exact one that goes back on the target.
#
# Runs INSIDE the jenkins-agent container (same reasons as release_deploy.sh).
# The version is passed directly — it must already exist in the generic repo,
# which the Release Console checks before offering this path.
#
#   release_deploy_artifactory.sh <version>
#   requires JFROG_URL and JFROG_TOKEN in the environment
set -euo pipefail

version="${1:?usage: release_deploy_artifactory.sh <version>}"
: "${JFROG_URL:?JFROG_URL is required}"
: "${JFROG_TOKEN:?JFROG_TOKEN is required}"

WORKSPACE_SRC="${WORKSPACE_SRC:-/workspace}"
DEPLOY_DIR="${RC_DEPLOY_DIR:-/home/jenkins/release-console-deploy}"

log() { printf '\n=== %s ===\n' "$*"; }
export PATH="/opt/toolchain/bin:${PATH}"

log "preparing current deploy tooling (tip of ${WORKSPACE_SRC})"
rm -rf "${DEPLOY_DIR}"
git clone --quiet "${WORKSPACE_SRC}" "${DEPLOY_DIR}"
cd "${DEPLOY_DIR}"

install -d -m 700 secrets
cp "${WORKSPACE_SRC}/secrets/deploy_key" secrets/deploy_key
chmod 600 secrets/deploy_key

log "pulling sensor-hub ${version} from Artifactory and deploying (no rebuild)"
SENSORCORE_VERSION="${version}" SOURCE=artifactory \
    TARGET_HOST=target-host TARGET_PORT=22 make deploy

log "done: ${version} deployed from Artifactory"
