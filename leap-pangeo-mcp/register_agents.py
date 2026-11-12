"""Register the leap-pangeo MCP server with Claude Code and Codex for the current user.

Runs at every server start (from /srv/leap-start, before the base image's
/srv/start). Claude Code and Codex only read MCP servers from the user's own
config files, which live in the persistent home directory that the hub mounts
over the image, so the entries can't be baked in; this adds them instead.

Rules:
- Adds the entry only when the user's config has no server named leap-pangeo.
  Anything else in the file is left exactly as it was.
- Registers each agent at most once per user. A marker in
  ~/.local/state/leap-pangeo-mcp/ records it, so a user who removes the server
  (`claude mcp remove leap-pangeo`) doesn't get it back on the next restart.
- Never fails server start: problems are printed to stderr and skipped.

Set LEAP_PANGEO_MCP_AUTOREGISTER=0 to turn it off.
"""

import json
import os
import sys
import tempfile

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None

NAME = "leap-pangeo"
COMMAND = "/srv/conda/envs/notebook/bin/leap-pangeo-mcp"


def log(msg):
    print(f"leap-pangeo-mcp register: {msg}", file=sys.stderr)


def atomic_write(path, text):
    """Write text to path via a temp file in the same directory, keeping the mode."""
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    mode = os.stat(path).st_mode & 0o777 if os.path.exists(path) else 0o600
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".leap-pangeo-")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def register_claude(home):
    """Add a user-scope stdio server to ~/.claude.json (what `claude mcp add --scope user` writes)."""
    path = os.path.join(home, ".claude.json")
    if os.path.exists(path):
        with open(path) as f:
            text = f.read()
        try:
            config = json.loads(text) if text.strip() else {}
        except json.JSONDecodeError:
            log(f"{path} is not valid JSON; leaving it alone")
            return False
        if not isinstance(config, dict):
            log(f"{path} is not a JSON object; leaving it alone")
            return False
    else:
        config = {}

    servers = config.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        log(f"mcpServers in {path} is not an object; leaving it alone")
        return False
    if NAME in servers:
        return True
    servers[NAME] = {"type": "stdio", "command": COMMAND, "args": [], "env": {}}
    atomic_write(path, json.dumps(config, indent=2) + "\n")
    log(f"added {NAME} to {path}")
    return True


def register_codex(home):
    """Append an [mcp_servers.leap-pangeo] table to ~/.codex/config.toml."""
    if tomllib is None:
        log("Python has no tomllib; skipping Codex")
        return False
    path = os.path.join(home, ".codex", "config.toml")
    text = ""
    if os.path.exists(path):
        with open(path) as f:
            text = f.read()
    try:
        config = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        log(f"{path} is not valid TOML; leaving it alone")
        return False
    if NAME in config.get("mcp_servers", {}):
        return True

    block = f'[mcp_servers.{NAME}]\ncommand = "{COMMAND}"\n'
    new_text = text
    if new_text and not new_text.endswith("\n"):
        new_text += "\n"
    if new_text:
        new_text += "\n"
    new_text += block
    try:
        # Appending a table is invalid if mcp_servers is an inline table, for one.
        if tomllib.loads(new_text).get("mcp_servers", {}).get(NAME, {}).get("command") != COMMAND:
            raise ValueError("entry not readable after append")
    except (tomllib.TOMLDecodeError, ValueError, AttributeError):
        log(f"couldn't add {NAME} to {path} without breaking it; leaving it alone")
        return False
    atomic_write(path, new_text)
    log(f"added {NAME} to {path}")
    return True


AGENTS = {"claude": register_claude, "codex": register_codex}


def main(home=None):
    if os.environ.get("LEAP_PANGEO_MCP_AUTOREGISTER", "1") == "0":
        return
    home = home or os.path.expanduser("~")
    state = os.path.join(home, ".local", "state", "leap-pangeo-mcp")
    for agent, register in AGENTS.items():
        marker = os.path.join(state, f"registered-{agent}")
        if os.path.exists(marker):
            continue
        try:
            if register(home):
                os.makedirs(state, exist_ok=True)
                with open(marker, "w") as f:
                    f.write(f"{NAME} registered for {agent}; delete this file to have it re-added\n")
        except Exception as e:  # never block server start
            log(f"{agent}: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main(*sys.argv[1:])
