#!/usr/bin/env bash
#
# Creates the Ubuntu 24.04 development container and installs the toolchain.
#
# Why: the project targets Ubuntu, but a developer's workstation might not be
# Ubuntu (this one is an immutable Fedora, where layering build tools means a
# reboot). distrobox gives the same distribution the CI image uses, without
# touching the host. See docs/adr/0004-ubuntu-devbox.md.
#
# Run this from the HOST, once:  ./scripts/devbox.sh
# Then work inside it:           distrobox enter devbox
set -euo pipefail

BOX_NAME="${BOX_NAME:-devbox}"
BOX_IMAGE="${BOX_IMAGE:-docker.io/library/ubuntu:24.04}"
CONAN_VERSION="${CONAN_VERSION:-2.31.2}"

if ! command -v distrobox >/dev/null 2>&1; then
    cat >&2 <<'EOF'
distrobox is not installed.

On a machine that already runs Ubuntu you do not need it — install the toolchain
directly with the apt line from docker/Dockerfile.builder, or just build inside
that image:

  docker build -f docker/Dockerfile.builder -t pet-devops-builder:local docker
  docker run --rm -it -v "$PWD:/workspace" pet-devops-builder:local bash
EOF
    exit 1
fi

if ! distrobox list | awk '{print $3}' | grep -qx "${BOX_NAME}"; then
    printf '=== creating %s from %s ===\n' "${BOX_NAME}" "${BOX_IMAGE}"
    distrobox create --name "${BOX_NAME}" --image "${BOX_IMAGE}" --yes
fi

printf '=== installing toolchain in %s ===\n' "${BOX_NAME}"
distrobox enter "${BOX_NAME}" -- bash -s <<EOF
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
export LC_ALL=C.UTF-8 LANG=C.UTF-8

sudo apt-get update -qq
sudo apt-get install -y -qq --no-install-recommends \
    build-essential cmake ninja-build git curl ca-certificates pkg-config \
    python3 python3-venv python3-pip pipx \
    dpkg-dev fakeroot lintian \
    ansible sshpass openssh-client \
    clang-format shellcheck jq

export PATH="\$HOME/.local/bin:\$PATH"
pipx install --quiet "conan==${CONAN_VERSION}" 2>/dev/null || true
pipx install --quiet pre-commit 2>/dev/null || true
pipx install --quiet uv 2>/dev/null || true

conan profile detect --force >/dev/null 2>&1 || true

# A distrobox container has no container runtime of its own, but it does share
# the host's network namespace — so forwarding \`docker\` to the host makes the
# container-backed integration tests work from inside the box unchanged.
if ! command -v docker >/dev/null 2>&1 && command -v distrobox-host-exec >/dev/null 2>&1; then
    printf '%s\n' \
        '#!/bin/sh' \
        'exec distrobox-host-exec docker "\$@"' \
        | sudo tee /usr/local/bin/docker >/dev/null
    sudo chmod +x /usr/local/bin/docker
fi
EOF

cat <<EOF

=== ${BOX_NAME} is ready ===

  distrobox enter ${BOX_NAME}
  make build test

Add this to the container's shell rc if PATH is missing pipx tools:
  export PATH="\$HOME/.local/bin:\$PATH"
EOF
