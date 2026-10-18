"""Tests for the MCPHub client."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.mcphub.client import (
    InvalidAuth,
    MCPHubClient,
)


@pytest.mark.asyncio
async def test_client_get_servers_success() -> None:
    """Test successful retrieval of servers."""
    client = MCPHubClient("http://mcphub:3000", api_key="secret")

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(
        return_value={
            "servers": [{"name": "finance", "status": "connected", "tools": ["t1"]}]
        }
    )

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_resp
    client._session = mock_session

    servers = await client.async_get_servers()
    assert len(servers) == 1
    assert servers[0]["name"] == "finance"


@pytest.mark.asyncio
async def test_client_get_servers_auth_error() -> None:
    """Test 401 raises InvalidAuth."""
    client = MCPHubClient("http://mcphub:3000", api_key="wrong_key")

    mock_resp = AsyncMock()
    mock_resp.status = 401

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_resp
    client._session = mock_session

    with pytest.raises(InvalidAuth):
        await client.async_get_servers()


@pytest.mark.asyncio
async def test_client_get_status_overview() -> None:
    """Test get_status_overview calculation."""
    client = MCPHubClient("http://mcphub:3000", api_key="secret")
    client.async_get_servers = AsyncMock(
        return_value=[
            {"name": "finance", "status": "connected", "tools": ["t1", "t2"]},
            {"name": "steam", "status": "disconnected", "tools": []},
        ]
    )

    overview = await client.async_get_status_overview()
    assert overview["total_servers"] == 2
    assert overview["connected_servers"] == 1
    assert overview["total_tools"] == 2
    assert "latency_ms" in overview


@pytest.mark.asyncio
async def test_client_call_tool_flow() -> None:
    """Test full MCP tool call handshake and execution."""
    client = MCPHubClient("http://mcphub:3000", api_key="secret")

    # Mock init response
    init_resp = AsyncMock()
    init_resp.status = 200
    init_resp.headers = {"Mcp-Session-Id": "sess_12345"}
    init_resp.text = AsyncMock(return_value='data: {"result": {}}\n\n')

    # Mock call response
    call_resp = AsyncMock()
    call_resp.status = 200
    call_resp.text = AsyncMock(
        return_value='data: {"result": {"content": [{"type": "text", "text": "OK"}]}}\n\n'
    )

    mock_session = MagicMock()
    # First post is init, second is call
    mock_session.post.return_value.__aenter__.side_effect = [init_resp, call_resp]
    client._session = mock_session

    res = await client.async_call_tool(
        "finance", "finance-finance_get_quote", {"symbol": "AAPL"}
    )
    assert "content" in res
    assert res["content"][0]["text"] == "OK"


@pytest.mark.asyncio
async def test_client_toggle_and_reload() -> None:
    """Test toggle and reload endpoints."""
    client = MCPHubClient("http://mcphub:3000", api_key="secret")

    resp_ok = AsyncMock()
    resp_ok.status = 200

    mock_session = MagicMock()
    mock_session.post.return_value.__aenter__.return_value = resp_ok
    client._session = mock_session

    assert await client.async_toggle_server("finance") is True
    assert await client.async_reload_server("finance") is True
    assert await client.async_clear_cache() is True
