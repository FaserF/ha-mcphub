"""Custom services for MCPHub integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError

from .client import MCPHubClient
from .const import (
    ATTR_IS_ERROR,
    ATTR_RESULT,
    CONF_DEFAULT_GROUP,
    DATA_CLIENT,
    DEFAULT_DEFAULT_GROUP,
    DOMAIN,
    SERVICE_CALL_TOOL,
    SERVICE_CLEAR_CACHE,
    SERVICE_DISCOVER_TOOLS,
    SERVICE_RELOAD_SERVER,
    SERVICE_TOGGLE_SERVER,
)

_LOGGER = logging.getLogger(__name__)

CALL_TOOL_SCHEMA = vol.Schema(
    {
        vol.Required("tool_name"): str,
        vol.Optional("server"): str,
        vol.Optional("arguments", default={}): dict,
    }
)

SERVER_SCHEMA = vol.Schema(
    {
        vol.Required("server_name"): str,
    }
)

DISCOVER_TOOLS_SCHEMA = vol.Schema(
    {
        vol.Optional("server_or_group"): str,
    }
)


def _get_client_and_entry(hass: HomeAssistant) -> tuple[MCPHubClient, Any]:
    """Get the first active client and config entry from hass data."""
    domain_data = hass.data.get(DOMAIN, {})
    for entry_id, entry_data in domain_data.items():
        if DATA_CLIENT in entry_data:
            entry = hass.config_entries.async_get_entry(entry_id)
            return entry_data[DATA_CLIENT], entry
    raise HomeAssistantError("No active MCPHub integration instance found")


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register custom MCPHub services."""

    async def handle_call_tool(call: ServiceCall) -> dict[str, Any]:
        """Execute a tool via MCPHub."""
        client, entry = _get_client_and_entry(hass)
        tool_name: str = call.data["tool_name"]
        arguments: dict[str, Any] = call.data.get("arguments", {})

        # Default to configured default_group (e.g. $smart) if server not specified
        default_group = (
            entry.options.get(
                CONF_DEFAULT_GROUP,
                entry.data.get(CONF_DEFAULT_GROUP, DEFAULT_DEFAULT_GROUP),
            )
            if entry
            else DEFAULT_DEFAULT_GROUP
        )

        server_target = call.data.get("server") or default_group

        try:
            res = await client.async_call_tool(server_target, tool_name, arguments)
            return {
                ATTR_RESULT: res,
                ATTR_IS_ERROR: False,
            }
        except Exception as exc:
            _LOGGER.error(
                "Failed to execute tool %s on %s: %s", tool_name, server_target, exc
            )
            return {
                ATTR_RESULT: str(exc),
                ATTR_IS_ERROR: True,
            }

    async def handle_reload_server(call: ServiceCall) -> None:
        """Reload an MCP server."""
        client, _ = _get_client_and_entry(hass)
        server_name: str = call.data["server_name"]
        await client.async_reload_server(server_name)

    async def handle_toggle_server(call: ServiceCall) -> None:
        """Toggle an MCP server on/off."""
        client, _ = _get_client_and_entry(hass)
        server_name: str = call.data["server_name"]
        await client.async_toggle_server(server_name)

    async def handle_clear_cache(call: ServiceCall) -> None:
        """Clear MCPHub tool cache."""
        client, _ = _get_client_and_entry(hass)
        await client.async_clear_cache()

    async def handle_discover_tools(call: ServiceCall) -> dict[str, Any]:
        """Discover tools exposed by a server or group."""
        client, entry = _get_client_and_entry(hass)
        target = call.data.get("server_or_group")
        if not target:
            target = (
                entry.options.get(
                    CONF_DEFAULT_GROUP,
                    entry.data.get(CONF_DEFAULT_GROUP, DEFAULT_DEFAULT_GROUP),
                )
                if entry
                else DEFAULT_DEFAULT_GROUP
            )

        tools = await client.async_list_tools(target)
        return {"tools": tools, "count": len(tools)}

    if not hass.services.has_service(DOMAIN, SERVICE_CALL_TOOL):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CALL_TOOL,
            handle_call_tool,
            schema=CALL_TOOL_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_RELOAD_SERVER):
        hass.services.async_register(
            DOMAIN,
            SERVICE_RELOAD_SERVER,
            handle_reload_server,
            schema=SERVER_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_TOGGLE_SERVER):
        hass.services.async_register(
            DOMAIN,
            SERVICE_TOGGLE_SERVER,
            handle_toggle_server,
            schema=SERVER_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_CLEAR_CACHE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CLEAR_CACHE,
            handle_clear_cache,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_DISCOVER_TOOLS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_DISCOVER_TOOLS,
            handle_discover_tools,
            schema=DISCOVER_TOOLS_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unregister MCPHub services when last entry is unloaded."""
    if DOMAIN not in hass.data or not hass.data[DOMAIN]:
        for service in (
            SERVICE_CALL_TOOL,
            SERVICE_RELOAD_SERVER,
            SERVICE_TOGGLE_SERVER,
            SERVICE_CLEAR_CACHE,
            SERVICE_DISCOVER_TOOLS,
        ):
            if hass.services.has_service(DOMAIN, service):
                hass.services.async_remove(DOMAIN, service)
