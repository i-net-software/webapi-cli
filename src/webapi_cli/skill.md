# WebAPI CLI Skill for AI Agents

## Overview

The `webapi` CLI tool connects to i-net product servers from version 26.10 through the shared WebAPI Core MCP endpoint. It discovers the API operations and schemas available to your account, then lets you inspect and invoke them from the command line.

## Installation

Install from GitHub with `uv`:
```bash
uv tool install --from git+https://github.com/i-net-software/webapi-cli webapi-cli
```

From a local checkout, run `uv tool install .` in the repository root.

## Quick Start

1. **Log in** to your server:
   ```bash
   webapi login --server https://server.example.com
   ```

   Enter your access token when prompted.

2. **Discover available tools**:
   ```bash
   webapi discover
   ```

3. **Inspect a tool**:
   ```bash
   webapi describe <tool_name>
   ```

4. **Call a tool**:
   ```bash
   webapi call <tool_name> --params '{"param":"value"}'
   webapi call <tool_name> --body '{"field":"value"}'
   ```

## Command Reference

| Command | Purpose |
|---------|---------|
| `webapi login` | Interactive server authentication |
| `webapi logout` | Clear stored credentials |
| `webapi discover` | List all available WebAPI tools |
| `webapi describe <tool>` | Show tool description and parameter schema |
| `webapi call <tool>` | Invoke a WebAPI endpoint |
| `webapi profiles` | Manage server profiles (dev/staging/prod) |
| `webapi whoami` | Show current profile and server info |

## Common Usage Patterns

The tool names below are examples from the i-net CoWork and i-net HelpDesk Web APIs. Run `webapi discover` to see which tools your server provides.

### Read data (GET endpoints)
```bash
webapi call cowork__teams__get
webapi call ticket__ticket__get --params '{"id":"12345"}'
webapi call ticket__search__post --params '{"query":"login error","limit":10}'
```

### Create/update data (POST/PUT/PATCH endpoints)
```bash
webapi call cowork__teams__team__channels__channel__messages__post \
  --params '{"team":"myteam","channel":"general"}' \
  --body '{"text":"Hello world"}'
```

### Raw output for piping
```bash
webapi call --pretty-print ticket__search__post --params '{"query":"bug"}' | jq .
```

### Multiple servers
```bash
webapi login --server https://dev.example.com --token ... --profile dev
webapi login --server https://production.example.com --token ... --profile prod
webapi profiles use prod
webapi discover -s https://dev.example.com  # One-off server override
```

## Tool Naming Convention

Tools are named using the pattern `path__segments__http_method`:

- Path segments are joined with double underscores (`__`)
- Path parameters `{param}` are stripped of braces
- Non-alphanumeric characters are replaced with underscores
- The HTTP method (get/post/put/delete) is appended as the last segment

Examples:
- `GET /api/cowork/teams` → `cowork__teams__get`
- `POST /api/cowork/teams/{team}/channels/{channel}/messages` → `cowork__teams__team__channels__channel__messages__post`
- `DELETE /api/ticket/{id}` → `ticket__id__delete`

## Parameter Structure

Each tool's `inputSchema` defines:
- **Path parameters**: Named in the schema, passed via `--params`
- **Query parameters**: Named in the schema, passed via `--params`
- **Request body**: Passed via `--body` as a JSON value

Use `webapi describe <tool>` before calling to see the exact schema.

## Error Handling

- Run `webapi discover` first. Tool names may differ between server versions.
- If a call fails with HTTP 401/403, your Bearer token may have expired; run `webapi login` again
- Use `--pretty-print` to see the full server response for debugging
- Pipe errors to stderr for scripts: `webapi call ... 2>/dev/null`

## Cross-referencing

After discovering tools, you can compare tool names against the REST API docs
by mapping the convention: `cowork__teams__get` → `GET /api/cowork/teams`.
