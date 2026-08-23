#!/usr/bin/env bash
#
# Deploys the built package to the target host with Ansible.
#
# Defaults to the .deb this working tree just produced, which is what a
# developer wants; the release pipeline passes SOURCE=artifactory so the exact
# published artifact is what reaches the host.
#
#   SOURCE=local|artifactory   (default: local)
#   TARGET_HOST / TARGET_PORT  where the deploy target is reachable
#   LIMIT=<host pattern>       (default: all hosts in the inventory)
#   CHECK=1                    dry run (--check --diff)
#
# TARGET_HOST/PORT exist because the same target has two addresses: a developer
# on the host reaches the container as 127.0.0.1:2222, while the Jenkins agent
# shares its network and reaches it as target-host:22.
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}/ansible"

SOURCE="${SOURCE:-local}"
VERSION="$(../scripts/version.sh)"
ARCH="$(dpkg --print-architecture 2>/dev/null || echo amd64)"

log() { printf '\n=== %s ===\n' "$*"; }

extra_vars=(
    "sensor_hub_package_source=${SOURCE}"
    "ansible_host=${TARGET_HOST:-127.0.0.1}"
    "ansible_port=${TARGET_PORT:-2222}"
)

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

# Jenkins binds the deploy key with `sshagent`, so in that context there is no
# key file to point at — and generating one would create a key the target has
# never been told to trust.
if [[ -n "${SSH_AUTH_SOCK:-}" ]]; then
    log "using the ssh-agent already present in the environment"
else
    key="${REPO_ROOT}/secrets/deploy_key"
    if [[ ! -f "${key}" ]]; then
        log "no deploy key yet — generating one"
        "${REPO_ROOT}/scripts/gen_keys.sh"
    fi
    extra_vars+=("ansible_ssh_private_key_file=${key}")
fi

args=(deploy.yml)
for var in "${extra_vars[@]}"; do
    args+=(--extra-vars "${var}")
done
[[ -n "${LIMIT:-}" ]] && args+=(--limit "${LIMIT}")
[[ "${CHECK:-0}" == "1" ]] && args+=(--check --diff)

export ANSIBLE_CONFIG="${REPO_ROOT}/ansible/ansible.cfg"
exec ansible-playbook "${args[@]}"
