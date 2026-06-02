"""Output formatters for the WebAPI CLI — JSON output (compact by default, pretty-printed with --pretty-print)."""

from __future__ import annotations

import json
import sys
from typing import Any

from rich.console import Console

console = Console()


def _dump(data: Any, pretty_print: bool) -> str:
    """Serialize *data* to a JSON string.

    Args:
        data: The JSON-serializable object to dump.
        pretty_print: If True, use 2-space indentation; otherwise compact.
    """
    if pretty_print:
        return json.dumps(data, indent=2, ensure_ascii=False)
    return json.dumps(data)


# ------------------------------------------------------------------
# Tool list (discover)
# ------------------------------------------------------------------

def format_tool_list(tools: list[dict[str, Any]], server: str, pretty_print: bool = False) -> None:
    """Print the list of available MCP tools as JSON.

    Args:
        tools: List of tool definition dicts from ``tools/list``.
        server: Server URL (unused; kept for API compatibility).
        pretty_print: If True, pretty-print with 2-space indentation.
    """
    sys.stdout.write(_dump(tools, pretty_print) + "\n")


# ------------------------------------------------------------------
# Tool detail (describe)
# ------------------------------------------------------------------

def format_tool_detail(tool: dict[str, Any], pretty_print: bool = False) -> None:
    """Print detailed information about a single tool as JSON.

    Args:
        tool: A single tool definition dict.
        pretty_print: If True, pretty-print with 2-space indentation.
    """
    sys.stdout.write(_dump(tool, pretty_print) + "\n")


# ------------------------------------------------------------------
# Tool call result
# ------------------------------------------------------------------

def format_tool_result(result: dict[str, Any], pretty_print: bool = False) -> None:
    """Print the result of a tool invocation as JSON.

    Args:
        result: The ``result`` object from a ``tools/call`` response.
        pretty_print: If True, pretty-print with 2-space indentation.
    """
    sys.stdout.write(_dump(result, pretty_print) + "\n")


# ------------------------------------------------------------------
# Profiles
# ------------------------------------------------------------------

def format_profiles(config: Any, pretty_print: bool = False) -> None:
    """Print the list of configured profiles as JSON.

    Args:
        config: The Config instance.
        pretty_print: If True, pretty-print with 2-space indentation.
    """
    payload = {
        "current_profile": config.current_profile,
        "profiles": {
            name: {"server_url": p.server_url, "default": p.default}
            for name, p in config.profiles.items()
        },
    }
    sys.stdout.write(_dump(payload, pretty_print) + "\n")
