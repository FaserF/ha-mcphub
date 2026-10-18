"""Sensors for MCPHub integration with intelligent dynamic tool mapping and custom mapping support."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

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
from .custom_mapping import (
    DeviceMapping,
    EntityMapping,
    extract_device_info,
    get_nested_value,
    load_mappings_from_entry,
    render_template_str,
    sync_device_registry,
)
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

        entities.append(MCPHubServerSensor(coordinator, entry, name))

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

    # Process dynamically mapped sensors (e.g. Printer status, Uptime, Toner markers)
    tracked_sensors: set[str] = set()

    def _sync_mapped_sensors() -> None:
        mappings = load_mappings_from_entry(entry)
        sensor_mappings = [
            (m, e)
            for m in mappings
            if m.enabled
            for e in m.entities
            if e.platform == "sensor"
        ]
        if not sensor_mappings:
            return

        mapped_data = coordinator.data.get("mapped_data", {})
        new_sensors: list[SensorEntity] = []

        for mapping, entity_cfg in sensor_mappings:
            payload = mapped_data.get(mapping.id)
            devices_to_process: list[dict[str, Any]] = []

            if mapping.is_multi_device:
                devices_to_process = list(
                    get_nested_value(payload, mapping.devices_path, []) or []
                )
            elif isinstance(payload, dict):
                devices_to_process = [payload]

            for dev in devices_to_process:
                ident_val = str(
                    get_nested_value(dev, mapping.device_identifier_key, mapping.id)
                )
                clean_id = ident_val.replace(":", "_").replace(".", "_")
                sync_device_registry(hass, entry, mapping, dev)

                if entity_cfg.is_collection:
                    items = get_nested_value(dev, entity_cfg.collection_path, []) or []
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        item_id = str(
                            item.get(
                                entity_cfg.collection_id_key, item.get("index", "")
                            )
                        )
                        clean_item_id = item_id.replace(" ", "_").lower()
                        uid = f"{entry.entry_id}_{clean_id}_{entity_cfg.key}_{clean_item_id}"
                        if uid in tracked_sensors:
                            continue
                        tracked_sensors.add(uid)
                        new_sensors.append(
                            MCPHubMappedSensor(
                                coordinator,
                                entry,
                                mapping,
                                entity_cfg,
                                dev,
                                collection_item=item,
                            )
                        )
                else:
                    uid = f"{entry.entry_id}_{clean_id}_{entity_cfg.key}"
                    if uid in tracked_sensors:
                        continue
                    tracked_sensors.add(uid)
                    new_sensors.append(
                        MCPHubMappedSensor(coordinator, entry, mapping, entity_cfg, dev)
                    )

        if new_sensors:
            async_add_entities(new_sensors)

    _sync_mapped_sensors()
    coordinator.async_add_listener(_sync_mapped_sensors)


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


class MCPHubMappedSensor(CoordinatorEntity[MCPHubCoordinator], SensorEntity):
    """Dynamically mapped sensor for custom MCP devices."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        entry: ConfigEntry,
        mapping: DeviceMapping,
        entity_cfg: EntityMapping,
        device_data: dict[str, Any],
        collection_item: dict[str, Any] | None = None,
    ) -> None:
        """Initialize mapped sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._mapping = mapping
        self._entity_cfg = entity_cfg
        self._device_data = dict(device_data)
        self._collection_item = dict(collection_item) if collection_item else None

        ident_val = str(
            get_nested_value(device_data, mapping.device_identifier_key, mapping.id)
        )
        self._ident_val = ident_val
        clean_id = ident_val.replace(":", "_").replace(".", "_")

        if collection_item:
            item_id = str(
                collection_item.get(
                    entity_cfg.collection_id_key, collection_item.get("index", "")
                )
            )
            clean_item_id = item_id.replace(" ", "_").lower()
            self._attr_unique_id = (
                f"{entry.entry_id}_{clean_id}_{entity_cfg.key}_{clean_item_id}"
            )
            name_tpl = entity_cfg.name or "{item.name}"
            self._attr_name = render_template_str(name_tpl, {"item": collection_item})
        else:
            self._attr_unique_id = f"{entry.entry_id}_{clean_id}_{entity_cfg.key}"
            self._attr_name = entity_cfg.name

        cls_str = (entity_cfg.device_class or "").lower()
        if cls_str == "enum":
            self._attr_device_class = getattr(SensorDeviceClass, "ENUM", "enum")
            self._attr_options = entity_cfg.options
        elif cls_str == "timestamp":
            self._attr_device_class = getattr(
                SensorDeviceClass, "TIMESTAMP", "timestamp"
            )

        st_str = (entity_cfg.state_class or "").lower()
        if st_str == "measurement":
            self._attr_state_class = getattr(
                SensorStateClass, "MEASUREMENT", "measurement"
            )
        elif st_str == "total_increasing":
            self._attr_state_class = getattr(
                SensorStateClass, "TOTAL_INCREASING", "total_increasing"
            )

        if entity_cfg.unit_of_measurement:
            self._attr_native_unit_of_measurement = entity_cfg.unit_of_measurement

        self._update_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return dynamic device information extracted via custom mapping."""
        return extract_device_info(self._entry, self._mapping, self._device_data)

    def _update_state(self) -> None:
        """Update internal state and attributes safely."""
        status_val = get_nested_value(
            self._device_data, self._mapping.offline_policy.status_key
        )
        offline_vals = self._mapping.offline_policy.offline_values
        is_offline = status_val in offline_vals or (
            isinstance(status_val, str)
            and status_val.lower() in [str(x).lower() for x in offline_vals]
        )

        cls_str = (self._entity_cfg.device_class or "").lower()
        st_str = (self._entity_cfg.state_class or "").lower()

        if is_offline:
            if cls_str == "enum":
                self._attr_native_value = (
                    self._mapping.offline_policy.default_state_when_offline
                )
            elif cls_str == "timestamp":
                self._attr_native_value = None
            elif st_str in ("measurement", "total", "total_increasing"):
                self._attr_native_value = None
            self._attr_available = self._mapping.offline_policy.available_when_offline
            return

        self._attr_available = True
        source_data = (
            self._collection_item if self._collection_item else self._device_data
        )
        raw_val = get_nested_value(source_data, self._entity_cfg.value_path)
        val = (
            self._entity_cfg.state_map.get(raw_val, raw_val)
            if self._entity_cfg.state_map
            else raw_val
        )

        if cls_str == "timestamp":
            if val is None or val == "":
                self._attr_native_value = None
            elif isinstance(val, (int, float)):
                self._attr_native_value = dt_util.utc_from_timestamp(float(val))
            elif isinstance(val, str):
                parsed = dt_util.parse_datetime(val)
                self._attr_native_value = parsed if parsed is not None else None
            elif isinstance(val, datetime):
                self._attr_native_value = val
            else:
                self._attr_native_value = None
        elif st_str in ("measurement", "total", "total_increasing"):
            if val is None or val == "":
                self._attr_native_value = None
            else:
                try:
                    self._attr_native_value = (
                        int(val) if str(val).isdigit() else float(val)
                    )
                except (ValueError, TypeError):
                    self._attr_native_value = val
        else:
            self._attr_native_value = val

        if self._entity_cfg.attributes:
            attrs: dict[str, Any] = {}
            for ha_key, payload_path in self._entity_cfg.attributes.items():
                attrs[ha_key] = get_nested_value(source_data, payload_path)
            self._attr_extra_state_attributes = attrs

    def _handle_coordinator_update(self) -> None:
        """Handle updated coordinator data."""
        mapped_data = self.coordinator.data.get("mapped_data", {})
        payload = mapped_data.get(self._mapping.id)

        target_dev: dict[str, Any] | None = None
        if self._mapping.is_multi_device:
            devices = get_nested_value(payload, self._mapping.devices_path, []) or []
            for d in devices:
                ident = str(
                    get_nested_value(d, self._mapping.device_identifier_key, "")
                )
                if ident == self._ident_val:
                    target_dev = d
                    break
        elif isinstance(payload, dict):
            target_dev = payload

        if target_dev:
            self._device_data.update(target_dev)
            if self._collection_item:
                items = (
                    get_nested_value(target_dev, self._entity_cfg.collection_path, [])
                    or []
                )
                item_id = str(
                    self._collection_item.get(
                        self._entity_cfg.collection_id_key,
                        self._collection_item.get("index", ""),
                    )
                )
                for it in items:
                    if (
                        str(
                            it.get(
                                self._entity_cfg.collection_id_key,
                                it.get("index", ""),
                            )
                        )
                        == item_id
                    ):
                        self._collection_item.update(it)
                        break
            self._update_state()
            self.async_write_ha_state()
