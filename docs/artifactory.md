# Wiring up Artifactory

The pipeline publishes the `sensorcore` Conan package and the `sensor-hub` `.deb`
to JFrog Artifactory. Everything else works without it — publishing is the one
step that degrades to a logged skip when credentials are absent, which is what
keeps forks and outside pull requests green.

This page is the checklist for turning it on. It needs a JFrog account, so it is
the one part of the setup that cannot be scripted from this repository.

## 1. Create the instance and repositories

Sign up for the JFrog Cloud free tier at <https://jfrog.com/start-free/>. In the
new instance create two repositories:

| Repository | Type | Holds |
|---|---|---|
| `conan-local` | Conan, local | `sensorcore/<version>` |
| `pet-devops-generic` | Generic, local | `sensor-hub_<version>_amd64.deb` and its checksum |

Then create an identity token under **User menu → Edit Profile → Generate an
Identity Token**. Use a token, not your password: it is scoped and revocable.

## 2. Note the four values

```
JFROG_URL          https://<tenant>.jfrog.io/artifactory
JFROG_USER         you@example.com
JFROG_TOKEN        <identity token>
CONAN_REMOTE_URL   https://<tenant>.jfrog.io/artifactory/api/conan/conan-local
```

## 3. Try it locally first

```bash
export JFROG_URL JFROG_USER JFROG_TOKEN CONAN_REMOTE_URL
make build deb publish
```

`scripts/publish.sh` uploads the Conan package with `conan upload`, then PUTs
the `.deb` with `X-Checksum-Sha256` and `X-Checksum-Md5` headers so Artifactory
verifies the body it received rather than trusting the transfer.

## 4. Give the values to GitHub Actions

```bash
for name in JFROG_URL JFROG_USER JFROG_TOKEN CONAN_REMOTE_URL; do
    gh secret set "$name" --body "${!name}"
done
```

The `publish` job checks for `JFROG_TOKEN` and reports a skip when it is
missing, so adding the secrets is all that is needed to turn the job on.

## 5. Give the values to Jenkins

The controller reads them from its environment and stores them as credentials
(`jenkins/casc.yaml`). Export them before starting the stack:

```bash
export JFROG_URL JFROG_USER JFROG_TOKEN CONAN_REMOTE_URL
make down && make up
```

The pipeline's publish stage probes whether the credential holds a value before
binding it, so an incomplete setup skips rather than failing the build.

## 6. Deploy from Artifactory rather than from the workspace

With publishing working, the deploy stage can install the exact artifact that
was published instead of the one sitting in the build tree:

```bash
SOURCE=artifactory make deploy
```

In Jenkins that is the `DEPLOY_SOURCE=artifactory` build parameter. The Ansible
role downloads with the `Authorization` header marked `no_log`, so the token
does not reach the play output.

## If the trial expires

Nothing breaks. Unset the four variables and the pipeline goes back to
resolving dependencies from conancenter and reporting the publish step as
skipped — the same path a contributor without credentials takes.
