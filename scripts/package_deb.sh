#!/usr/bin/env bash
#
# Builds dist/sensor-hub_<version>_<arch>.deb from the compiled binary.
#
# A staged tree plus `dpkg-deb --build` is used rather than full debhelper: the
# payload is a single binary, one conffile and one unit, and the explicit stage
# makes what lands on the target host obvious. Moving to debhelper/`dh_make` is
# tracked in the README roadmap.
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

BUILD_TYPE="${BUILD_TYPE:-Release}"
VERSION="$(./scripts/version.sh)"
ARCH="$(dpkg --print-architecture)"
STAGE="${REPO_ROOT}/stage/deb"
DIST="${REPO_ROOT}/dist"

log() { printf '\n=== %s ===\n' "$*"; }

binary="$(find "cpp/sensor-hub/build" -name sensor-hub -type f -perm -u+x 2>/dev/null | head -1 || true)"
if [[ -z "${binary}" ]]; then
    printf 'sensor-hub binary not found — run scripts/build.sh first\n' >&2
    exit 1
fi

log "packaging sensor-hub ${VERSION} (${ARCH}) from ${binary}"

rm -rf "${STAGE}"
mkdir -p "${STAGE}/DEBIAN" \
         "${STAGE}/usr/bin" \
         "${STAGE}/etc/sensor-hub" \
         "${STAGE}/lib/systemd/system" \
         "${STAGE}/usr/share/doc/sensor-hub" \
         "${DIST}"

install -Dm755 "${binary}"                            "${STAGE}/usr/bin/sensor-hub"
install -Dm644 packaging/deb/config.yaml              "${STAGE}/etc/sensor-hub/config.yaml"
install -Dm644 packaging/deb/sensor-hub.service       "${STAGE}/lib/systemd/system/sensor-hub.service"

sed -e "s/@VERSION@/${VERSION}/" -e "s/@ARCH@/${ARCH}/" \
    packaging/deb/control.in > "${STAGE}/DEBIAN/control"

# Marking the config as a conffile is what makes dpkg preserve local edits on
# upgrade instead of silently overwriting them.
printf '/etc/sensor-hub/config.yaml\n' > "${STAGE}/DEBIAN/conffiles"

for script in postinst prerm postrm; do
    install -Dm755 "packaging/deb/${script}" "${STAGE}/DEBIAN/${script}"
done

install -Dm644 LICENSE "${STAGE}/usr/share/doc/sensor-hub/copyright"
{
    printf 'sensor-hub (%s) unstable; urgency=medium\n\n' "${VERSION}"
    printf '  * Automated build from %s\n\n' "$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
    printf ' -- Aleksandr Albekov <bulbashenko69@gmail.com>  %s\n' "$(date -R)"
} > "${STAGE}/usr/share/doc/sensor-hub/changelog"
gzip -9n "${STAGE}/usr/share/doc/sensor-hub/changelog"

# Installed-Size is what apt reports to the operator; compute it rather than guess.
installed_size="$(du -ks --exclude=DEBIAN "${STAGE}" | cut -f1)"
printf 'Installed-Size: %s\n' "${installed_size}" >> "${STAGE}/DEBIAN/control"

package="${DIST}/sensor-hub_${VERSION}_${ARCH}.deb"
fakeroot dpkg-deb --build --root-owner-group "${STAGE}" "${package}" >/dev/null

log "built ${package}"
dpkg-deb --info "${package}"
dpkg-deb --contents "${package}"

if command -v lintian >/dev/null 2>&1; then
    log "lintian"
    # Informational: a hand-rolled package trips a few debhelper-oriented tags.
    LC_ALL=C.UTF-8 lintian --tag-display-limit 0 \
        --suppress-tags no-manual-page,maintainer-script-calls-systemctl \
        "${package}" || true
fi

sha256sum "${package}" > "${package}.sha256"
log "checksum $(cat "${package}.sha256")"
