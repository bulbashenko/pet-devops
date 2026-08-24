# Runbook

Operating the stack, and what to do when a piece of it misbehaves.

## Where to run commands

**Inside the development container.** Run everything from there:

```bash
distrobox enter devbox
```

It is the only place where every command works. It has the compiler, CMake,
Conan, uv and Ansible, and `scripts/devbox.sh` installs a `docker` shim that
forwards to the host — so even starting and stopping the container stack works
from inside it. The container also shares the host's network namespace, which is
why `localhost:8080` means the same thing on both sides.

A developer already on Ubuntu does not need distrobox at all: install the same
packages listed in `docker/Dockerfile.builder`, or shell into that image.

One trap worth knowing: distrobox shares your home directory, so `~/.local/bin`
puts `conan`, `uv` and `sensorctl` on the host's `PATH` too — where they fail
with `ModuleNotFoundError`, because they are virtualenvs built against the
container's Python. A confusing traceback from one of those on the host almost
always means "you are in the wrong shell", not that anything is broken.

From the host itself only the things needing no toolchain work: `make up`,
`make down`, `make smoke`, `curl`, and git.

## Everyday commands

```bash
make help             # every target, with a one-line description

make build            # conan create sensorcore, then build sensor-hub
make test             # GTest + pytest, JUnit XML into reports/
make test-integration # the same, plus tests against a real container
make deb wheel        # artifacts into dist/
make lint             # every linter, through pre-commit

make up               # Jenkins controller + agent + deploy target
make deploy           # Ansible installs the built .deb on the target
make smoke            # verifies what is actually serving
make down             # stop everything, remove volumes
```

`make up` generates `secrets/deploy_key` on first run, so there is nothing to
set up beforehand.

| Service | URL | Credentials |
|---|---|---|
| Jenkins | http://localhost:8081 | `admin` / `admin` (override with `JENKINS_ADMIN_PASSWORD`) |
| sensor-hub on the target | http://localhost:8080/healthz | — |
| Target host over SSH | `ssh -i secrets/deploy_key -p 2222 deploy@localhost` | key only |

## Cutting a release

```bash
git tag v0.2.0
git push --tags
```

That is the whole procedure. The tag drives the version of the Conan package,
the `.deb`, the wheel and the image alike ([ADR 0002](adr/0002-version-from-git-tag.md)),
GitHub Actions attaches the artifacts to a GitHub release, and the Jenkins job
publishes to Artifactory and deploys.

## Deploying a specific version, in either direction

`SENSORCORE_VERSION` overrides what `scripts/version.sh` derives, and every
deployment path honours it. Rolling back and rolling forward are therefore the
same command with a different value — there is no separate rollback procedure to
get wrong under pressure.

First, find out where you are:

```bash
# What is actually serving
curl -s localhost:8080/healthz

# What the target believes it has installed
docker exec pet-devops-target dpkg-query --showformat='${Version}\n' --show sensor-hub

# Which builds are available locally
ls -1 dist/*.deb | sed 's/.*sensor-hub_//; s/_amd64.deb//'
```

Then deploy the one you want:

```bash
# From a .deb already in dist/
SENSORCORE_VERSION=0.1.0.dev2+gaf66d71 make deploy

# From a released version in Artifactory
SOURCE=artifactory SENSORCORE_VERSION=0.1.0 make deploy

# Back to whatever the working tree is at
make deploy
```

Verify, naming the version you expect so a silent no-op cannot pass:

```bash
make smoke                                          # checks whatever is serving
./scripts/smoke_test.py --expect-version 0.1.0      # fails unless that exact build answers
```

The role compares the version the daemon reports against the package `dpkg` says
is installed and fails the play when they differ, so a deployment that left the
old process running is reported as a failure rather than a success.

In Jenkins the same thing is the `DEPLOY_SOURCE` build parameter — `local` for
the artifact that run built, `artifactory` for a published one.

### Restarting or stopping the deployed service

```bash
docker exec pet-devops-target systemctl status sensor-hub
docker exec pet-devops-target systemctl restart sensor-hub
docker exec pet-devops-target journalctl -u sensor-hub -n 50 --no-pager
```

On a real host these are the same commands over ssh:

```bash
ssh -i secrets/deploy_key -p 2222 deploy@localhost 'sudo systemctl restart sensor-hub'
```

### Starting over

