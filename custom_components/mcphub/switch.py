"""Switches for MCPHub integration."""

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
    DATA_CLIENT,
    DATA_COORDINATOR,
    DEFAULT_MANUFACTURER,
    DOMAIN,
)
from .coordinator import MCPHubCoordinator


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
        entities.append(
            MCPHubServerEnableSwitch(coordinator, client, entry, server.get("name", ""))
        )

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
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_{server_name}")},
            "via_device": (DOMAIN, entry.entry_id),
            "name": f"MCP {server_name.capitalize()}",
            "manufacturer": DEFAULT_MANUFACTURER,
            "model": f"MCP Server ({server_name})",
        }

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
