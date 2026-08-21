#!/usr/bin/env bash
#
# Deploys the built package to the target host with Ansible.
#
# Defaults to the .deb this working tree just produced, which is what a
# developer wants; the release pipeline passes SOURCE=artifactory so the exact
# published artifact is what reaches the host.
#
#   SOURCE=local|artifactory   (default: local)
#   LIMIT=<host pattern>       (default: all hosts in the inventory)
#   CHECK=1                    dry run (--check --diff)
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}/ansible"

SOURCE="${SOURCE:-local}"
VERSION="$(../scripts/version.sh)"
ARCH="$(dpkg --print-architecture 2>/dev/null || echo amd64)"

log() { printf '\n=== %s ===\n' "$*"; }

extra_vars=("sensor_hub_package_source=${SOURCE}")

case "${SOURCE}" in
    local)
        deb="${REPO_ROOT}/dist/sensor-hub_${VERSION}_${ARCH}.deb"
        if [[ ! -f "${deb}" ]]; then
            printf 'no package at %s — run '\''make deb'\'' first\n' "${deb}" >&2
            exit 1
        fi
        extra_vars+=("sensor_hub_local_deb=${deb}")
        log "deploying ${deb}"
        ;;
    artifactory)
        if [[ -z "${JFROG_URL:-}" || -z "${JFROG_TOKEN:-}" ]]; then
            printf 'SOURCE=artifactory needs JFROG_URL and JFROG_TOKEN\n' >&2
            exit 1
        fi
        extra_vars+=(
            "sensor_hub_version=${VERSION}"
            "sensor_hub_artifactory_url=${JFROG_URL%/}/${JFROG_GENERIC_REPO:-pet-devops-generic}"
            "sensor_hub_artifactory_token=${JFROG_TOKEN}"
        )
        log "deploying sensor-hub ${VERSION} from Artifactory"
        ;;
    *)
        printf 'unknown SOURCE=%s (expected local or artifactory)\n' "${SOURCE}" >&2
        exit 2
        ;;
esac

args=(deploy.yml)
for var in "${extra_vars[@]}"; do
    args+=(--extra-vars "${var}")
done
[[ -n "${LIMIT:-}" ]] && args+=(--limit "${LIMIT}")
[[ "${CHECK:-0}" == "1" ]] && args+=(--check --diff)

if [[ ! -f "${REPO_ROOT}/secrets/deploy_key" ]]; then
    log "no deploy key yet — generating one"
    "${REPO_ROOT}/scripts/gen_keys.sh"
fi

export ANSIBLE_CONFIG="${REPO_ROOT}/ansible/ansible.cfg"
exec ansible-playbook "${args[@]}"
