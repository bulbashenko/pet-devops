# Architecture decision records

Short notes on the choices that shaped this project — each states the problem,
the decision, the alternative that was rejected, and what the choice costs.

| # | Decision |
|---|---|
| [0001](0001-gha-gates-jenkins-releases.md) | GitHub Actions gates pull requests, Jenkins cuts releases |
| [0002](0002-version-from-git-tag.md) | One version, derived from the git tag |
| [0003](0003-logic-lives-in-scripts.md) | Build logic lives in scripts, never in CI configuration |
| [0004](0004-one-toolchain-image.md) | One toolchain image everywhere |
| [0005](0005-jenkins-as-code.md) | The Jenkins controller is configured only from code |
