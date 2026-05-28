"""Tests for webapi_cli.mcp_client."""

from __future__ import annotations

import json

import httpx
import pytest

from webapi_cli.mcp_client import McpClient, McpError, JSON_RPC_VERSION, MCP_SESSION_HEADER


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _json_response(data, status=200, headers=None):
    if headers is None:
        headers = {}
    return httpx.Response(status, json=data, headers=headers)


def _rpc_success(id_, result, session_id=None):
    headers = {}
    if session_id:
        headers[MCP_SESSION_HEADER] = session_id
    return _json_response({"jsonrpc": JSON_RPC_VERSION, "id": id_, "result": result}, headers=headers)


def _rpc_error(id_, code, message):
    return _json_response({"jsonrpc": JSON_RPC_VERSION, "id": id_, "error": {"code": code, "message": message}})


def _make_client(handler, token="tok"):
    """Create an McpClient with a mock transport that delegates to *handler*."""
    return McpClient("https://example.com", token, _transport=MockTransport(handler))


class MockTransport(httpx.BaseTransport):
    def __init__(self, handler):
        self._handler = handler

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return self._handler(request)


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

def test_initialize_stores_session_and_server_info():
    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        if body["method"] == "initialize":
            return _rpc_success(body["id"], {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "test", "title": "Test", "version": "1.0"},
            }, session_id="abc-123")
        return _rpc_error(body["id"], -32601, "unknown")

    client = _make_client(handle)
    result = client.initialize()
    assert result["serverInfo"]["title"] == "Test"
    assert client.session_id == "abc-123"
    assert client.server_info["title"] == "Test"


def test_list_tools_caches_and_returns_tools():
    tools = [{"name": "a__get", "description": "A GET tool"}]

    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        if body["method"] == "tools/list":
            return _rpc_success(body["id"], {"tools": tools})
        return _rpc_error(body["id"], -32601, "unknown")

    client = _make_client(handle)
    result = client.list_tools()
    assert len(result) == 1
    assert result[0]["name"] == "a__get"

    # Second call uses cache
    result2 = client.list_tools()
    assert result2 == result


def test_list_tools_refresh_bypasses_cache():
    counter = [0]

    def handle(request: httpx.Request) -> httpx.Response:
        counter[0] += 1
        body = json.loads(request.read())
        return _rpc_success(body["id"], {"tools": [{"name": f"t{counter[0]}"}]})

    client = _make_client(handle)
    r1 = client.list_tools()
    r2 = client.list_tools()
    assert r1 == r2  # cached
    r3 = client.list_tools(refresh=True)
    assert r3 != r1  # refreshed


def test_call_tool_sends_arguments():
    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        if body["method"] == "tools/call":
            assert body["params"]["name"] == "my__tool"
            assert body["params"]["arguments"] == {"x": "1", "body": {"text": "hi"}}
            return _rpc_success(body["id"], {
                "content": [{"type": "text", "text": "ok"}],
                "structuredContent": {"status": 200, "body": {"result": "done"}},
            })
        return _rpc_error(body["id"], -32601, "unknown")

    client = _make_client(handle)
    result = client.call_tool("my__tool", {"x": "1", "body": {"text": "hi"}})
    assert result["structuredContent"]["body"]["result"] == "done"


def test_rpc_error_raises_mcp_error():
    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        return _rpc_error(body["id"], -32000, "Something went wrong")

    client = _make_client(handle)
    with pytest.raises(McpError, match="Something went wrong"):
        client.initialize()


def test_http_error_raises_mcp_error():
    def handle(request: httpx.Request) -> httpx.Response:
        return _json_response({"error": "not authorized"}, status=401)

    client = _make_client(handle)
    with pytest.raises(McpError, match="HTTP 401"):
        client.initialize()


def test_close_clears_session():
    client = McpClient("https://example.com", "tok", _transport=MockTransport(
        lambda req: httpx.Response(204)
    ))
    client.session_id = "xyz"
    client._tools_cache = [{"name": "a"}]
    client._server_info = {"title": "X"}
    client.close()

    assert client.session_id is None
    assert client._tools_cache is None
    assert client._server_info is None


def test_bearer_token_in_headers():
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "Bearer my-token"
        body = json.loads(request.read())
        return _rpc_success(body["id"], {"ok": True})

    client = McpClient("https://example.com", "my-token", _transport=MockTransport(handle))
    client.initialize()


def test_session_id_stored_after_initialize():
    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        if body["method"] == "initialize":
            return _rpc_success(body["id"], {}, session_id="sess-1")
        if body["method"] == "tools/list":
            # Verify session header is sent on subsequent requests
            assert request.headers.get(MCP_SESSION_HEADER) == "sess-1"
            return _rpc_success(body["id"], {"tools": []})
        return _rpc_error(body["id"], -32601, "unknown")

    client = _make_client(handle)
    client.initialize()
    assert client.session_id == "sess-1"
    client.list_tools()


def test_empty_tools_list():
    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        return _rpc_success(body["id"], {"tools": []})

    client = _make_client(handle)
    assert client.list_tools() == []
