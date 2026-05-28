# WebAPI CLI

Command-line client for i-net HelpDesk Web API servers.  
Uses the server's **MCP endpoint** (`/mcp`) to dynamically discover and invoke
any WebAPI endpoint without hardcoding URLs or schemas.

## Prerequisites

1. **uv** — the package manager that runs the CLI. Install it once:

   ```bash
   # macOS / Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Windows (PowerShell)
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

   # macOS via Homebrew
   brew install uv

   # Windows via winget
   winget install --id=astral-sh.uv -e
   ```

   After installing, restart your terminal.

2. A **Bearer token** with WebAPI access (see [Getting a Bearer token](#getting-a-bearer-token))

## Installation

```bash
# Install globally from GitHub
uv tool install --from git+https://github.com/i-net-software/webapi-cli webapi-cli

# Or from a local wheel
uv tool install /path/to/webapi_cli-1.0.0-py3-none-any.whl

# Or from a local checkout
uv tool install /path/to/WebAPICLI

# Or one-shot — no install needed (credentials still persist)
uvx --from git+https://github.com/i-net-software/webapi-cli webapi discover
```

Verify it's on your PATH:

```bash
webapi --help
```

## Getting a Bearer token

You need a Bearer token that grants access to the Web API.  Generate one in the
HelpDesk administration UI:

1. Log in to your HelpDesk server as an administrator
2. Navigate to **Administration → Web API → Bearer Tokens**
3. Click **Create token**, give it a name, and select the WebAPI permissions
   you need (e.g. `WebAPI - cowork`, `WebAPI - tickets`)
4. Copy the generated token — it's shown only once

> **Tip:** Create a dedicated token for your CLI usage so you can revoke it
> independently.  If you use multiple servers (dev/staging/prod), generate
> one token per server.

## Quick Start (2 minutes)

```bash
# 1. Authenticate — interactive, asks for server URL and token
webapi login

# 2. See what's available
webapi discover

# 3. Inspect a tool's parameters
webapi describe cowork__teams__get

# 4. Call a tool
webapi call cowork__teams__get
webapi call ticket__search__post --params '{"query":"login error","limit":5}'
```

## Command Reference

### `webapi login`

Interactive setup for one or more servers.  Prompts for the server URL and
Bearer token, tests the connection, and stores credentials in
`~/.config/webapi-cli/config.json` (permissions `0600`).

```bash
webapi login                          # interactive
webapi login --server https://dev.example.com --token abc123 --profile dev
webapi login --profile staging        # re-authenticate an existing profile
```

Options:
- `--server, -s` — server base URL
- `--token, -t`  — Bearer token (omit to enter interactively; input is hidden)
- `--profile, -P` — profile name (default: `"default"`)

### `webapi discover`

Lists every WebAPI endpoint the server exposes as an MCP tool.  
Tool names are derived from URL path segments + HTTP method
(e.g. `GET /api/cowork/teams` → `cowork__teams__get`).

```bash
webapi discover                 # table format
webapi discover --raw | jq .    # machine-readable JSON
webapi discover -s https://dev.example.com   # one-off server override
```

Options:
- `--raw, -r` — output raw JSON
- `--refresh, -f` — bypass cache and re-fetch
- `--server, -s` — override server URL for this call

### `webapi describe <tool>`

Shows the full parameter schema for a tool — which arguments are required,
their types, and descriptions (all from the server's OpenAPI spec).

```bash
webapi describe ticket__ticket__post
webapi describe --raw ticket__ticket__post
```

### `webapi call <tool>`

Invokes any MCP tool.  Pass path/query parameters with `--params` and the
request body with `--body`.

```bash
# GET — query parameters only
webapi call ticket__search__post --params '{"query":"password reset"}'

# GET with path parameter
webapi call ticket__id__get --params '{"id":"12345"}'

# POST with body
webapi call ticket__id__post \
  --params '{"id":"12345"}' \
  --body '{"subject":"Hello","priority":2}'

# Raw output for scripting
webapi call --raw ticket__search__post --params '{"query":"bug"}' | jq '.body[0].subject'
```

Options:
- `--params, -p` — JSON object for query/path parameters
- `--body, -b` — JSON object or string for the request body
- `--raw, -r` — output raw JSON (no formatting)
- `--server, -s` — override server URL for this call

### `webapi profiles`

Manage multiple server profiles (e.g. dev, staging, production).

```bash
webapi profiles            # list all profiles
webapi profiles use prod   # switch active profile
webapi profiles remove dev # delete a profile
```

### `webapi logout`

Destroys the remote MCP session and clears the stored Bearer token for the
active profile.

```bash
webapi logout
```

### `webapi whoami`

Shows the current profile, server URL, application name, and version.

```bash
webapi whoami
```

## Tool Naming Convention

Tools follow the pattern `path__segments__http_method`:

| REST endpoint | Tool name |
|---|---|
| `GET /api/cowork/teams` | `cowork__teams__get` |
| `GET /api/cowork/teams/{team}/channels` | `cowork__teams__team__channels__get` |
| `POST /api/ticket/search` | `ticket__search__post` |
| `DELETE /api/cowork/teams/{team}/channels/{channel}/messages/{message}` | `cowork__teams__team__channels__channel__messages__message__delete` |

Path parameter tokens like `{id}` are stripped of braces and special
characters.  Always run `webapi discover` or `webapi describe` first —
names are generated deterministically from the server's OpenAPI spec and may
vary between versions.

## Working with Multiple Servers

```bash
# Add profiles
webapi login --server https://dev-helpdesk.example.com  --token <tok1> --profile dev
webapi login --server https://helpdesk.example.com       --token <tok2> --profile prod

# Switch
webapi profiles use dev

# Run a one-off command against a different server
webapi discover -s https://staging.example.com

# Check which profile is active
webapi whoami
```

## AI Agent Integration

If you use AI coding assistants (opencode, Claude Code, Cursor, Copilot,
etc.), point them to [skill.md](skill.md) for instructions on integrating
the WebAPI CLI into their tool set.

## Shell Completion

```bash
webapi --install-completion     # install for your current shell
webapi --show-completion        # preview the completion script
```

After installing, `<Tab>` auto-completes tool names by querying the server.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `No profile configured` | Run `webapi login` first |
| `HTTP 401` / `Unauthorized` | Your Bearer token may have expired. Run `webapi login` to update it. |
| `Tool not found` | Run `webapi discover` — tool names might differ between server versions |
| `Connection failed` | Check the server URL is correct and reachable. Verify the `/mcp` endpoint exists (HelpDesk 26.10+). |
| Need to debug raw responses | Use `--raw` to see the full JSON response |

## Updating

```bash
uv tool upgrade webapi-cli
```

## Uninstalling

```bash
uv tool uninstall webapi-cli
```

## For Developers

See `skill.md` for AI agent integration instructions.  The `tests/` directory
contains unit tests runnable with `pytest`.  The server-side code lives in
`WebAPICore/src/com/inet/plugin/webapi/server/WebAPICoreMCPServlet.java`.
