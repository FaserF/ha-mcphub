"""Buttons for MCPHub integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .client import MCPHubClient
from .const import (
    DATA_CLIENT,
    DATA_COORDINATOR,
    DEFAULT_MANUFACTURER,
    DEFAULT_MODEL,
    DEFAULT_NAME,
    DOMAIN,
)
from .coordinator import MCPHubCoordinator


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

    # Add reload buttons for each server
    for server in coordinator.data.get("servers", []):
        entities.append(
            MCPHubReloadServerButton(coordinator, client, entry, server.get("name", ""))
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
            name="Reload Server",
            icon="mdi:restart",
        )
        self._attr_unique_id = f"{entry.entry_id}_reload_{server_name}"
        self._attr_has_entity_name = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_{server_name}")},
            "via_device": (DOMAIN, entry.entry_id),
            "name": f"MCP {server_name.capitalize()}",
            "manufacturer": DEFAULT_MANUFACTURER,
            "model": f"MCP Server ({server_name})",
        }

    async def async_press(self) -> None:
        """Reload the server and refresh coordinator."""
        await self._client.async_reload_server(self._server_name)
        await self.coordinator.async_request_refresh()
