#!/usr/bin/env bash
#
# Deploy an arbitrary git ref to the target, for the Release Console web UI.
#
# Runs INSIDE the jenkins-agent container: that is the only place with the full
# toolchain, dpkg-deb and ansible, and it shares a network with target-host. The
# host is Arch and has none of those, so the panel shells out to
# `docker exec pet-devops-jenkins-agent bash /workspace/scripts/release_deploy.sh <ref>`.
#
# The important idea — the one that makes rollback actually work — is that only
# the ARTIFACT is old. The deployment tooling (the Ansible role, deploy.sh) is
# always taken from the current tip, never from the ref being rolled back to.
# Rolling back to a commit that predates "allow downgrades" would otherwise use
# that commit's role and be refused: "a later version is already installed". In
# production you pull an old .deb from a registry and deploy it with today's
# playbook; here we rebuild the old .deb from source because there is no registry.
#
# So there are two checkouts:
#   BUILD_DIR  — the requested ref, used only to compile that version's .deb
#   DEPLOY_DIR — the current tip, whose deploy.sh + Ansible role install it
set -euo pipefail

ref="${1:?usage: release_deploy.sh <git-ref>}"

WORKSPACE_SRC="${WORKSPACE_SRC:-/workspace}"
BUILD_DIR="${RC_BUILD_DIR:-/home/jenkins/release-console-build}"
DEPLOY_DIR="${RC_DEPLOY_DIR:-/home/jenkins/release-console-deploy}"

log() { printf '\n=== %s ===\n' "$*"; }
export PATH="/opt/toolchain/bin:${PATH}"

# --- build the requested version's artifact ---------------------------------
log "checking out ${ref} to build its artifact"
rm -rf "${BUILD_DIR}"
git clone --quiet "${WORKSPACE_SRC}" "${BUILD_DIR}"
cd "${BUILD_DIR}"
git checkout --quiet --detach "${ref}"

VERSION="$(./scripts/version.sh)"
export SENSORCORE_VERSION="${VERSION}"
log "building sensor-hub ${VERSION}"
make build
make deb

deb="${BUILD_DIR}/dist/sensor-hub_${VERSION}_$(dpkg --print-architecture).deb"

# --- deploy it with the CURRENT tooling -------------------------------------
log "preparing current deploy tooling (tip of ${WORKSPACE_SRC})"
rm -rf "${DEPLOY_DIR}"
git clone --quiet "${WORKSPACE_SRC}" "${DEPLOY_DIR}"
cd "${DEPLOY_DIR}"
install -d dist
cp "${deb}" dist/

# The deploy key is generated, not committed, so the clone does not carry it.
install -d -m 700 secrets
cp "${WORKSPACE_SRC}/secrets/deploy_key" secrets/deploy_key
chmod 600 secrets/deploy_key

log "deploying ${VERSION} to target-host with current tooling"
# The agent shares the target's network, so it is reachable by service name.
SENSORCORE_VERSION="${VERSION}" TARGET_HOST=target-host TARGET_PORT=22 SOURCE=local make deploy

log "done: ${VERSION} is deployed"
