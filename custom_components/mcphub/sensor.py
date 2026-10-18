"""Sensors for MCPHub integration with intelligent dynamic tool mapping."""

from __future__ import annotations

import logging
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
    CONF_AUTO_IMPORT_NEW,
    CONF_ENABLED_SERVERS,
    DATA_COORDINATOR,
    DEFAULT_AUTO_IMPORT_NEW,
    DOMAIN,
)
from .coordinator import MCPHubCoordinator
from .helpers import get_gateway_device_info, get_server_device_info

_LOGGER = logging.getLogger(__name__)

GATEWAY_SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
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
    """Set up MCPHub sensor platform."""
    coordinator: MCPHubCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities: list[SensorEntity] = [
        MCPHubGatewaySensor(coordinator, entry, description)
        for description in GATEWAY_SENSOR_TYPES
    ]

    # Process all registered servers
    servers = coordinator.data.get("servers", [])
    for server in servers:
        name = server.get("name", "")
        if not name or not _is_server_enabled(entry, name):
            continue

        # Add the server's primary status & metadata sensor
        entities.append(MCPHubServerSensor(coordinator, entry, name))

        # Dynamically inspect tools and create sensors for zero-arg query/status tools
        tools = server.get("tools", [])
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            tool_name = tool.get("name", "")
            req_params = (tool.get("inputSchema") or {}).get("required", [])
            props = list((tool.get("inputSchema") or {}).get("properties", {}).keys())

            is_query = any(
                term in tool_name.lower()
                for term in (
                    "status",
                    "health",
                    "stats",
                    "overview",
                    "info",
                    "get_",
                    "list_",
                )
            )

            if (
                (not req_params or len(req_params) == 0)
                and (not props or len(props) == 0)
                and is_query
            ):
                entities.append(MCPHubDynamicToolSensor(coordinator, entry, name, tool))

    async_add_entities(entities)


class MCPHubGatewaySensor(CoordinatorEntity[MCPHubCoordinator], SensorEntity):
    """Representation of an MCPHub Gateway summary sensor."""

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the gateway sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_has_entity_name = True
        self._attr_device_info = get_gateway_device_info(entry)

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self.entity_description.key)


class MCPHubServerSensor(CoordinatorEntity[MCPHubCoordinator], SensorEntity):
    """Primary sensor for an MCP server device."""

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        entry: ConfigEntry,
        server_name: str,
    ) -> None:
        """Initialize the server status sensor."""
        super().__init__(coordinator)
        self._server_name = server_name
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_server_{server_name}"
        self._attr_has_entity_name = True
        self._attr_name = "Connection Status"
        self._attr_icon = "mdi:server-network-outline"

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
    def native_value(self) -> str | None:
        """Return the current status of the server."""
        data = self._get_server_data()
        return data.get("status") if data else "unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed attributes for this server."""
        data = self._get_server_data() or {}
        tools = data.get("tools", [])
        cfg = data.get("config") or {}
        return {
            "version": data.get("version"),
            "enabled": data.get("enabled", True),
            "tool_count": len(tools) if isinstance(tools, list) else 0,
            "transport_type": cfg.get("type", "unknown"),
            "description": cfg.get("description"),
            "command": cfg.get("command"),
            "error": data.get("error"),
        }


class MCPHubDynamicToolSensor(CoordinatorEntity[MCPHubCoordinator], SensorEntity):
    """Dynamic sensor reflecting zero-argument query tool status."""

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        entry: ConfigEntry,
        server_name: str,
        tool: dict[str, Any],
    ) -> None:
        """Initialize the dynamic tool sensor."""
        super().__init__(coordinator)
        self._server_name = server_name
        self._tool = tool
        raw_name = tool.get("name", "")
        short_name = (
            raw_name.split("-")[-1]
            .replace(f"{server_name}_", "")
            .replace("_", " ")
            .title()
        )

        self._attr_unique_id = f"{entry.entry_id}_{server_name}_dyn_{raw_name}"
        self._attr_has_entity_name = True
        self._attr_name = short_name
        self._attr_icon = "mdi:information-outline"

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
    def native_value(self) -> str:
        """Return available if server is connected."""
        if not self.coordinator.data:
            return "unknown"
        for server in self.coordinator.data.get(ATTR_SERVERS, []):
            if server.get("name") == self._server_name:
                return "Ready" if server.get("status") == "connected" else "Offline"
        return "Offline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return tool documentation and schema."""
        return {
            "tool_name": self._tool.get("name"),
            "description": self._tool.get("description"),
            "required_parameters": (self._tool.get("inputSchema") or {}).get(
                "required", []
            ),
        }
