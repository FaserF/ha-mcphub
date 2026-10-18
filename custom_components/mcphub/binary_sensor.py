"""Binary sensors for MCPHub integration with intelligent device grouping."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_SERVERS,
    CONF_AUTO_IMPORT_NEW,
    CONF_ENABLED_SERVERS,
    DATA_COORDINATOR,
    DEFAULT_AUTO_IMPORT_NEW,
    DEFAULT_MANUFACTURER,
    DEFAULT_MODEL,
    DEFAULT_NAME,
    DOMAIN,
    SERVER_VISIT_URLS,
)
from .coordinator import MCPHubCoordinator


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
    """Set up MCPHub binary sensor platform."""
    coordinator: MCPHubCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities: list[BinarySensorEntity] = [
        MCPHubGatewayConnectivitySensor(coordinator, entry)
    ]

    # Add server online binary sensor under each server's device entity
    for server in coordinator.data.get("servers", []):
        name = server.get("name", "")
        if not name or not _is_server_enabled(entry, name):
            continue
        entities.append(MCPHubServerConnectivitySensor(coordinator, entry, name))

    async_add_entities(entities)


class MCPHubGatewayConnectivitySensor(
    CoordinatorEntity[MCPHubCoordinator], BinarySensorEntity
):
    """Binary sensor for MCPHub Gateway overall connectivity."""

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = BinarySensorEntityDescription(
            key="connectivity",
            name="Gateway Connected",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
        )
        self._attr_unique_id = f"{entry.entry_id}_connectivity"
        self._attr_has_entity_name = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": DEFAULT_NAME,
            "manufacturer": DEFAULT_MANUFACTURER,
            "model": DEFAULT_MODEL,
            "configuration_url": entry.data.get("api_url"),
        }

    @property
    def is_on(self) -> bool:
        """Return True if coordinator successfully got data."""
        return self.coordinator.last_update_success and bool(self.coordinator.data)


class MCPHubServerConnectivitySensor(
    CoordinatorEntity[MCPHubCoordinator], BinarySensorEntity
):
    """Binary sensor indicating whether an individual MCP server is connected."""

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        entry: ConfigEntry,
        server_name: str,
    ) -> None:
        """Initialize the server connectivity sensor."""
        super().__init__(coordinator)
        self._server_name = server_name
        self.entity_description = BinarySensorEntityDescription(
            key=f"connected_{server_name}",
            name="Online",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
        )
        self._attr_unique_id = f"{entry.entry_id}_server_online_{server_name}"
        self._attr_has_entity_name = True

        server_data = self._get_server_data() or {}
        cfg = server_data.get("config") or {}
        vis_url = SERVER_VISIT_URLS.get(server_name) or cfg.get("url")

        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_{server_name}")},
            "via_device": (DOMAIN, entry.entry_id),
            "name": f"MCP {server_name.replace('-', ' ').title()}",
            "manufacturer": "MCP Server Ecosystem",
            "model": f"MCP {cfg.get('type', 'stdio').upper()} Service",
            "sw_version": server_data.get("version", "1.0.0"),
            "configuration_url": vis_url,
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
        """Return True if the server is connected."""
        data = self._get_server_data()
        return bool(data and data.get("status") == "connected")
