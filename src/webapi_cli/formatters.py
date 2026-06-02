"""Output formatters for the WebAPI CLI — rich tables, JSON, and raw output."""

from __future__ import annotations

import json
import sys
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()


# ------------------------------------------------------------------
# Tool list (discover)
# ------------------------------------------------------------------

def format_tool_list(tools: list[dict[str, Any]], server: str, pretty_print: bool = False) -> None:
    """Print a formatted table of available MCP tools.

    Args:
        tools: List of tool definition dicts from ``tools/list``.
        server: Server URL for the header.
        pretty_print: If True, output raw JSON instead of a table.
    """
    if pretty_print:
        sys.stdout.write(json.dumps(tools, indent=2, ensure_ascii=False) + "\n")
        return

    if not tools:
        console.print("[yellow]No tools available.[/yellow]")
        return

    table = Table(title=f"Available tools on [bold]{server}[/bold]", show_lines=False)
    table.add_column("Tool", style="cyan", no_wrap=True)
    table.add_column("Description", style="green")

    for tool in sorted(tools, key=lambda t: t.get("name", "")):
        name = tool.get("name", "")
        desc = tool.get("description", "") or ""
        # Truncate long descriptions
        if len(desc) > 120:
            desc = desc[:117] + "..."
        table.add_row(name, desc)

    console.print(table)


# ------------------------------------------------------------------
# Tool detail (describe)
# ------------------------------------------------------------------

def format_tool_detail(tool: dict[str, Any], pretty_print: bool = False) -> None:
    """Print detailed information about a single tool.

    Args:
        tool: A single tool definition dict.
        pretty_print: If True, output raw JSON.
    """
    if pretty_print:
        sys.stdout.write(json.dumps(tool, indent=2, ensure_ascii=False) + "\n")
        return

    name = tool.get("name", "unknown")
    desc = tool.get("description", "No description")
    http_method = _guess_http_method(name)

    console.print(f"\n[bold cyan]{name}[/bold cyan]")
    console.print(f"[dim]{desc}[/dim]\n")

    schema = tool.get("inputSchema", {})
    all_props = schema.get("properties", {}) or {}
    required = schema.get("required", [])

    # Separate body param from path/query params
    body_prop = all_props.pop("body", None) if "body" in all_props else None
    path_params = {k: v for k, v in all_props.items() if k != "body"}
    body_nested = (body_prop or {}).get("properties") if isinstance(body_prop, dict) else None

    # Path/query parameters
    if path_params:
        console.print("[bold]Path/Query Parameters[/bold] (use [cyan]--params[/cyan]):")
        for pname, pinfo in sorted(path_params.items()):
            req_mark = " [red]*[/red]" if pname in required else ""
            console.print(f"  [cyan]{pname}[/cyan] ({_format_type(pinfo, False)}){req_mark}")
            _print_param_details(pinfo, "    ")
    elif not body_nested:
        console.print("[dim]No path/query parameters.[/dim]")

    # Body
    if body_nested:
        console.print(f"\n[bold]Request Body[/bold] (use [cyan]--body[/cyan]): [dim italic]{body_prop.get('title', '')}[/dim italic]")
        for pname, pinfo in sorted(body_nested.items()):
            req_mark = " [red]*[/red]" if pname in (body_prop.get("required") or []) else ""
            console.print(f"  [cyan]{pname}[/cyan] ({_format_type(pinfo, False)}){req_mark}")
            _print_param_details(pinfo, "    ")
    elif body_prop and not body_nested:
        # Body without nested properties (free-form string/object)
        console.print(f"\n[bold]Request Body[/bold] (use [cyan]--body[/cyan]): ({_format_type(body_prop, False)})")
        desc_text = body_prop.get("description", "")
        if desc_text:
            console.print(f"  [dim]{desc_text}[/dim]")

    # Usage hint
    console.print(f"\n[dim]Usage[/dim]:")
    params_part = ""
    if path_params:
        params_part = " --params '{" + ", ".join(
            f'"{pn}":"..."' for pn in sorted(path_params.keys())
        ) + "}'"
    body_part = ""
    if body_nested:
        body_part = " --body '{" + ", ".join(
            f'"{pn}":"..."' for pn in sorted(body_nested.keys())
        ) + "}'"
    elif body_prop:
        body_part = " --body '...'"
    console.print(f"  [bold]webapi call {name}{params_part}{body_part}[/bold]")

    annotations = tool.get("annotations", {})
    if annotations:
        console.print("\n[bold]Flags:[/bold]")
        if annotations.get("readOnlyHint"):
            console.print("  [dim]Read-only[/dim]")
        if annotations.get("destructiveHint"):
            console.print("  [red]Destructive[/red]")


