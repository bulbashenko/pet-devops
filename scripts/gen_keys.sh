#!/usr/bin/env bash
#
# Generates the local-only SSH keypair the deploy target trusts.
#
# The key is created on the developer's machine and never committed (secrets/ is
# in .gitignore, and the gitleaks hook would catch it anyway). In the Jenkins
# pipeline the equivalent key comes from the credentials store instead.
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
KEY_DIR="${REPO_ROOT}/secrets"
KEY="${KEY_DIR}/deploy_key"

mkdir -p "${KEY_DIR}"
chmod 700 "${KEY_DIR}"

if [[ -f "${KEY}" ]]; then
    printf 'deploy key already present at %s\n' "${KEY}"
    exit 0
fi

ssh-keygen -t ed25519 -N '' -C 'pet-devops local deploy target' -f "${KEY}" >/dev/null
chmod 600 "${KEY}"
chmod 644 "${KEY}.pub"

printf 'generated %s\n' "${KEY}"
