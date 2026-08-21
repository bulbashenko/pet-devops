# ADR 0004 — One toolchain image everywhere

Status: accepted

## Context

The project targets Ubuntu, but the machine it was developed on runs an
immutable Fedora where installing a C++ toolchain means layering packages and
rebooting. Meanwhile GitHub Actions runners and the Jenkins agent each come with
their own idea of what "gcc" and "cmake" mean. Three environments, three chances
for a build to pass in one place and fail in another for reasons nobody can see.

## Decision

`docker/Dockerfile.builder` defines the one build environment: Ubuntu 24.04 with
GCC, CMake, Conan and uv, plus a Conan profile baked in so `conan create` is
reproducible and parallel jobs cannot race on `conan profile detect`.

Everything builds in it:

* **GitHub Actions** pulls it and runs `make` inside it.
* **The Jenkins agent** (`docker/Dockerfile.jenkins-agent`) is built `FROM` it,
  adding only the remoting client and Ansible.
* **Local development** uses a distrobox container of the same Ubuntu release
  (`scripts/devbox.sh`), which keeps the host untouched.

The GitHub Actions image is tagged with the hash of the Dockerfile, so it is
rebuilt when the toolchain changes and cached the rest of the time.

## Consequences

* "Works on my machine" and "works in CI" become the same claim, because it is
  the same machine.
* A toolchain upgrade is one Dockerfile edit that all three environments pick up.
* The local distrobox is installed by a script rather than being the image
  itself, because a development container wants the developer's home directory
  and editor — that is the one place the environments legitimately differ.
* A developer already on Ubuntu can skip distrobox entirely and either install
  the same apt line or shell into the builder image; `scripts/devbox.sh` says so
  when distrobox is missing.
