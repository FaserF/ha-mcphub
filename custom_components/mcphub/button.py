"""Buttons for MCPHub integration with dynamic executable actions."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .client import MCPHubClient
from .const import (
    CONF_AUTO_IMPORT_NEW,
    CONF_ENABLED_SERVERS,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DEFAULT_AUTO_IMPORT_NEW,
    DEFAULT_MANUFACTURER,
    DEFAULT_MODEL,
    DEFAULT_NAME,
    DOMAIN,
    SERVER_VISIT_URLS,
)
from .coordinator import MCPHubCoordinator

_LOGGER = logging.getLogger(__name__)


def _is_server_enabled(entry: ConfigEntry, server_name: str) -> bool:
    """Check if server is enabled by user configuration."""
    auto_import = entry.options.get(
        CONF_AUTO_IMPORT_NEW,
        entry.data.get(CONF_AUTO_IMPORT_NEW, DEFAULT_AUTO_IMPORT_NEW),
    )
    enabled_servers = entry.options.get(
        CONF_ENABLED_SERVERS,
        entry.data.get(CONF_ENABLED_SERVERS),
    )
    if enabled_servers is None:
        return True
    if server_name in enabled_servers:
        return True
    return auto_import and (server_name not in enabled_servers)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MCPHub buttons."""
    coordinator: MCPHubCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    client: MCPHubClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]

    entities: list[ButtonEntity] = [
        MCPHubClearCacheButton(coordinator, client, entry),
        MCPHubRefreshButton(coordinator, entry),
    ]

    # Add reload and action buttons for each enabled server device
    for server in coordinator.data.get("servers", []):
        name = server.get("name", "")
        if not name or not _is_server_enabled(entry, name):
            continue

        entities.append(MCPHubReloadServerButton(coordinator, client, entry, name))

        # Dynamic tool execution buttons for zero-required-argument action tools
        tools = server.get("tools", [])
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            tool_name = tool.get("name", "")
            req_params = (tool.get("inputSchema") or {}).get("required", [])

            is_action = any(
                act in tool_name.lower()
                for act in (
                    "clear",
                    "flush",
                    "reboot",
                    "restart",
                    "start",
                    "wake",
                    "sync",
                    "run",
                )
            )

            # If it's an action tool and requires zero arguments, add it as a native Button
            if (not req_params or len(req_params) == 0) and is_action:
                entities.append(
                    MCPHubDynamicToolButton(coordinator, client, entry, name, tool)
                )

    async_add_entities(entities)


class MCPHubClearCacheButton(CoordinatorEntity[MCPHubCoordinator], ButtonEntity):
    """Button to clear MCPHub tool and schema cache."""

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        client: MCPHubClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._client = client
        self.entity_description = ButtonEntityDescription(
            key="clear_cache",
            name="Clear Cache",
            icon="mdi:cached",
        )
        self._attr_unique_id = f"{entry.entry_id}_clear_cache"
        self._attr_has_entity_name = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": DEFAULT_NAME,
            "manufacturer": DEFAULT_MANUFACTURER,
            "model": DEFAULT_MODEL,
            "configuration_url": entry.data.get("api_url"),
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        await self._client.async_clear_cache()
        await self.coordinator.async_request_refresh()


class MCPHubRefreshButton(CoordinatorEntity[MCPHubCoordinator], ButtonEntity):
    """Button to trigger manual status refresh."""

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the refresh button."""
        super().__init__(coordinator)
        self.entity_description = ButtonEntityDescription(
            key="refresh_status",
            name="Refresh Status",
            icon="mdi:refresh",
        )
        self._attr_unique_id = f"{entry.entry_id}_refresh_status"
        self._attr_has_entity_name = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": DEFAULT_NAME,
            "manufacturer": DEFAULT_MANUFACTURER,
            "model": DEFAULT_MODEL,
            "configuration_url": entry.data.get("api_url"),
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_request_refresh()


class MCPHubReloadServerButton(CoordinatorEntity[MCPHubCoordinator], ButtonEntity):
    """Button to reload a specific MCP server."""

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        client: MCPHubClient,
        entry: ConfigEntry,
        server_name: str,
    ) -> None:
        """Initialize the reload button."""
        super().__init__(coordinator)
        self._client = client
        self._server_name = server_name
        self.entity_description = ButtonEntityDescription(
            key=f"reload_{server_name}",
            name="Restart & Reload",
            icon="mdi:restart",
        )
        self._attr_unique_id = f"{entry.entry_id}_reload_{server_name}"
        self._attr_has_entity_name = True

        vis_url = SERVER_VISIT_URLS.get(server_name)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_{server_name}")},
            "via_device": (DOMAIN, entry.entry_id),
            "name": f"MCP {server_name.replace('-', ' ').title()}",
            "manufacturer": "MCP Server Ecosystem",
            "configuration_url": vis_url,
        }

    async def async_press(self) -> None:
        """Reload the server and refresh coordinator."""
        await self._client.async_reload_server(self._server_name)
        await self.coordinator.async_request_refresh()


class MCPHubDynamicToolButton(CoordinatorEntity[MCPHubCoordinator], ButtonEntity):
    """Dynamic button to execute a zero-argument action tool on this MCP server."""

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        client: MCPHubClient,
        entry: ConfigEntry,
        server_name: str,
        tool: dict[str, Any],
    ) -> None:
        """Initialize dynamic action button."""
        super().__init__(coordinator)
        self._client = client
        self._server_name = server_name
        self._tool = tool
        raw_name = tool.get("name", "")
        short_name = (
            raw_name.split("-")[-1]
            .replace(f"{server_name}_", "")
            .replace("_", " ")
            .title()
        )

        self.entity_description = ButtonEntityDescription(
            key=f"dyn_btn_{raw_name}",
            name=short_name,
            icon="mdi:play-circle-outline",
        )
        self._attr_unique_id = f"{entry.entry_id}_{server_name}_btn_{raw_name}"
        self._attr_has_entity_name = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_{server_name}")},
            "via_device": (DOMAIN, entry.entry_id),
            "name": f"MCP {server_name.replace('-', ' ').title()}",
            "manufacturer": "MCP Server Ecosystem",
        }

    async def async_press(self) -> None:
        """Execute the tool."""
        tool_name = self._tool.get("name", "")
        _LOGGER.info(
            "Executing MCP tool %s on %s via button", tool_name, self._server_name
        )
        await self._client.async_call_tool(self._server_name, tool_name, {})
        await self.coordinator.async_request_refresh()
