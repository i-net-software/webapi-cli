"""WebAPI CLI — Typer app entry point.

Provides commands to interact with any server exposing a Web API MCP endpoint
at ``/mcp``.  Typical workflow::

    $ webapi login
    $ webapi discover
    $ webapi call <tool> --params '{"key":"val"}'
"""

from __future__ import annotations

import json
from typing import Annotated, Optional

import typer

from .completions import tool_name_completer
from .config import Config
from .config import Profile
from .formatters import console
from .formatters import format_profiles
from .formatters import format_tool_detail
from .formatters import format_tool_list
from .formatters import format_tool_result
from .mcp_client import McpClient
from .mcp_client import McpError

app = typer.Typer(
    name="webapi",
    help="CLI client for the i-net HelpDesk Web API MCP endpoint.",
    no_args_is_help=True,
)

_pretty_opt = Annotated[
    bool,
    typer.Option("--pretty-print", help="Pretty-print JSON output with indentation."),
]

ServerURL = Annotated[
    Optional[str],
    typer.Option("--server", "-s", help="Override server URL for this command."),
]

ParamsOpt = Annotated[
    Optional[str],
    typer.Option("--params", "-p", help='JSON object for query/path parameters.'),
]

BodyOpt = Annotated[
    Optional[str],
    typer.Option("--body", "-b", help="JSON object/string for the request body."),
]


# ------------------------------------------------------------------
# Helper – get a ready-to-use MCP client
# ------------------------------------------------------------------

def _get_config() -> Config:
    cfg = Config.load()
    if cfg.current_profile is None:
        typer.echo(
            "No profile configured.\n"
            "Run [bold]webapi login[/bold] to connect to a server.",
            err=True,
        )
        raise typer.Exit(1)
    if cfg.get() is None:
        typer.echo(
            f"Profile '{cfg.current_profile}' not found.\n"
            "Run [bold]webapi profiles[/bold] to list available profiles.",
            err=True,
        )
        raise typer.Exit(1)
    return cfg


def _make_client(cfg: Config, server: str | None = None) -> McpClient:
    profile = cfg.get()
    assert profile is not None
    url = server or profile.server_url
    if not url:
        typer.echo("No server URL configured.", err=True)
        raise typer.Exit(1)
    return McpClient(url, profile.bearer_token)


# ------------------------------------------------------------------
# login
# ------------------------------------------------------------------

@app.command()
def login(
    server: Annotated[
        Optional[str],
        typer.Option("--server", "-s", help="Server base URL."),
    ] = None,
    token: Annotated[
        Optional[str],
        typer.Option("--token", "-t", help="Bearer token (omit for interactive prompt)."),
    ] = None,
    profile_name: Annotated[
        str,
        typer.Option("--profile", "-P", help="Profile name."),
    ] = "default",
    set_current: Annotated[
        bool,
        typer.Option("--set-current/--no-set-current", help="Make this the active profile."),
    ] = True,
) -> None:
    """Authenticate with a server and store credentials locally."""
    cfg = Config.load()

    # Interactive prompts
    if server is None:
        existing = cfg.get(profile_name)
        default_server = existing.server_url if existing else ""
        server = typer.prompt("Server URL", default=default_server or "https://helpdesk.example.com")

    if token is None:
        if profile_name in cfg.profiles and cfg.profiles[profile_name].bearer_token:
            existing_token = cfg.profiles[profile_name].bearer_token
            masked = existing_token[:8] + "..." if len(existing_token) > 8 else "***"
            use_existing = typer.confirm(f"Use existing Bearer token ({masked})?", default=True)
            if use_existing:
                token = existing_token
        if token is None:
            token = typer.prompt("Bearer token", hide_input=True)

    if not token:
        typer.echo("Bearer token is required.", err=True)
        raise typer.Exit(1)

    # Test connection
    console.print(f"Connecting to {server}...")
    client = McpClient(server, token)
    try:
        result = client.initialize()
    except McpError as exc:
        typer.echo(f"Connection failed: {exc}", err=True)
        raise typer.Exit(1)

    client.close()

    # Save profile
    profile = Profile(
        name=profile_name,
        server_url=server.rstrip("/"),
        bearer_token=token,
        default=set_current,
    )
    cfg.add(profile)
    if set_current:
        cfg.set_current(profile_name)
    cfg.save()

    server_name = result.get("serverInfo", {}).get("title", server)
    version = result.get("serverInfo", {}).get("version", "?")
    n_tools = len(result.get("capabilities", {}).get("tools", {}))

    console.print(f"\n[green]Authenticated![/green]")
    console.print(f"  Server:  {server_name} ({version})")
    console.print(f"  Profile: {profile_name}")

    # Show a quick tool count
    try:
        client = _make_client(cfg)
        client.initialize()
        tools = client.list_tools()
        client.close()
        console.print(f"  Tools:   {len(tools)} available")
    except Exception:
        pass

    if not set_current:
        cfg2 = Config.load()
        cfg2.set_current(profile_name)
        cfg2.save()
        console.print(f"\nRun [bold]webapi discover[/bold] to explore available tools.")


