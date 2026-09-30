"""MCP JSON-RPC HTTP client for communicating with a Web API MCP servlet."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import time
from pathlib import Path
from typing import Any

import httpx

MCP_PATH = "/mcp"
JSON_RPC_VERSION = "2.0"
MCP_SESSION_HEADER = "Mcp-Session-Id"
MCP_PROTOCOL_VERSION = "2025-03-26"

# File-based cache TTL in seconds (5 minutes)
CACHE_TTL = 300


def _cache_dir() -> Path:
    xdg = os.environ.get("XDG_CACHE_HOME", "")
    if xdg:
        return Path(xdg) / "webapi-cli"
    return Path.home() / ".cache" / "webapi-cli"


def _cache_path(server_url: str) -> Path:
    h = hashlib.sha256(server_url.encode()).hexdigest()[:16]
    return _cache_dir() / f"tools_{h}.json"


class McpError(Exception):
    """Error returned by the MCP server."""
    def __init__(self, code: int, message: str, data: Any = None) -> None:
        self.code = code
        self.data = data
        super().__init__(f"[{code}] {message}")


class SessionExpiredError(McpError):
    """The MCP session has expired and the client needs to re-initialize."""


class McpClient:
    """Low-level MCP JSON-RPC client over HTTP.

    Handles the full MCP lifecycle: initialize, tools/list, tools/call, and
    session teardown via DELETE.
    """

    def __init__(
        self,
        server_url: str,
        bearer_token: str | None = None,
        *,
        _transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Create a new MCP client.

        Args:
            server_url: Base URL of the server (e.g. ``https://server.example.com``).
            bearer_token: Optional Bearer token for authentication.
        """
        self.base_url = server_url.rstrip("/")
        self._mcp_url = f"{self.base_url}{MCP_PATH}"
        self.bearer_token = bearer_token
        self._transport = _transport
        self.session_id: str | None = None
        self._request_id = 0
        self._tools_cache: list[dict[str, Any]] | None = None
        self._server_info: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Public MCP lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> dict[str, Any]:
        """Send an ``initialize`` request, create a session, and return server info.

        Returns:
            The ``result`` object from the initialize response, containing
            ``protocolVersion``, ``capabilities``, and ``serverInfo``.

        Raises:
            McpError: If the server rejects the request.
        """
        result = self._rpc("initialize", params={"protocolVersion": MCP_PROTOCOL_VERSION})
        self._server_info = result.get("serverInfo", {})
        return result

    def list_tools(self, refresh: bool = False) -> list[dict[str, Any]]:
        """List all available MCP tools.

        Results are cached in memory and on disk (TTL: 5 min).  Pass
        ``refresh=True`` to bypass both caches and force a fresh fetch.

        Args:
            refresh: If True, ignore the cache and re-fetch.

        Returns:
            A list of tool definition dicts (name, description, inputSchema).
        """
        # Check in-memory cache first
        if self._tools_cache is not None and not refresh:
            return self._tools_cache

        # Check file cache (unless refresh or using mock transport)
        if not refresh and self._transport is None:
            cached = _load_cache(self.base_url)
            if cached is not None:
                self._tools_cache = cached
                return self._tools_cache

        # Fetch fresh
        result = self._rpc("tools/list")
        self._tools_cache = result.get("tools", [])
        if self._transport is None:
            _save_cache(self.base_url, self._tools_cache)
        return self._tools_cache

    def list_tools_cached(self) -> list[dict[str, Any]] | None:
        """Return tools from the on-disk cache (no network), or None if stale/missing."""
        return _load_cache(self.base_url)

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Invoke a named MCP tool.

        Args:
            name: Tool name as returned by ``list_tools()``.
            arguments: Tool arguments (path/query params from inputSchema).

        Returns:
            The ``result`` object from the tool call (contains ``content`` and
            ``structuredContent``).

        Raises:
            McpError: If the tool call fails.
        """
        params: dict[str, Any] = {"name": name, "arguments": arguments or {}}
        return self._rpc("tools/call", params=params)

    def close(self) -> None:
        """Destroy the current MCP session on the server (DELETE)."""
        if not self.session_id:
            return
        headers = self._build_headers()
        try:
            if self._transport is not None:
                with httpx.Client(transport=self._transport) as client:
                    client.delete(self._mcp_url, headers=headers, timeout=30)
            else:
                httpx.delete(self._mcp_url, headers=headers, timeout=30)
        except Exception:
            pass
        finally:
            self.session_id = None
            self._tools_cache = None
            self._server_info = None

    @property
    def server_info(self) -> dict[str, Any] | None:
        """Information returned by the server during ``initialize``."""
        return self._server_info

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.session_id:
            headers[MCP_SESSION_HEADER] = self.session_id
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        return headers

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a JSON-RPC request and return the ``result`` field.

        Raises McpError for JSON-RPC errors or HTTP failures.
        """
        self._request_id += 1
        payload: dict[str, Any] = {
            "jsonrpc": JSON_RPC_VERSION,
            "id": self._request_id,
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        try:
            if self._transport is not None:
                with httpx.Client(transport=self._transport) as client:
                    response = client.post(
                        self._mcp_url,
                        json=payload,
                        headers=self._build_headers(),
                        timeout=60,
                    )
            else:
                response = httpx.post(
                    self._mcp_url,
                    json=payload,
                    headers=self._build_headers(),
                    timeout=60,
                )
        except httpx.RequestError as exc:
            raise McpError(-1, f"HTTP request failed: {exc}") from exc

        # Capture session id from response header
        new_session = response.headers.get(MCP_SESSION_HEADER)
        if new_session:
            self.session_id = new_session

        if response.status_code >= 400:
            raise McpError(
                response.status_code,
                f"HTTP {response.status_code}",
                response.text[:800],
            )

        try:
            body = response.json()
        except Exception:
            raise McpError(-1, f"Invalid JSON response: {response.text[:500]}")

        return self._parse_rpc_response(body)

    def _parse_rpc_response(self, body: dict[str, Any]) -> dict[str, Any]:
        """Extract ``result`` from a JSON-RPC response, raising errors if needed."""
        if "error" in body:
            err = body["error"]
            code = err.get("code", -1)
            message = err.get("message", "Unknown error")
            data = err.get("data")
            raise McpError(code, message, data)

        if "result" not in body:
            raise McpError(-1, "JSON-RPC response missing 'result' field")

        return body["result"]


# ------------------------------------------------------------------
# File-based tool cache
# ------------------------------------------------------------------

def _load_cache(server_url: str) -> list[dict[str, Any]] | None:
    """Load tools from the on-disk cache if still fresh. Returns None if stale."""
    path = _cache_path(server_url)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if time.time() - data.get("cached_at", 0) > CACHE_TTL:
        return None
    return data.get("tools")


def _save_cache(server_url: str, tools: list[dict[str, Any]]) -> None:
    """Persist the tools list to the on-disk cache."""
    path = _cache_path(server_url)
    _cache_dir().mkdir(parents=True, exist_ok=True)
    payload = {"cached_at": time.time(), "tools": tools}
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.chmod(stat.S_IRUSR | stat.S_IWUSR)
    tmp.replace(path)
