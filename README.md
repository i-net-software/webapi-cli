# i-net WebAPI CLI

The `webapi` command-line client lets you discover and use API operations published by an i-net server. It connects to the server's Model Context Protocol endpoint at `/mcp` and reads the tools and schemas available to your account. Use it in a terminal, in scripts, or from an AI coding assistant.

## Product support

The WebAPI CLI is available for i-net product servers from version 26.10. It connects through the shared WebAPI Core MCP endpoint at `/mcp`. This includes i-net HelpDesk, i-net Clear Reports, i-net PDFC, i-net CoWork, and other i-net products that provide the endpoint. The server determines which tools are available. The list depends on the product, installed extensions, server version, MCP configuration, and your account permissions.

## What you need

- An i-net server that exposes the WebAPI Core MCP endpoint at `/mcp`.
- A Bearer access token with Web API access and permission to use the API contexts you need.
- `uv` to install and run the CLI. The project requires Python 3.10 or later.

The CLI appends `/mcp` to the server URL you enter. Include the server's context path in the URL when it has one.

## Install

Install `uv` if it is not already available on your system:

```bash
# macOS or Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows PowerShell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS with Homebrew
brew install uv

# Windows with winget
winget install --id=astral-sh.uv -e
```

Install the CLI from GitHub:

```bash
uv tool install --from git+https://github.com/i-net-software/webapi-cli webapi-cli
```

To use the CLI without a permanent installation, run each command with `uvx`. Connect to a server first:

```bash
uvx --from git+https://github.com/i-net-software/webapi-cli webapi login
uvx --from git+https://github.com/i-net-software/webapi-cli webapi discover
```

Check the installation:

```bash
webapi --help
```

## Connect to your server

Create an access token in your server's administration interface. Select the Web API access permission and the permissions for the API contexts you want to use. Available permissions depend on your account and the APIs installed on the server. Ask your server administrator if you need a token or additional permissions.

Run the interactive login command:

```bash
webapi login
```

Enter the server URL and access token when prompted. The token entry is hidden. The CLI checks the connection and saves a profile for later use.

You can provide the server URL and profile name in the command. The CLI still prompts for the token:

```bash
webapi login --server https://server.example.com --profile production
```

## Quick start

List the tools available to your account:

```bash
webapi discover
```

Choose a tool from the list, then inspect its parameters:

```bash
webapi describe TOOL_NAME
```

Replace `TOOL_NAME` with a name returned by `webapi discover`. Call the tool with the parameters shown by `webapi describe`:

```bash
webapi call TOOL_NAME --params '{"id":"123"}'
```

For an operation that requires a request body, pass it with `--body`:

```bash
webapi call TOOL_NAME --body '{"name":"Example"}'
```

A call runs with your account's Web API permissions. Some API operations can change server data, so review the tool description and parameters before calling it.

## Use the CLI

### Discover tools

`webapi discover` lists the tools exposed by the server. Tool definitions come from the server's Web API description, so the available tools can differ between products and server versions.

```bash
webapi discover
webapi discover --refresh
webapi discover --pretty-print | jq .
webapi discover --server https://server.example.com
```

### Inspect a tool

`webapi describe` shows a tool's description, required parameters, types, and input schema.

```bash
webapi describe TOOL_NAME
webapi describe --pretty-print TOOL_NAME
```

### Call a tool

Pass path and query parameters with `--params`. Pass a request body with `--body`.

```bash
# Parameters
webapi call TOOL_NAME --params '{"id":"123","limit":5}'

# Request body
webapi call TOOL_NAME --body '{"name":"Example"}'

# Parameters and request body
webapi call TOOL_NAME --params '{"id":"123"}' --body '{"name":"Example"}'

# JSON output for scripts
webapi call --pretty-print TOOL_NAME --params '{"id":"123"}' | jq .
```

Replace `TOOL_NAME` and the example parameters with values from your server's tool list and schema.

### Manage server profiles

Profiles let you save connections for development, test, and production servers.

```bash
# Add a profile
webapi login --server https://dev.example.com --profile dev
webapi login --server https://production.example.com --profile production

# List and switch profiles
webapi profiles
webapi profiles use production

# Use another server for one command
webapi discover --server https://test.example.com

# Show the current server and account
webapi whoami

# Remove a profile
webapi profiles remove dev
```

### Sign out

`webapi logout` ends the remote MCP session and removes the saved token for the active profile.

```bash
webapi logout
```

### Shell completion

Install or preview tab completion for your current shell:

```bash
webapi --install-completion
webapi --show-completion
```

Completion uses the tool list from the active server.

## Tool names

Tool names are generated from the API path and HTTP method. Path parameters become name segments without braces.

| Web API operation | Tool name |
|---|---|
| `GET /api/cowork/teams` | `cowork__teams__get` |
| `GET /api/cowork/teams/{team}/channels` | `cowork__teams__team__channels__get` |
| `POST /api/ticket/search` | `ticket__search__post` |

These examples come from different API contexts. The tool names available on your server may differ. Run `webapi discover` and use the exact name shown there.

## Scripting and development

The CLI reads tool definitions and schemas from the server at runtime. You can use the same commands interactively or in scripts without generating a product-specific client.

For machine-readable output, add `--pretty-print` and pipe the JSON to tools such as `jq`:

```bash
webapi discover --pretty-print | jq .
webapi describe --pretty-print TOOL_NAME | jq .
webapi call --pretty-print TOOL_NAME --params '{"id":"123"}' | jq .
```

The server applies its normal Web API authentication and permission checks to each operation. For details about an endpoint's behavior, parameters, and response fields, use the API documentation exposed by your server.

## AI agent integration

AI coding assistants can use the CLI to discover tools, inspect schemas, and call API operations. See [skill.md](skill.md) for setup instructions and examples.

## Configuration and credentials

The CLI stores server profiles and access tokens in `~/.config/webapi-cli/config.json`. Set `XDG_CONFIG_HOME` to use a different configuration directory. The CLI restricts file permissions where the operating system supports them.

Use a separate profile for each server environment. You can remove a saved token at any time with `webapi logout` or delete its profile with `webapi profiles remove`.

## Troubleshooting

| Problem | Solution |
|---|---|
| No profile is configured | Run `webapi login` and connect to a server. |
| Connection failed | Check the server URL and network access. Confirm that your product version exposes the `/mcp` endpoint. |
| HTTP 401 or 403 | Check that the token is valid and has Web API access and permission for the requested API context. |
| Tool not found | Run `webapi discover` and copy the exact tool name from the list. |
| Tool call failed | Run `webapi describe TOOL_NAME` to check required parameters and request body fields. |
| Need the complete response | Add `--pretty-print` to the command. |

## Update or uninstall

Upgrade the installed CLI:

```bash
uv tool upgrade webapi-cli
```

Remove it:

```bash
uv tool uninstall webapi-cli
```
