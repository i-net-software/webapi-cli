"""Dynamic shell completion support for WebAPI tool names.

Provides a callback for Typer's ``autocompletion`` parameter that fetches
tool names from the server (with file caching so repeated <Tab> presses are
instant).
"""

from __future__ import annotations

from .config import Config


def tool_name_completer(incomplete: str = "") -> list[str]:
    """Return tool names matching *incomplete* for shell completion.

    Loads from the on-disk cache first (instant).  Falls back to a live
    server call only if the cache is stale or missing.
    """
    try:
        config = Config.load()
        profile = config.get()
        if profile is None or not profile.server_url:
            return []
    except Exception:
        return []

    try:
        from .mcp_client import McpClient

        client = McpClient(profile.server_url, profile.bearer_token)

        # Try disk cache first (instant)
        tools = client.list_tools_cached()
        if tools is None:
            # Cache miss — do a live fetch
            client.initialize()
            tools = client.list_tools()
        client.close()
    except Exception:
        return []

    names = [t.get("name", "") for t in tools if t.get("name")]
    return [n for n in names if n.startswith(incomplete)]
