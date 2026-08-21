#!/bin/sh
# Installs the deploy public key that the compose stack mounts, then hands over
# to systemd as PID 1.
set -eu

KEY_SOURCE=/run/deploy-key/deploy_key.pub
AUTHORIZED_KEYS=/home/deploy/.ssh/authorized_keys

if [ -f "${KEY_SOURCE}" ]; then
    install -d -m 0700 -o deploy -g deploy /home/deploy/.ssh
    install -m 0600 -o deploy -g deploy "${KEY_SOURCE}" "${AUTHORIZED_KEYS}"
else
    echo "warning: ${KEY_SOURCE} is missing — run 'make keys' before 'make up'" >&2
fi

exec /sbin/init
