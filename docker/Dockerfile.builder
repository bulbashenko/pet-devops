# Build environment shared by every place that compiles this project:
# local `make build`, the GitHub Actions job (`container:`) and the Jenkins
# agent (docker/Dockerfile.jenkins-agent builds FROM this image).
#
# One image means "works on my machine" and "works in CI" are the same claim.
FROM docker.io/library/ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
ARG CONAN_VERSION=2.31.2
ARG UV_VERSION=0.12.5
ARG HADOLINT_VERSION=2.12.0
ARG PRE_COMMIT_VERSION=4.6.2

# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        clang-format \
        cmake \
        curl \
        dpkg-dev \
        fakeroot \
        git \
        jq \
        lintian \
        ninja-build \
        perl \
        pkg-config \
        python3 \
        python3-pip \
        python3-venv \
        shellcheck \
    && rm -rf /var/lib/apt/lists/*

# PEP 668 marks the system interpreter as externally managed; a dedicated venv
# on PATH is the supported way to add build tooling without fighting apt.
ENV VIRTUAL_ENV=/opt/toolchain
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
RUN python3 -m venv "${VIRTUAL_ENV}" \
    && pip install --no-cache-dir \
        "conan==${CONAN_VERSION}" \
        "uv==${UV_VERSION}" \
        "pre-commit==${PRE_COMMIT_VERSION}"

# hadolint as a plain binary rather than through its own container image: the
# containerised hook cannot read bind-mounted files under rootless podman, and
# a linter that only works on some developers' machines is worse than none.
RUN curl -fsSL -o /usr/local/bin/hadolint \
      "https://github.com/hadolint/hadolint/releases/download/v${HADOLINT_VERSION}/hadolint-Linux-x86_64" \
    && chmod +x /usr/local/bin/hadolint

# A profile baked into the image keeps `conan create` reproducible and avoids a
# `conan profile detect` race on parallel CI jobs.
RUN conan profile detect --force

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    CONAN_HOME=/root/.conan2

WORKDIR /workspace

LABEL org.opencontainers.image.source="https://github.com/bulbashenko/pet-devops" \
      org.opencontainers.image.title="pet-devops builder" \
      org.opencontainers.image.description="Ubuntu 24.04 toolchain: gcc, cmake, conan, uv"
