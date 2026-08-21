# Runbook

Operating the stack, and what to do when a piece of it misbehaves.

## Everyday commands

All of these run inside the build environment (`distrobox enter devbox`, or the
builder image). `make help` lists them.

```bash
make build            # conan create sensorcore, then build sensor-hub
make test             # GTest + pytest, JUnit XML into reports/
make test-integration # the same, plus tests against a real container
make deb wheel        # artifacts into dist/
make lint             # every linter, through pre-commit
```

The local stack runs on the host, not inside the development container:

```bash
make keys             # once — generates secrets/deploy_key
make up               # Jenkins controller + agent + deploy target
make deploy           # Ansible installs the built .deb on the target
make smoke            # verifies what is actually serving
make down             # stop everything, remove volumes
```

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

### Rolling back a deployment

The `.deb` is versioned, so rolling back is installing the previous one:

```bash
SOURCE=artifactory SENSORCORE_VERSION=0.1.0 make deploy
```

The role's final check compares the version the daemon reports against the
installed package, so a rollback that silently left the old process running
fails the play instead of looking successful.
