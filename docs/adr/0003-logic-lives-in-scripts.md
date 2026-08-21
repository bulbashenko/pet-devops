# ADR 0003 — Build logic lives in scripts, never in CI configuration

Status: accepted

## Context

The fastest way to write a pipeline is to put the commands directly into the CI
configuration. It is also the fastest way to end up with a build that only
exists inside that CI system: when it goes red, the only way to reproduce it is
to push another commit and wait, and moving to a different CI system means
rewriting the build from scratch.

This project deliberately runs two CI systems, so the cost of that mistake would
be paid twice.

## Decision

Every step is a script in `scripts/`, exposed as a `make` target. CI
configuration is a thin wrapper that calls `make` and does CI-specific things
only — publishing test reports, uploading artifacts, binding credentials.

```
.github/workflows/ci.yml ─┐
                          ├─> make build|test|package|publish|deploy ──> scripts/*.sh
Jenkinsfile ──────────────┘
```

A rule of thumb that keeps it honest: if a step cannot be run from a developer's
terminal, it is in the wrong place.

## Consequences

* A red build is reproducible locally with the same command that failed.
* Adding a third CI system, or dropping one, is a wrapper change.
* `make` targets are the documented interface, so the README does not have to
  explain two sets of commands.
* The cost is one extra indirection: reading a pipeline means opening the script
  too. That is a fair trade for being able to run it.
