# Single entry point for humans and for both CI systems.
#
# GitHub Actions and Jenkins do not reimplement any build logic — they call
# these targets, which call scripts/. Swapping CI means rewriting the thin
# wrapper, never the build. See docs/adr/0003-logic-lives-in-scripts.md.
#
# Run these inside the build environment (the `devbox` distrobox, or the
# pet-devops-builder image). `make devbox` creates that environment.

SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

VERSION        := $(shell ./scripts/version.sh)
DOCKER_TAG     := $(shell ./scripts/version.sh --docker)
ARCH           := $(shell dpkg --print-architecture 2>/dev/null || echo amd64)
BUILD_TYPE     ?= Release

REGISTRY       ?= ghcr.io/bulbashenko
BUILDER_IMAGE  ?= pet-devops-builder:local
RUNTIME_IMAGE  ?= sensor-hub:local

DEB            := dist/sensor-hub_$(VERSION)_$(ARCH).deb

export SENSORCORE_VERSION := $(VERSION)

.PHONY: help
help: ## Show this help
	@printf '\npet-devops — version %s\n\n' '$(VERSION)'
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@printf '\n'

.PHONY: version
version: ## Print the version every artifact will carry
	@printf 'semver : %s\ndocker : %s\ndeb    : %s\n' '$(VERSION)' '$(DOCKER_TAG)' '$(DEB)'

# --- build & test ------------------------------------------------------------

.PHONY: build
build: ## Build sensorcore (conan create) and sensor-hub
	./scripts/build.sh

.PHONY: test
test: ## Run C++ and Python unit tests, writing JUnit XML to reports/
	./scripts/test.sh

.PHONY: test-integration
test-integration: image ## Run the container-backed integration tests
	INTEGRATION=1 SUITE=python SENSOR_HUB_IMAGE=$(RUNTIME_IMAGE) ./scripts/test.sh

.PHONY: lint
lint: ## Run every linter through pre-commit
	pre-commit run --all-files

# --- packaging ---------------------------------------------------------------

.PHONY: deb
deb: ## Build the .deb from the compiled binary
	./scripts/package_deb.sh

.PHONY: wheel
wheel: ## Build the sensorctl wheel and sdist into dist/
	./scripts/package_wheel.sh

.PHONY: package
package: deb wheel ## Build every distributable artifact

.PHONY: publish
publish: ## Upload the Conan package and the .deb to Artifactory (skips without credentials)
	./scripts/publish.sh

# --- images ------------------------------------------------------------------

.PHONY: builder-image
builder-image: ## Build the shared toolchain image
	docker build -f docker/Dockerfile.builder -t $(BUILDER_IMAGE) docker

.PHONY: image
image: builder-image ## Build the sensor-hub runtime image
	docker build -f docker/Dockerfile.runtime \
		--build-arg BUILDER_IMAGE=$(BUILDER_IMAGE) \
		--build-arg SENSORCORE_VERSION=$(VERSION) \
		-t $(RUNTIME_IMAGE) -t sensor-hub:$(DOCKER_TAG) .

# --- local stack -------------------------------------------------------------

.PHONY: keys
keys: ## Generate the local SSH key the deploy target trusts
	./scripts/gen_keys.sh

.PHONY: up
up: ## Start Jenkins, its agent and the deploy target
	./scripts/stack.sh up

.PHONY: down
down: ## Stop the local stack and remove its volumes
	./scripts/stack.sh down

.PHONY: logs
logs: ## Follow the local stack logs
	./scripts/stack.sh logs

.PHONY: deploy
deploy: ## Deploy the built .deb onto the target host with Ansible
	./scripts/deploy.sh

.PHONY: smoke
smoke: ## Verify a deployed instance answers correctly
	./scripts/smoke_test.py

.PHONY: ui
ui: ## Release Console: web panel to view versions and deploy/roll back (http://localhost:8090)
	@python3 webui/server.py

# --- housekeeping ------------------------------------------------------------

.PHONY: devbox
devbox: ## Create the Ubuntu 24.04 development container (run once, from the host)
	./scripts/devbox.sh

.PHONY: clean
clean: ## Remove build output
	rm -rf cpp/*/build cpp/*/CMakeUserPresets.json dist stage reports \
	       python/sensorctl/.venv python/sensorctl/src/sensorctl/_version.py
