"""API Client for MCPHub Gateway & Server Manager."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import aiohttp
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)


class MCPHubError(HomeAssistantError):
    """Base exception for MCPHub errors."""


class CannotConnect(MCPHubError):
    """Exception to indicate connection error."""


class InvalidAuth(MCPHubError):
    """Exception to indicate invalid authentication."""


class ToolExecutionError(MCPHubError):
    """Exception to indicate error during tool execution."""


class MCPHubClient:
    """Client for interacting with MCPHub REST and Streamable HTTP MCP endpoints."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        session: aiohttp.ClientSession | None = None,
        timeout: int = 25,
    ) -> None:
        """Initialize the MCPHub client."""
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key.strip() if api_key else None
        self._session = session
        self._own_session = False
        self._timeout = timeout
        self._active_sessions: dict[str, str] = {}  # group/server -> sessionId

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp ClientSession."""
        if self._session is None or getattr(self._session, "closed", False) is True:
            self._session = aiohttp.ClientSession()
            self._own_session = True
        return self._session

    def _get_headers(self, additional: dict[str, str] | None = None) -> dict[str, str]:
        """Construct common HTTP request headers."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "HomeAssistant-MCPHub-Integration/0.1.0",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        if additional:
            headers.update(additional)
        return headers

    async def close(self) -> None:
        """Close the client session if owned."""
        if self._own_session and self._session and not self._session.closed:
            await self._session.close()

    async def async_get_servers(self) -> list[dict[str, Any]]:
        """Fetch all registered servers from /api/servers."""
        session = await self._get_session()
        url = f"{self._base_url}/api/servers"
        headers = self._get_headers()

        try:
            async with asyncio.timeout(self._timeout):
                async with session.get(url, headers=headers) as resp:
                    if resp.status in (401, 403):
                        raise InvalidAuth("Invalid Bearer API key for MCPHub")
                    if resp.status != 200:
                        text = await resp.text()
                        raise CannotConnect(
                            f"HTTP {resp.status} checking MCPHub servers: {text[:200]}"
                        )
                    data = await resp.json()
                    if isinstance(data, dict):
                        if "servers" in data:
                            return data["servers"]
                        payload = data.get("data")
                        if isinstance(payload, list):
                            return payload
                        if isinstance(payload, dict) and "servers" in payload:
                            return payload["servers"]
                    if isinstance(data, list):
                        return data
                    return []
        except TimeoutError as err:
            raise CannotConnect(f"Timeout connecting to MCPHub at {url}") from err
        except aiohttp.ClientError as err:
            raise CannotConnect(
                f"ClientError connecting to MCPHub at {url}: {err}"
            ) from err

    async def async_get_status_overview(self) -> dict[str, Any]:
        """Fetch server list and calculate aggregate statistics with latency."""
        start = time.monotonic()
        servers = await self.async_get_servers()
        latency = round((time.monotonic() - start) * 1000, 2)

        connected = [s for s in servers if s.get("status") == "connected"]
        total_tools = sum(
            len(s.get("tools", [])) for s in servers if isinstance(s.get("tools"), list)
        )

        return {
            "latency_ms": latency,
            "total_servers": len(servers),
            "connected_servers": len(connected),
            "total_tools": total_tools,
            "servers": servers,
        }

    async def async_toggle_server(self, server_name: str) -> bool:
        """Toggle a server on/off via POST /api/servers/:name/toggle."""
        session = await self._get_session()
        url = f"{self._base_url}/api/servers/{server_name}/toggle"
        headers = self._get_headers()

        try:
            async with asyncio.timeout(self._timeout):
                async with session.post(url, headers=headers) as resp:
                    if resp.status in (401, 403):
                        raise InvalidAuth("Invalid authentication toggling server")
                    if resp.status not in (200, 204):
                        text = await resp.text()
                        raise CannotConnect(
                            f"HTTP {resp.status} toggling server {server_name}: {text}"
                        )
                    return True
        except TimeoutError as err:
            raise CannotConnect(f"Timeout toggling server {server_name}") from err
        except aiohttp.ClientError as err:
            raise CannotConnect(
                f"Client error toggling server {server_name}: {err}"
            ) from err

    async def async_reload_server(self, server_name: str) -> bool:
        """Reload a server via POST /api/servers/:name/reload."""
        session = await self._get_session()
        url = f"{self._base_url}/api/servers/{server_name}/reload"
        headers = self._get_headers()

        try:
            async with asyncio.timeout(self._timeout):
                async with session.post(url, headers=headers) as resp:
                    if resp.status in (401, 403):
                        raise InvalidAuth("Invalid authentication reloading server")
                    if resp.status not in (200, 204):
                        text = await resp.text()
                        raise CannotConnect(
                            f"HTTP {resp.status} reloading server {server_name}: {text}"
                        )
                    return True
        except TimeoutError as err:
            raise CannotConnect(f"Timeout reloading server {server_name}") from err
        except aiohttp.ClientError as err:
            raise CannotConnect(
                f"Client error reloading server {server_name}: {err}"
            ) from err

    async def async_clear_cache(self) -> bool:
        """Clear MCPHub tool & schema cache via POST /api/cache/clear."""
        session = await self._get_session()
        url = f"{self._base_url}/api/cache/clear"
        headers = self._get_headers()

        try:
            async with asyncio.timeout(self._timeout):
                async with session.post(url, headers=headers) as resp:
                    if resp.status in (401, 403):
                        raise InvalidAuth("Invalid authentication clearing cache")
                    return resp.status in (200, 204)
        except Exception as err:
            raise CannotConnect(f"Error clearing cache: {err}") from err

    async def _async_init_mcp_session(self, group_or_server: str) -> str:
        """Initialize an MCP Streamable HTTP session and return the session ID."""
        session = await self._get_session()
        url = f"{self._base_url}/mcp/{group_or_server}"
        headers = self._get_headers()

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ha-mcphub", "version": "0.1.0"},
            },
        }

        try:
            async with asyncio.timeout(self._timeout):
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status in (401, 403):
                        raise InvalidAuth("Unauthorized initializing MCP session")
                    if resp.status not in (200, 202):
                        text = await resp.text()
                        raise CannotConnect(
                            f"HTTP {resp.status} on MCP init: {text[:200]}"
                        )

                    raw_sess = resp.headers.get("Mcp-Session-Id")
                    if not raw_sess:
                        raise CannotConnect(
                            "No Mcp-Session-Id header returned from MCPHub"
                        )

                    sess_id = raw_sess.strip()
                    self._active_sessions[group_or_server] = sess_id
                    return sess_id
        except TimeoutError as err:
            raise CannotConnect(f"Timeout initializing MCP session at {url}") from err
        except aiohttp.ClientError as err:
            raise CannotConnect(f"ClientError initializing MCP session: {err}") from err

    async def async_call_tool(
        self,
        server_or_group: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a tool via the MCP streamable-http interface with session management."""
        session = await self._get_session()
        url = f"{self._base_url}/mcp/{server_or_group}"

        # Get or create active session
        session_id = self._active_sessions.get(server_or_group)
        if not session_id:
            session_id = await self._async_init_mcp_session(server_or_group)

        # Build payload
        payload = {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {},
            },
        }

        headers = self._get_headers({"Mcp-Session-Id": session_id})

        for attempt in range(2):
            try:
                async with asyncio.timeout(self._timeout):
                    async with session.post(url, headers=headers, json=payload) as resp:
                        if resp.status == 401:
                            raise InvalidAuth("Invalid authentication calling tool")

                        raw_text = await resp.text()

                        # Check for session expiration
                        if (
                            resp.status != 200
                            or "-32001" in raw_text
                            or "Session not found" in raw_text
                        ):
                            if attempt == 0:
                                _LOGGER.debug("MCP session expired, reinitializing...")
                                session_id = await self._async_init_mcp_session(
                                    server_or_group
                                )
                                headers = self._get_headers(
                                    {"Mcp-Session-Id": session_id}
                                )
                                continue
                            raise ToolExecutionError(
                                f"Session failed: {raw_text[:200]}"
                            )

                        # Parse SSE event format
                        parsed: dict[str, Any] | None = None
                        for line in raw_text.splitlines():
                            if line.startswith("data:"):
                                chunk = line[5:].strip()
                                if chunk and chunk != "[DONE]":
                                    try:
                                        parsed = json.loads(chunk)
                                        break
                                    except json.JSONDecodeError:
                                        continue

                        if parsed is None:
                            try:
                                parsed = json.loads(raw_text)
                            except json.JSONDecodeError as exc:
                                raise ToolExecutionError(
                                    f"Failed to parse tool response: {raw_text[:200]}"
                                ) from exc

                        if "error" in parsed:
                            err_data = parsed["error"]
                            msg = (
                                err_data.get("message", str(err_data))
                                if isinstance(err_data, dict)
                                else str(err_data)
                            )
                            raise ToolExecutionError(f"MCP tool error: {msg}")

                        result = parsed.get("result", parsed)
                        return (
                            result if isinstance(result, dict) else {"result": result}
                        )
            except TimeoutError as err:
                raise CannotConnect(f"Timeout calling tool {tool_name}") from err
            except aiohttp.ClientError as err:
                raise CannotConnect(
                    f"ClientError calling tool {tool_name}: {err}"
                ) from err

        raise ToolExecutionError(f"Failed to execute tool {tool_name} after retry")

    async def async_list_tools(self, server_or_group: str) -> list[dict[str, Any]]:
        """List tools available for a given server or group."""
        session = await self._get_session()
        url = f"{self._base_url}/mcp/{server_or_group}"

        session_id = self._active_sessions.get(server_or_group)
        if not session_id:
            session_id = await self._async_init_mcp_session(server_or_group)

        payload = {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000),
            "method": "tools/list",
            "params": {},
        }
        headers = self._get_headers({"Mcp-Session-Id": session_id})

        try:
            async with asyncio.timeout(self._timeout):
                async with session.post(url, headers=headers, json=payload) as resp:
                    raw_text = await resp.text()
                    parsed: dict[str, Any] | None = None
                    for line in raw_text.splitlines():
                        if line.startswith("data:"):
                            chunk = line[5:].strip()
                            if chunk and chunk != "[DONE]":
                                try:
                                    parsed = json.loads(chunk)
                                    break
                                except json.JSONDecodeError:
                                    continue
                    if parsed is None:
                        parsed = json.loads(raw_text)

                    res = parsed.get("result", {}) if isinstance(parsed, dict) else {}
                    return res.get("tools", [])
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug("Could not list tools for %s: %s", server_or_group, exc)
            return []
