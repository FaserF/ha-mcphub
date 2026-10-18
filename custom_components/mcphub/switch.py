"""Switches for MCPHub integration with per-server control."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .client import MCPHubClient
from .const import (
    ATTR_SERVERS,
    CONF_AUTO_IMPORT_NEW,
    CONF_ENABLED_SERVERS,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DEFAULT_AUTO_IMPORT_NEW,
    DOMAIN,
)
from .coordinator import MCPHubCoordinator
from .helpers import get_server_device_info


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
    """Set up MCPHub switch platform."""
    coordinator: MCPHubCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    client: MCPHubClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]

    entities: list[SwitchEntity] = []

    for server in coordinator.data.get("servers", []):
        name = server.get("name", "")
        if not name or not _is_server_enabled(entry, name):
            continue
        entities.append(MCPHubServerEnableSwitch(coordinator, client, entry, name))

    async_add_entities(entities)


class MCPHubServerEnableSwitch(CoordinatorEntity[MCPHubCoordinator], SwitchEntity):
    """Switch to enable or disable an MCP server in MCPHub."""

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        client: MCPHubClient,
        entry: ConfigEntry,
        server_name: str,
    ) -> None:
        """Initialize the enable switch."""
        super().__init__(coordinator)
        self._client = client
        self._server_name = server_name
        self.entity_description = SwitchEntityDescription(
            key=f"enable_{server_name}",
            name="Enabled",
            icon="mdi:toggle-switch",
        )
        self._attr_unique_id = f"{entry.entry_id}_enable_{server_name}"
        self._attr_has_entity_name = True

        server_data = self._get_server_data() or {}
        self._attr_device_info = get_server_device_info(entry, server_name, server_data)

    def _get_server_data(self) -> dict[str, Any] | None:
        """Get the latest data for this server."""
        if not self.coordinator.data:
            return None
        for server in self.coordinator.data.get(ATTR_SERVERS, []):
            if server.get("name") == self._server_name:
                return server
        return None

    @property
    def is_on(self) -> bool:
        """Return True if the server is enabled."""
        data = self._get_server_data()
        return bool(data.get("enabled", True)) if data else False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the server."""
        if not self.is_on:
            await self._client.async_toggle_server(self._server_name)
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the server."""
        if self.is_on:
            await self._client.async_toggle_server(self._server_name)
            await self.coordinator.async_request_refresh()
