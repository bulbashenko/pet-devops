#!/usr/bin/env bash
#
# Starts and stops the local release stack.
#
# A script rather than a bare `docker compose` line because two things have to
# be prepared first: the toolchain image the agent builds FROM, and the deploy
# key, which reaches Jenkins as an environment variable rather than a mount —
# under rootless containers a 0600 file on the host is unreadable by the jenkins
# user inside the container, and JCasC would silently store an empty key.
#
#   scripts/stack.sh up|down|logs|ps
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

COMPOSE_FILE="docker/compose.yaml"
BUILDER_IMAGE="${BUILDER_IMAGE:-pet-devops-builder:local}"
action="${1:-up}"

log() { printf '\n=== %s ===\n' "$*"; }

compose() {
    BUILDER_IMAGE="${BUILDER_IMAGE}" \
    DEPLOY_KEY="${DEPLOY_KEY:-}" \
    docker compose -f "${COMPOSE_FILE}" "$@"
}

case "${action}" in
    up)
        ./scripts/gen_keys.sh

        # Trailing newline included: OpenSSH rejects a key without one.
        DEPLOY_KEY="$(cat secrets/deploy_key)"$'\n'
        export DEPLOY_KEY

        log "building the toolchain image (${BUILDER_IMAGE})"
        docker build -f docker/Dockerfile.builder -t "${BUILDER_IMAGE}" docker

        log "starting the stack"
        compose up -d --build

        cat <<'EOF'

Jenkins:    http://localhost:8081   (admin / admin)
sensor-hub: http://localhost:8080/healthz   (after `make deploy`)
target host: ssh -i secrets/deploy_key -p 2222 deploy@localhost

EOF
        ;;
    down)
        log "stopping the stack and removing its volumes"
        compose down -v
        ;;
    logs)
        compose logs -f
        ;;
    ps)
        compose ps
        ;;
    *)
        printf 'usage: %s [up|down|logs|ps]\n' "$0" >&2
        exit 2
        ;;
esac
