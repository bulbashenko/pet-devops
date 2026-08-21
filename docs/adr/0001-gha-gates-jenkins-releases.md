# ADR 0001 — GitHub Actions gates pull requests, Jenkins cuts releases

Status: accepted

## Context

The project needs both CI systems represented, and having two of them raises an
obvious question: which one owns what? "Both do everything" is the worst answer —
two implementations of the same pipeline drift, and when they disagree nobody
knows which one is right.

## Decision

The split follows where the work naturally belongs.

**GitHub Actions gates pull requests.** It runs on every push and pull request:
linting, unit tests, packaging, a `.deb` install check, and the security scans.
It is fast, its results are visible to anyone looking at the repository, and it
needs no infrastructure to exist.

**Jenkins cuts releases.** It builds tagged versions, publishes the Conan
package and the `.deb` to Artifactory, deploys to the target host and smoke
tests the result. These are exactly the steps that need things a public runner
does not have: credentials for an internal registry and network access to a
deploy target.

Neither system contains build logic. Both call `make` targets, and the targets
call `scripts/`. See [ADR 0003](0003-logic-lives-in-scripts.md).

## Consequences

* A contributor gets fast feedback without any access to internal systems.
* The release path is exercised in one place, so there is one answer to "how did
  this version get to production".
* The two systems overlap on build and test, deliberately: that overlap is what
  proves the `make` targets are not secretly coupled to one CI system's
  environment.
* GitHub Actions also has a publish job, but it is conditional on credentials
  being present. Without them it reports as skipped rather than failing, so
  forks and outside pull requests stay green.
