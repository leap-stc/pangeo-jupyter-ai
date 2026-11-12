"""Tests for register_agents.py, run by the Dockerfile smoke test.

Each case uses a throwaway home directory. Run outside the image with:
    python -I leap-pangeo-mcp/test_register_agents.py
"""

import json
import os
import sys
import tempfile
import tomllib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import register_agents as r  # noqa: E402


def files(home):
    claude = os.path.join(home, ".claude.json")
    codex = os.path.join(home, ".codex", "config.toml")
    return claude, codex


def read(path):
    with open(path) as f:
        return f.read()


def test_fresh_home():
    with tempfile.TemporaryDirectory() as home:
        r.main(home)
        claude, codex = files(home)
        assert json.loads(read(claude))["mcpServers"]["leap-pangeo"]["command"] == r.COMMAND
        assert tomllib.loads(read(codex))["mcp_servers"]["leap-pangeo"]["command"] == r.COMMAND
        # Second run changes nothing.
        before = read(claude), read(codex)
        r.main(home)
        assert (read(claude), read(codex)) == before


def test_keeps_existing_config():
    with tempfile.TemporaryDirectory() as home:
        claude, codex = files(home)
        with open(claude, "w") as f:
            json.dump({"hasCompletedOnboarding": True, "mcpServers": {"mine": {"command": "x"}}}, f)
        os.makedirs(os.path.dirname(codex))
        with open(codex, "w") as f:
            f.write('model = "gpt-5"\n\n[mcp_servers.mine]\ncommand = "x"')  # no trailing newline
        r.main(home)
        c = json.loads(read(claude))
        assert c["hasCompletedOnboarding"] is True and set(c["mcpServers"]) == {"mine", "leap-pangeo"}
        t = tomllib.loads(read(codex))
        assert t["model"] == "gpt-5" and set(t["mcp_servers"]) == {"mine", "leap-pangeo"}


def test_respects_removal():
    with tempfile.TemporaryDirectory() as home:
        r.main(home)
        claude, codex = files(home)
        with open(claude, "w") as f:
            json.dump({"mcpServers": {}}, f)
        with open(codex, "w") as f:
            f.write("")
        r.main(home)
        assert json.loads(read(claude)) == {"mcpServers": {}}
        assert read(codex) == ""


def test_leaves_broken_files_alone():
    with tempfile.TemporaryDirectory() as home:
        claude, codex = files(home)
        with open(claude, "w") as f:
            f.write("{not json")
        os.makedirs(os.path.dirname(codex))
        with open(codex, "w") as f:
            f.write("mcp_servers = { other = { command = 'x' } }\n")  # inline table: can't append
        r.main(home)
        assert read(claude) == "{not json"
        assert read(codex) == "mcp_servers = { other = { command = 'x' } }\n"
        assert not os.path.exists(os.path.join(home, ".local", "state", "leap-pangeo-mcp", "registered-claude"))


def test_opt_out():
    with tempfile.TemporaryDirectory() as home:
        os.environ["LEAP_PANGEO_MCP_AUTOREGISTER"] = "0"
        try:
            r.main(home)
        finally:
            del os.environ["LEAP_PANGEO_MCP_AUTOREGISTER"]
        assert os.listdir(home) == []


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("register_agents OK")
