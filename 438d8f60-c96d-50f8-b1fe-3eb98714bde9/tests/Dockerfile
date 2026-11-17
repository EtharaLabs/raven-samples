# syntax=docker/dockerfile:1.10@sha256:865e5dd094beca432e8c0a1d5e1c465db5f998dca4e439981029b3b81fb39ed5
FROM --platform=$BUILDPLATFORM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS build
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV PIP_NO_INPUT=1 PIP_DISABLE_PIP_VERSION_CHECK=1
# git is a BUILD-STAGE-ONLY tool: pip needs it to clone harbor-rewardkit from
# its git+https ref below. It never reaches the runtime stage, so it is not part
# of the verifier's grading surface and needs no pinned version. Reproducibility
# is already fixed by the base image @sha256 (its apt set is internally
# consistent with its own security-patched perl-base) plus the exact @fdba28fc
# pip ref. Pinning an exact git version against a separate dated snapshot instead
# fights the digest's perl-base and is both fragile and unnecessary here.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir "harbor-rewardkit @ git+https://github.com/harbor-framework/harbor@fdba28fc411e47e8765420a1a063b4918fce3def#subdirectory=packages/rewardkit"

FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
LABEL org.opencontainers.image.title="raven-ar9-temporal-deadline-verifier"
LABEL org.opencontainers.image.description="Separate verifier image for AR9 temporal-deadline anchor 12d73d30; carries harbor-rewardkit pinned at Harbor fdba28fc."
LABEL org.opencontainers.image.version="0.1.0"
LABEL org.opencontainers.image.vendor="Green Rider Technology LLP (Ethara AI)"
LABEL org.opencontainers.image.source="https://github.com/EtharaOrion/raven"
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
COPY --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# The in-flow judge (tests/judge/runner.py) dials an OpenAI-compatible endpoint over urllib
# (OPENAI_API_KEY / OPENAI_BASE_URL, injected by the harness at launch). No model CLI is baked;
# python:3.12-slim already ships ca-certificates for the TLS call.
WORKDIR /tests
# Build context is tests/ (Harbor verifier context_dir = the verifier Dockerfile's
# own directory), so the context root IS the tests tree; copy it wholesale.
COPY . /tests/
USER 10001:10001
CMD ["/bin/sh", "/tests/test.sh"]
