# ADR 0002 — One version, derived from the git tag

Status: accepted

## Context

A single commit produces four differently-packaged artifacts:

| Artifact | Format |
|---|---|
| `sensorcore` | Conan package |
| `sensor-hub` | `.deb` and a container image |
| `sensorctl` | Python wheel and sdist |

Each format has its own idea of what a version is, and each ecosystem has its
own idiomatic way to set one — `project(VERSION)` in CMake, `debian/changelog`
for dpkg, `[project] version` for Python. Following each convention separately
means four places to bump and four chances to forget one, and then "sensor-hub
1.4.0" and "sensorctl 1.3.2" turn out to be the same commit.

## Decision

The git tag is the only version input. `scripts/version.sh` reads it with
`git describe` and every other consumer derives from that script:

* CMake takes `-DSENSORCORE_VERSION`, injected by the Conan recipe.
* The Conan recipes take `--version` on the command line.
* The wheel uses `hatch-vcs`, which reads the same tag.
* `scripts/package_deb.sh` renders `packaging/deb/control.in`.
* The container tag uses `scripts/version.sh --docker`.

Off a tag the script produces `X.Y.Z.devN+g<sha>`, so an untagged build is still
unique and traceable back to a commit.

Two details are worth noting because they cost debugging time:

* CMake's `project(VERSION)` accepts only numeric components, so it gets the
  numeric prefix while the full string goes into `version.hpp` and is what the
  API reports.
* Docker tags cannot contain `+`, hence the `--docker` mode.

## Consequences

* Releasing is `git tag vX.Y.Z && git push --tags`. Nothing else to edit.
* All four artifacts from one commit always carry the same version, which is
  what lets the smoke test assert that the daemon serving traffic is the exact
  build that was just deployed.
* Builds need the tag history: CI must check out with `fetch-depth: 0`.