# ------------------------------------------------------------------
# logout
# ------------------------------------------------------------------

@app.command()
def logout() -> None:
    """Destroy the remote session and clear stored credentials."""
    cfg = Config.load()
    profile = cfg.get()
    if profile is None:
        typer.echo("No active profile.", err=True)
        raise typer.Exit(1)

    try:
        client = _make_client(cfg)
        client.initialize()
        client.close()
    except Exception:
        pass

    profile.bearer_token = None
    cfg.add(profile)
    cfg.save()

    console.print(f"Logged out of profile [bold]{cfg.current_profile}[/bold].")


# ------------------------------------------------------------------
# discover
# ------------------------------------------------------------------

@app.command()
def discover(
    pretty_print: _pretty_opt = False,
    server: ServerURL = None,
    refresh: Annotated[
        bool,
        typer.Option("--refresh", "-f", help="Bypass cache and re-fetch tools."),
    ] = False,
) -> None:
    """List all available WebAPI tools on the server."""
    cfg = _get_config()
    client = _make_client(cfg, server)

    try:
        client.initialize()
        tools = client.list_tools(refresh=refresh)
    except McpError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    finally:
        client.close()

    format_tool_list(tools, client.base_url, pretty_print=pretty_print)


# ------------------------------------------------------------------
# describe
# ------------------------------------------------------------------

@app.command()
def describe(
    tool: Annotated[
        str,
        typer.Argument(help="Tool name to describe.", autocompletion=tool_name_completer),
    ],
    pretty_print: _pretty_opt = False,
    server: ServerURL = None,
) -> None:
    """Show the full parameter schema for a tool."""
    cfg = _get_config()
    client = _make_client(cfg, server)

    try:
        client.initialize()
        tools = client.list_tools()
    except McpError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    finally:
        client.close()

    match = [t for t in tools if t.get("name") == tool]
    if not match:
        console.print(f"[red]Tool '{tool}' not found. Run [bold]webapi discover[/bold] to list tools.[/red]")
        raise typer.Exit(1)

    format_tool_detail(match[0], pretty_print=pretty_print)


# ------------------------------------------------------------------
# call
# ------------------------------------------------------------------