def _print_param_details(pinfo: dict[str, Any], indent: str) -> None:
    """Print extra details for a single parameter: description, enum, example, default."""
    desc = pinfo.get("description", "")
    title = pinfo.get("title", "")
    if title and title != pinfo.get("name", ""):
        console.print(f"{indent}  [dim italic]{title}[/dim italic]")
    if desc:
        console.print(f"{indent}  [dim]{desc}[/dim]")
    enum_vals = pinfo.get("enum")
    if enum_vals:
        console.print(f"{indent}  [yellow]Options:[/yellow] {', '.join(str(v) for v in enum_vals)}")
    example = pinfo.get("example")
    if example is not None:
        console.print(f"{indent}  [dim]Example:[/dim] {example}")
    default = pinfo.get("default")
    if default is not None:
        console.print(f"{indent}  [dim]Default:[/dim] {default}")
    # Recurse into nested objects inside body fields
    nested_props = pinfo.get("properties")
    if nested_props:
        for nname, ninfo in sorted(nested_props.items()):
            console.print(f"{indent}    [cyan]{nname}[/cyan] ({_format_type(ninfo, False)})")
            _print_param_details(ninfo, indent + "      ")


def _guess_http_method(name: str) -> str:
    """Guess the HTTP method from a tool name's suffix."""
    suffixes = {"get", "post", "put", "patch", "delete", "head", "options"}
    parts = name.rsplit("__", 1)
    if len(parts) == 2 and parts[1].lower() in suffixes:
        return parts[1].upper()
    return "?"


def _print_schema(schema: dict[str, Any], indent: str) -> None:
    props = schema.get("properties", {})
    required = schema.get("required", [])

    if not props:
        return

    console.print(f"{indent}[bold]Parameters:[/bold]")
    for pname, pinfo in sorted(props.items()):
        req_mark = " [red]*[/red]" if pname in required else ""
        ptype = _format_type(pinfo)
        pdesc = pinfo.get("description", "")
        title = pinfo.get("title", "")
        console.print(f"{indent}  [cyan]{pname}[/cyan] ({ptype}){req_mark}")
        if title and title != pname:
            console.print(f"{indent}    [dim italic]{title}[/dim italic]")
        if pdesc:
            console.print(f"{indent}    [dim]{pdesc}[/dim]")
        # Show enum values
        enum_vals = pinfo.get("enum")
        if enum_vals:
            console.print(f"{indent}    [yellow]Options:[/yellow] {', '.join(str(v) for v in enum_vals)}")
        # Show example
        example = pinfo.get("example")
        if example is not None:
            console.print(f"{indent}    [dim]Example:[/dim] {example}")
        # Show default
        default = pinfo.get("default")
        if default is not None:
            console.print(f"{indent}    [dim]Default:[/dim] {default}")

    # Recurse into nested objects
    for pname, pinfo in props.items():
        nested_props = pinfo.get("properties")
        if nested_props:
            console.print(f"\n{indent}  [bold]{pname}[/bold] fields:")
            nested_schema = {"properties": nested_props}
            if pinfo.get("required"):
                nested_schema["required"] = pinfo["required"]
            _print_schema(nested_schema, indent + "    ")


def _format_type(pinfo: dict[str, Any], _recurse: bool = True) -> str:
    """Return a human-readable type string for a property info dict."""
    base = pinfo.get("type", "string")
    fmt = pinfo.get("format")
    has_props = "properties" in pinfo
    has_items = "items" in pinfo

    if has_props:
        return "object"
    if has_items and isinstance(pinfo["items"], dict):
        item_type = pinfo["items"].get("type", "string")
        return f"array[{item_type}]"
    if fmt == "int32":
        return "integer"
    return base


# ------------------------------------------------------------------
# Tool call result
# ------------------------------------------------------------------

def format_tool_result(result: dict[str, Any], pretty_print: bool = False) -> None:
    """Format the result of a tool invocation.

    Args:
        result: The ``result`` object from a ``tools/call`` response.
        pretty_print: If True, output raw JSON.
    """
    if pretty_print:
        sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        return

    is_error = result.get("isError", False)
    structured = result.get("structuredContent", {})
    status = structured.get("status", 0)

    if is_error:
        console.print(f"[red]Tool returned error (HTTP {status})[/red]")

    # Print the text content first (the human-readable part)
    for entry in result.get("content", []):
        if entry.get("type") == "text":
            console.print(entry.get("text", ""))
            break


# ------------------------------------------------------------------
# Profiles
# ------------------------------------------------------------------

def format_profiles(config: Any, pretty_print: bool = False) -> None:
    """Print the list of configured profiles.

    Args:
        config: The Config instance.
        pretty_print: If True, output raw JSON.
    """
    if pretty_print:
        payload = {
            "current_profile": config.current_profile,
            "profiles": {
                name: {"server_url": p.server_url, "default": p.default}
                for name, p in config.profiles.items()
            },
        }
        sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        return

    if not config.profiles:
        console.print("[yellow]No profiles configured. Run [bold]webapi login[/bold] to get started.[/yellow]")
        return

    table = Table(title="Profiles")
    table.add_column("Current", style="bold", width=8)
    table.add_column("Name", style="cyan")
    table.add_column("Server URL", style="green")

    for name, profile in config.profiles.items():
        current = "*" if name == config.current_profile else ""
        table.add_row(current, name, profile.server_url)

    console.print(table)
