# syntax=docker/dockerfile:1
#
# Pangeo + Jupyter AI
# -------------------
# The full pangeo-notebook stack with Jupyter AI v3 and its ACP agents
# (Claude Code, Codex, Gemini CLI) preinstalled. Users who start a server on
# this image get the chat panel and agents with nothing to install.
#
# Pin BASE_TAG to the same pangeo-notebook tag the hub already offers so the
# scientific stack is identical to the production image. Bump deliberately.
ARG BASE_TAG=2026.10.13
FROM pangeo/pangeo-notebook:${BASE_TAG}

# pangeo-notebook already sets NB_USER=jovyan, CONDA_ENV=notebook and puts
# NB_PYTHON_PREFIX=/srv/conda/envs/notebook first on PATH. Its ONBUILD hooks
# (environment.yml, postBuild, ...) only fire in its own build, not in ours,
# so every step below is explicit.
#
# Never COPY anything into /home/jovyan: on the hub, the user's persistent
# home directory is mounted over it and anything placed there is hidden.
USER ${NB_USER}

# --- Jupyter AI + Node.js ---------------------------------------------------
# jupyter-ai 3.2.0 is on conda-forge. The plain package (no [rtc] extras)
# no longer depends on jupyter-server-documents, which was the source of the
# instability 2i2c warns about. Node.js is needed for the npm-based agents.
ARG JUPYTER_AI_VERSION=3.2.0
ARG NODEJS_VERSION=22
RUN mamba install --yes --name ${CONDA_ENV} --channel conda-forge \
        "jupyter-ai=${JUPYTER_AI_VERSION}" \
        "nodejs=${NODEJS_VERSION}" \
 && mamba clean --all --force-pkgs-dirs --yes

# --- ACP agents ---------------------------------------------------------------
# Conda's node lives in the notebook env, so `npm install -g` puts these
# binaries in ${NB_PYTHON_PREFIX}/bin, which is already on PATH. Jupyter AI
# auto-detects an agent when its executable is on PATH; no extra config.
#
#   Claude Code  -> claude CLI + claude-agent-acp adapter
#   Codex        -> codex CLI  + codex-acp adapter
#   Gemini CLI   -> speaks ACP natively, no adapter
#
# "latest" resolves at build time, so each rebuild picks up current agents
# without tracking releases by hand. Set a version here to pin one.
# Each agent adds roughly 100-400 MB; delete any line you don't want.
ARG CLAUDE_CODE_VERSION=latest
ARG CLAUDE_ACP_VERSION=latest
ARG CODEX_VERSION=latest
ARG CODEX_ACP_VERSION=latest
ARG GEMINI_CLI_VERSION=latest
RUN npm install --global --no-fund --no-audit \
        "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
        "@agentclientprotocol/claude-agent-acp@${CLAUDE_ACP_VERSION}" \
        "@openai/codex@${CODEX_VERSION}" \
        "@zed-industries/codex-acp@${CODEX_ACP_VERSION}" \
        "@google/gemini-cli@${GEMINI_CLI_VERSION}" \
 && npm cache clean --force \
 && rm -rf ${HOME}/.npm /tmp/*

# Claude Code would otherwise update itself into /srv/conda, and that change
# disappears on the next server restart. New versions come from rebuilding.
ENV DISABLE_AUTOUPDATER=1

# --- Smoke test ---------------------------------------------------------------
# Fail the build (and the PR check) if anything didn't land.
RUN python -c "import importlib.metadata as m; print('jupyter-ai', m.version('jupyter-ai'))" \
 && jupyter server extension list 2>&1 | grep -q "jupyter_ai" \
 && jupyter labextension list 2>&1 | grep -q "@jupyter-ai/" \
 && for bin in claude claude-agent-acp codex codex-acp gemini; do \
        command -v "$bin" > /dev/null || { echo "missing: $bin"; exit 1; }; \
    done \
 && echo "Jupyter AI image OK"