@app.command()
def call(
    tool: Annotated[
        str,
        typer.Argument(help="Tool name to invoke.", autocompletion=tool_name_completer),
    ],
    params: ParamsOpt = None,
    body: BodyOpt = None,
    pretty_print: _pretty_opt = False,
    server: ServerURL = None,
) -> None:
    """Invoke an MCP tool (WebAPI endpoint)."""
    cfg = _get_config()
    client = _make_client(cfg, server)

    arguments: dict = {}

    if params:
        try:
            parsed = json.loads(params)
            if isinstance(parsed, dict):
                arguments.update(parsed)
            else:
                typer.echo("--params must be a JSON object (e.g. '{\"key\":\"val\"}')", err=True)
                raise typer.Exit(1)
        except json.JSONDecodeError as exc:
            typer.echo(f"Invalid JSON in --params: {exc}", err=True)
            raise typer.Exit(1)

    if body:
        try:
            parsed_body = json.loads(body)
        except json.JSONDecodeError:
            arguments["body"] = body
        else:
            arguments["body"] = parsed_body

    try:
        client.initialize()
        result = client.call_tool(tool, arguments)
    except McpError as exc:
        typer.echo(f"Tool call failed: {exc}", err=True)
        raise typer.Exit(1)
    finally:
        client.close()

    format_tool_result(result, pretty_print=pretty_print)


# ------------------------------------------------------------------
# profiles
# ------------------------------------------------------------------

profiles_app = typer.Typer(help="Manage server profiles.")
app.add_typer(profiles_app, name="profiles")


@profiles_app.callback(invoke_without_command=True)
def profiles_callback(
    pretty_print: _pretty_opt = False,
) -> None:
    """List all configured profiles."""
    cfg = Config.load()
    format_profiles(cfg, pretty_print=pretty_print)


@profiles_app.command(name="use")
def profiles_use(
    name: Annotated[str, typer.Argument(help="Profile name to activate.")],
) -> None:
    """Switch the active profile."""
    cfg = Config.load()
    try:
        cfg.set_current(name)
    except KeyError:
        typer.echo(f"Profile '{name}' not found.", err=True)
        raise typer.Exit(1)
    cfg.save()
    console.print(f"Switched to profile [bold]{name}[/bold] ({cfg.profiles[name].server_url}).")


@profiles_app.command(name="remove")
def profiles_remove(
    name: Annotated[str, typer.Argument(help="Profile name to delete.")],
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation prompt."),
    ] = False,
) -> None:
    """Remove a stored profile."""
    cfg = Config.load()
    if name not in cfg.profiles:
        typer.echo(f"Profile '{name}' not found.", err=True)
        raise typer.Exit(1)

    if not force:
        typer.confirm(f"Delete profile '{name}' ({cfg.profiles[name].server_url})?", abort=True)

    cfg.remove(name)
    cfg.save()
    typer.echo(
        f"Profile '{name}' removed."
        if cfg.current_profile != name
        else f"Profile '{name}' removed. Active profile is now [bold]{cfg.current_profile}[/bold]."
    )


# ------------------------------------------------------------------
# whoami
# ------------------------------------------------------------------

@app.command()
def whoami(
    server: ServerURL = None,
) -> None:
    """Show the current session and server info."""
    cfg = _get_config()
    profile = cfg.get()
    assert profile is not None
    client = _make_client(cfg, server)

    try:
        result = client.initialize()
        info = result.get("serverInfo", {})
        console.print(f"Profile:  [bold]{cfg.current_profile}[/bold]")
        console.print(f"Server:   {profile.server_url}")
        console.print(f"App:      {info.get('title', '?')} ({info.get('version', '?')})")
        console.print(f"Protocol: {result.get('protocolVersion', '?')}")
    except McpError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    finally:
        client.close()


# ------------------------------------------------------------------
# skill
# ------------------------------------------------------------------

@app.command()
def skill() -> None:
    """Output the AI agent skill file (skill.md)."""
    from pathlib import Path
    skill_path = Path(__file__).resolve().parent / "skill.md"
    if skill_path.exists():
        console.print(skill_path.read_text(encoding="utf-8"))
    else:
        typer.echo("skill.md not found.", err=True)
        raise typer.Exit(1)


def main() -> None:
    """Entry point for ``python -m webapi_cli``."""
    app()


if __name__ == "__main__":
    main()
