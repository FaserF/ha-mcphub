"""Sensors for MCPHub integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_CONNECTED_SERVERS,
    ATTR_LATENCY_MS,
    ATTR_SERVERS,
    ATTR_TOTAL_SERVERS,
    ATTR_TOTAL_TOOLS,
    DATA_COORDINATOR,
    DEFAULT_MANUFACTURER,
    DEFAULT_MODEL,
    DEFAULT_NAME,
    DOMAIN,
)
from .coordinator import MCPHubCoordinator

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=ATTR_CONNECTED_SERVERS,
        name="Connected Servers",
        icon="mdi:server-network",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_TOTAL_SERVERS,
        name="Total Servers",
        icon="mdi:server",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_TOTAL_TOOLS,
        name="Total Tools",
        icon="mdi:tools",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_LATENCY_MS,
        name="Gateway Latency",
        icon="mdi:timer-outline",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MCPHub sensor platform."""
    coordinator: MCPHubCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities: list[SensorEntity] = [
        MCPHubGatewaySensor(coordinator, entry, description)
        for description in SENSOR_TYPES
    ]

    # Add individual server status sensors
    servers = coordinator.data.get("servers", [])
    for server in servers:
        entities.append(MCPHubServerSensor(coordinator, entry, server.get("name", "")))

    async_add_entities(entities)


class MCPHubGatewaySensor(CoordinatorEntity[MCPHubCoordinator], SensorEntity):
    """Representation of an MCPHub Gateway summary sensor."""

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_has_entity_name = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": DEFAULT_NAME,
            "manufacturer": DEFAULT_MANUFACTURER,
            "model": DEFAULT_MODEL,
        }

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self.entity_description.key)


class MCPHubServerSensor(CoordinatorEntity[MCPHubCoordinator], SensorEntity):
    """Representation of an individual MCP server status & tools sensor."""

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        entry: ConfigEntry,
        server_name: str,
    ) -> None:
        """Initialize the server sensor."""
        super().__init__(coordinator)
        self._server_name = server_name
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_server_{server_name}"
        self._attr_has_entity_name = True
        self._attr_name = f"Server {server_name}"
        self._attr_icon = "mdi:server-network-outline"
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
    def native_value(self) -> str | None:
        """Return the current status of the server."""
        data = self._get_server_data()
        return data.get("status") if data else "unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed attributes for this server."""
        data = self._get_server_data() or {}
        tools = data.get("tools", [])
        return {
            "version": data.get("version"),
            "enabled": data.get("enabled", True),
            "tool_count": len(tools) if isinstance(tools, list) else 0,
            "transport_type": (data.get("config") or {}).get("type", "unknown"),
            "description": (data.get("config") or {}).get("description"),
            "error": data.get("error"),
        }
