# syntax=docker/dockerfile:1.10@sha256:865e5dd094beca432e8c0a1d5e1c465db5f998dca4e439981029b3b81fb39ed5
#
# Two runtime targets share one pinned base (acceptance 4). The `oracle` target is
# the only one that copies the engine (raven_ar9/) and the world/ground-truth data
# (universe_0.json), and it runs the MCP server that owns the authoritative event
# log. The `agent` target (the main image) copies neither, so the agent cannot
# import the scenario, clock or derivation to shortcut discovery and must reach the
# estate through the oracle MCP sidecar. `agent` is the LAST stage, so a bare
# `docker build environment/` yields the agent image by default. solution/ and
# tests/ never enter this image: the build context is environment/, so they are
# unreachable by construction (see .dockerignore for the context allowlist).

FROM --platform=$BUILDPLATFORM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS base
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV PIP_NO_INPUT=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# Pins:
#   meta-agents-research-environments==1.2.0  — the ARE engine pin; its provenance commit is
#     a9fd2edccb4bc7e22fbf45c8482a5fef30a2a5a4 (the 1.2.0 PyPI release corresponds to that commit).
#   mcp==1.11.0  — the mcp SDK revision whose `mcp.server.fastmcp.FastMCP` is the
#     API Lane B's create_mcp_server() imports FIRST (server.py). PyPI now also
#     serves an mcp 2.x line where FastMCP is renamed MCPServer; pinning 1.11.0
#     keeps the primary FastMCP path and its streamable-http endpoint (`/mcp`,
#     port 8000, FASTMCP_ env prefix) stable and off the 2.x rename fallback.
RUN pip install --no-cache-dir \
      "meta-agents-research-environments==1.2.0" \
      "mcp==1.11.0"

FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS oracle
LABEL org.opencontainers.image.title="raven-ar9-temporal-deadline-oracle"
LABEL org.opencontainers.image.description="Oracle sidecar for AR9 12d73d30: ARE engine + deterministic clock + MCP surface; owns the authoritative event log on an oracle-only volume."
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
COPY --from=base /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH="/task"
ENV PYTHONDONTWRITEBYTECODE=1
ENV RAVEN_UNIVERSE_PATH="/task/universe_0.json"
# The authoritative event log lives on the oracle-only /authority volume, NOT on any
# agent-writable path. server.flush() writes RAVEN_EVENTLOG_OUT at teardown.
ENV RAVEN_EVENTLOG_OUT="/authority/are_event_log.json"
ENV RAVEN_MCP_TRANSPORT="streamable-http"
ENV FASTMCP_HOST="0.0.0.0"
ENV FASTMCP_PORT="8000"
WORKDIR /task
COPY universe_0.json /task/universe_0.json
COPY raven_ar9/ /task/raven_ar9/
# Oracle runs as its own uid (10002), distinct from the agent uid (10001), and owns
# the authority dir. No agent uid can reach /authority (it is never mounted on main).
RUN mkdir -p /authority && chown -R 10002:10002 /authority /task
RUN install -d -m 1777 /trigger
USER 10002:10002
EXPOSE 8000
CMD ["python", "-m", "raven_ar9.server", "--transport", "streamable-http"]

FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS agent
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
COPY --from=base /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /task
# No engine, no universe: nothing app-specific is copied into the agent image. The
# venv carries mcp/ARE only as libraries (no scenario, no answer, no ground truth).
RUN mkdir -p /logs/artifacts /app && chown -R 10001:10001 /logs /task /app
RUN install -d -m 1777 /trigger
# The image ends as root because validation sandboxes can hang at startup on a non-root
# final stage. The agent still runs as uid 10001: docker-compose.yaml sets
# user "10001:10001" on main and task.toml sets [agent].user = "10001".
USER root
# Harbor injects the agent harness command at runtime; this placeholder keeps the
# image runnable standalone for isolation testing.
CMD ["python", "-c", "import time; time.sleep(2**31)"]
