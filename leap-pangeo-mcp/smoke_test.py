"""Build-time check that leap-pangeo-mcp and its agent configs landed in the image.

Run by the smoke test at the end of the Dockerfile; any failure fails the build.
To run it outside the image, pass the three config paths as arguments.
"""

import json
import os
import sys

import anyio
from jupyter_ai_persona_manager.mcp_server_models import McpServerHttp, McpServerStdio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from leap_pangeo_mcp.core import knowledge

JUPYTER_CONFIG = "/srv/conda/envs/notebook/etc/jupyter/jupyter_server_config.d/leap-pangeo-mcp.json"
GEMINI_SETTINGS = "/etc/gemini-cli/settings.json"
CLAUDE_MD = "/etc/claude-code/CLAUDE.md"

# The eight Phase 1 tools in leap-pangeo-mcp's SPEC.md.
PHASE_1_TOOLS = {
    "leap_overview",
    "search_datasets",
    "get_dataset",
    "describe_store",
    "list_storage",
    "search_docs",
    "get_my_environment",
    "how_to",
}


def builtin_servers(path):
    """Parse PersonaManager.builtin_mcp_servers the way Jupyter AI does.

    Jupyter AI drops an entry that fails these models with only a log warning,
    so a typo in the config would otherwise remove a server without an error.
    """
    with open(path) as f:
        entries = json.load(f)["PersonaManager"]["builtin_mcp_servers"]
    return [McpServerHttp(**e) if e.get("type") == "http" else McpServerStdio(**e) for e in entries]


async def list_tools(server):
    params = StdioServerParameters(command=server.command, args=server.args)
    with anyio.fail_after(60):
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return [tool.name for tool in (await session.list_tools()).tools]


def main(jupyter_config=JUPYTER_CONFIG, gemini_settings=GEMINI_SETTINGS, claude_md=CLAUDE_MD):
    servers = builtin_servers(jupyter_config)
    http = [s for s in servers if isinstance(s, McpServerHttp)]
    stdio = [s for s in servers if isinstance(s, McpServerStdio)]
    assert len(servers) == 2, f"expected 2 builtin MCP servers, got {len(servers)}"
    assert [s.url for s in http] == ["http://localhost:3001/mcp"], f"Jupyter MCP Server entry missing: {http}"
    assert [s.name for s in stdio] == ["leap-pangeo"], f"leap-pangeo entry missing: {stdio}"
    leap = stdio[0]
    assert os.access(leap.command, os.X_OK), f"not executable: {leap.command}"

    names = anyio.run(list_tools, leap)
    assert len(names) == 8 and set(names) == PHASE_1_TOOLS, f"unexpected tools: {sorted(names)}"

    with open(gemini_settings) as f:
        gemini = json.load(f)["mcpServers"]["leap-pangeo"]
    assert gemini["command"] == leap.command, f"Gemini CLI runs {gemini['command']}, not {leap.command}"

    with open(claude_md) as f:
        text = f.read()
    assert text.startswith(knowledge.overview()), "CLAUDE.md does not start with the LEAP primer"
    assert "claude mcp add --scope user leap-pangeo" in text, "CLAUDE.md lacks the claude mcp add note"

    print(f"leap-pangeo-mcp OK: {len(names)} tools over stdio; Jupyter AI, Gemini CLI and CLAUDE.md configs OK")


if __name__ == "__main__":
    main(*sys.argv[1:])
