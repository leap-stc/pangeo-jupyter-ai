# pangeo-jupyter-ai

The `pangeo/pangeo-notebook` image with Jupyter AI v3 and the Claude Code, Codex and Gemini CLI agents preinstalled. Start a server on this image and the Jupyter AI chat panel is there, with every installed agent available as a persona.

## What's in the image

- Base: `pangeo/pangeo-notebook:2026.10.13` (set by `BASE_TAG` in the Dockerfile; match whatever tag the hub's production image uses)
- `jupyter-ai` 3.2.0 from conda-forge, without the optional RTC extras
- `nodejs` 22 in the `notebook` conda env
- Agents installed with npm into the conda env: `claude` + `claude-agent-acp`, `codex` + `codex-acp`, `gemini`
- [`leap-pangeo-mcp`](https://github.com/leap-stc/leap-pangeo-mcp) v0.1.0 (set by `LEAP_PANGEO_MCP_VERSION`), an MCP server that gives the agents working knowledge of LEAP Pangeo; see [LEAP Pangeo tools](#leap-pangeo-tools)

Jupyter AI detects agents from what's on PATH, so the only Jupyter config the image ships is the MCP server list below.

## LEAP Pangeo tools

The `leap-pangeo` MCP server (data catalog, docs, buckets, the user's own server) is registered for each agent as follows:

| Agent | How it gets `leap-pangeo` |
| --- | --- |
| Every persona in the Jupyter AI chat | `PersonaManager.builtin_mcp_servers` in `/srv/conda/envs/notebook/etc/jupyter/jupyter_server_config.d/leap-pangeo-mcp.json`, next to the Jupyter MCP Server (the notebook tools) |
| Gemini CLI in a terminal | `mcpServers` in `/etc/gemini-cli/settings.json`, merged with the user's own servers |
| Claude Code in a terminal | Each user runs once: `claude mcp add --scope user leap-pangeo -- /srv/conda/envs/notebook/bin/leap-pangeo-mcp` |
| Codex in a terminal | Each user runs once: `codex mcp add leap-pangeo -- /srv/conda/envs/notebook/bin/leap-pangeo-mcp` |

Claude Code and Codex have no system-wide setting that adds a local (stdio) server without also blocking the servers users add themselves, so those two are per user; the commands save to `~/.claude.json` and `~/.codex/config.toml` in the persistent home. Claude Code also reads `/etc/claude-code/CLAUDE.md`, built from the server's LEAP primer, which ends with the `claude mcp add` command.

A stdio server named `leap-pangeo` in a user's own `~/.jupyter/mcp_settings.json` replaces the image's entry for that user.

## One-time setup

1. Create a public repository on quay.io, e.g. `<org>/pangeo-jupyter-ai`.
2. On quay.io, create a robot account with **Write** permission on that repository.
3. In this GitHub repo, go to Settings › Secrets and variables › Actions and add `QUAY_USERNAME` and `QUAY_PASSWORD` from the robot account.
4. Replace `YOUR_QUAY_ORG` in `.github/workflows/build.yaml` and `test.yaml`.
5. Enable workflows under the Actions tab.

## Building and releasing

- Open a PR: `test.yaml` builds the image and runs the smoke test at the end of the Dockerfile. Nothing is pushed.
- Merge to `main`: `build.yaml` builds and pushes `quay.io/<org>/pangeo-jupyter-ai:<commit-hash>`.
- Find the new tag under the repository's Tags tab on quay.io.

To pick up newer agents, re-run the build or merge any change; the npm packages resolve to their latest versions at build time. To freeze one, set its `*_VERSION` build arg in the Dockerfile.

## Using the image on the hub

- **Quick test:** on the hub launch page, choose Image › Other... and paste the full tag, e.g. `quay.io/<org>/pangeo-jupyter-ai:1a2b3c4d5e6f`.
- **For everyone:** ask 2i2c to add the tag to the hub's image dropdown (support ticket, or a PR to their infrastructure repo).
- **Build-your-own option:** because this repo has a Dockerfile, users can also paste the repo URL into "Build your own image" and repo2docker will build it directly. That rebuilds on the hub, so the quay.io image is faster for regular use.

## Signing in to an agent

Each user signs in once with their own subscription, from a terminal on the hub:

```bash
claude      # then follow the login prompt
codex login
gemini      # then choose a sign-in method
```

Credentials land in `~/.claude`, `~/.codex` and `~/.gemini`. Chats are `.chat` files in the user's workspace, and custom MCP servers go in `~/.jupyter/mcp_settings.json`. All of that lives in the persistent home directory, so it survives server restarts and carries over to any other image that has Jupyter AI installed.

## Notes

- Don't `COPY` files into `/home/jovyan`; the hub mounts the user's home over it. Put image-wide config under `/srv/conda/envs/notebook/etc/jupyter/` instead.
- `DISABLE_AUTOUPDATER=1` stops Claude Code from updating itself into the image filesystem, where the update would vanish on restart.
- Each agent adds roughly 100–400 MB. Drop any you don't need from the `npm install` line.