Each level of "start over" costs more than the last; take the cheapest one that
fixes the problem:

```bash
make clean            # build output only — cpp builds, dist, reports, venv
make down && make up   # rebuild the whole stack, discarding Jenkins' volume
docker exec pet-devops-target apt-get purge -y sensor-hub   # uninstall from the target
```

`make down` deletes the Jenkins home volume. That is safe here precisely because
the controller is built from `jenkins/casc.yaml` and holds no state worth
keeping ([ADR 0005](adr/0005-jenkins-as-code.md)).

## Troubleshooting

### The deploy target's service will not start

Symptom: the playbook fails at *Wait for the service to accept connections*, and
the target's journal shows:

```
sensor-hub.service: Failed to keep CAP_SYS_ADMIN: Operation not permitted
sensor-hub.service: Main process exited, code=exited, status=217/USER
```

Cause: the unit's systemd sandbox needs capabilities a rootless container does
not have. The role installs a drop-in on container targets to lift it, so this
should be handled automatically — if it is not, check that fact gathering
detected the container:

```bash
ansible -i ansible/inventory/hosts.ini target-host -m setup \
  -a 'filter=ansible_virtualization_*'
```

### A restart is refused with "Start request repeated too quickly"

A unit that crash-looped sits behind systemd's start rate limit and a plain
restart will not clear it. The role's handler runs `systemctl reset-failed`
first for exactly this reason. By hand:

```bash
docker exec pet-devops-target systemctl reset-failed sensor-hub
docker exec pet-devops-target systemctl restart sensor-hub
```

### Ansible cannot reach the target ("Permission denied (publickey)")

The deploy target has two addresses and two ways of presenting a key, depending
on who is deploying:

| Caller | Address | Key |
|---|---|---|
| Developer on the host | `127.0.0.1:2222` | `secrets/deploy_key` |
| Jenkins agent | `target-host:22` | held by `ssh-agent`, no file |

`scripts/deploy.sh` supplies both with `--extra-vars`, driven by `TARGET_HOST`,
`TARGET_PORT` and whether `SSH_AUTH_SOCK` is set. The inventory deliberately
names no key file: if it did, ssh would offer that one identity, fail to find it
under Jenkins, and never fall back to the agent.

To deploy somewhere else:

```bash
TARGET_HOST=10.0.0.5 TARGET_PORT=22 make deploy
```

### The Jenkins agent stays offline

The agent fetches its own connection secret from the controller on startup
([ADR 0005](adr/0005-jenkins-as-code.md)), so it depends on the controller being
reachable and on the node existing in `casc.yaml`.

```bash
docker logs pet-devops-jenkins-agent
```

`could not obtain a secret for ubuntu-build` means the node is missing —
Configuration as Code failed to apply. Look for `SEVERE` in the controller log:

```bash
docker logs pet-devops-jenkins | grep -iE 'casc|SEVERE'
```

### The build fails with "VERSION ... format invalid"

CMake accepts only numeric version components, and the derived version can be
`0.3.1.dev4+g1a2b3c4`. The CMakeLists files extract the numeric prefix for
CMake's own properties and keep the full string for `version.hpp`. If you add a
new CMake project, copy that handling rather than passing the raw version to
`project()`.

### A container build fails on a stale CMakeCache

`CMakeCache.txt ... is different than the directory ...` means a local `build/`
directory reached the image context. `.dockerignore` excludes it; check that any
new build output directory is listed there too.

### Publishing is skipped

That is by design when `CONAN_REMOTE_URL` and `JFROG_TOKEN` are unset — the
build stays green and reports the skip. To publish locally:

```bash
export CONAN_REMOTE_URL=https://<tenant>.jfrog.io/artifactory/api/conan/conan-local
export JFROG_URL=https://<tenant>.jfrog.io/artifactory
export JFROG_USER=you@example.com
export JFROG_TOKEN=<identity token>
make publish
```

### A rollback is refused

The commands are above, under
[Deploying a specific version](#deploying-a-specific-version-in-either-direction).
Going backwards needs two separate refusals lifted: the `apt` module compares
versions itself and fails with *"A later version is already installed"*, and
dpkg underneath refuses the downgrade. The role sets `force` and
`force-downgrade` for exactly this reason — see `sensor_hub_allow_downgrade` and
`sensor_hub_dpkg_options` in the role defaults.
