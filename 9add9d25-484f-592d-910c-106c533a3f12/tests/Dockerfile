# syntax=docker/dockerfile:1.7.1@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e
# Verifier (grading) image. Built by Harbor for the separate verifier environment from the tests/
# build context. The build phase has network and bakes the whole grader so the grade run needs no
# PyPI: uv (pinned), harbor-rewardkit (pinned), and Node 22 + the codex CLI for the agent judge.
# At grade time the codex judge reaches its model over the [verifier.environment] allowlist with
# the credential from [verifier.env]; the compiled test_output dimension needs no network. Built
# for linux/amd64 and linux/arm64 to match task.toml [metadata].platforms.
FROM python@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159

# Node 22 (for the codex CLI). NodeSource is the pinned major line; pulled only at build time.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && node --version

# Pin uv to an exact version (clears harbor-lint unpinned-python-dependency), then install the
# pinned grader and the codex CLI. The build fails if either executable is not on PATH.
RUN pip install --no-cache-dir uv==0.9.7 \
    && uv pip install --system --no-cache 'harbor-rewardkit==0.1.7' \
    && npm install -g @openai/codex@latest \
    && command -v rewardkit \
    && command -v codex

# Bundle the verifier tree so /tests/test.sh, the compiled dimension (tests/test_output/), and the
# judge dimension (tests/judge/) are present offline at grade time.
COPY . /tests
RUN chmod +x /tests/test.sh

WORKDIR /tests
CMD ["/bin/sh", "/tests/test.sh"]
