# Security and compliance

What is automated, what it catches, and what it deliberately does not.

## Automated checks

| Check | Tool | Where | Gating |
|---|---|---|---|
| Secret detection | gitleaks | pre-commit hook and CI | Yes |
| Python lint and format | ruff | pre-commit hook and CI | Yes |
| C++ format | clang-format | pre-commit hook and CI | Yes |
| Shell script analysis | shellcheck | pre-commit hook and CI | Yes |
| Dockerfile analysis | hadolint | pre-commit hook and CI | Yes |
| Ansible lint | ansible-lint | pre-commit hook and CI | Yes |
| Dependency and config vulnerabilities | Trivy | CI | No — reported to the Security tab |
| Software bill of materials | syft (anchore/sbom-action) | CI | No — attached to the run |
| Package sanity | lintian | `make deb` | No — informational |

Running the linters through pre-commit rather than listing them in the workflow
means a contributor gets the identical result locally: a pull request cannot
fail on something the author had no way to reproduce.

## Secrets

No credential is committed. There are three kinds and each has one home:

* **Artifactory** (`JFROG_URL`, `JFROG_USER`, `JFROG_TOKEN`, `CONAN_REMOTE_URL`) —
  GitHub Actions secrets, and the Jenkins credentials store populated from
  environment variables by `jenkins/casc.yaml`.
* **The deploy SSH key** — generated locally by `scripts/gen_keys.sh` into
  `secrets/`, which is in `.gitignore`. Jenkins gets it as a credential and
  binds it with `sshagent`, so it never lands in a workspace.
* **The Jenkins admin password** — an environment variable with a development
  default. Deploying this controller anywhere reachable means setting
  `JENKINS_ADMIN_PASSWORD`; the README says so.

The Ansible task that downloads from Artifactory is marked `no_log: true`
because the `Authorization` header would otherwise be printed.

## Hardening of the deployed service

`packaging/deb/sensor-hub.service` runs the daemon as a dedicated system user
with the systemd sandbox applied: `ProtectSystem=strict`, `PrivateDevices`,
`NoNewPrivileges`, a restricted capability bounding set, and address families
limited to IPv4 and IPv6.

Container deploy targets are the one exception. Applying that sandbox needs
capabilities a rootless container does not have, and the service fails to start
with `status=217/USER`. The Ansible role detects a container target and installs
a drop-in that lifts the sandbox **there only** — a VM or bare-metal host keeps
every directive. The alternative, weakening the shipped unit so it starts
everywhere, would have traded real production hardening for test convenience.

## What is not covered

Being explicit about the gaps is part of the point:

* **Artifacts are not signed.** They carry SHA-256 checksums, which detects
  corruption but not substitution. Signing (cosign for the image, a signed
  `Release` file for a real apt repository) is the next step.
* **No provenance attestation.** There is no SLSA-style statement binding an
  artifact to the build that produced it.
* **Trivy findings do not fail the build.** On a project with real users this
  would gate on HIGH and CRITICAL with a documented exception process; here it
  reports so the output stays readable.
* **The apt repository is a generic Artifactory repository**, not a signed one,
  so `apt-get install` works from a URL but `apt update` against a proper
  repository does not.
* **No runtime security monitoring.** The daemon exposes health and metrics
  endpoints; nothing scrapes or alerts on them.
