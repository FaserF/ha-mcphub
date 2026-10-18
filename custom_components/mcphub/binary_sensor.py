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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_SERVERS,
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
    sync_device_registry,
)
from .helpers import get_gateway_device_info, get_server_device_info


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

    for server in coordinator.data.get("servers", []):
        name = server.get("name", "")
        if not name or not _is_server_enabled(entry, name):
            continue
        entities.append(MCPHubServerConnectivitySensor(coordinator, entry, name))

    async_add_entities(entities)

    tracked_sensors: set[str] = set()

    def _sync_mapped_binary_sensors() -> None:
        mappings = load_mappings_from_entry(entry)
        bin_mappings = [
            (m, e)
            for m in mappings
            if m.enabled
            for e in m.entities
            if e.platform == "binary_sensor"
        ]
        if not bin_mappings:
            return

        mapped_data = coordinator.data.get("mapped_data", {})
        new_bins: list[BinarySensorEntity] = []

        for mapping, entity_cfg in bin_mappings:
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

                uid = f"{entry.entry_id}_{clean_id}_{entity_cfg.key}"
                if uid in tracked_sensors:
                    continue
                tracked_sensors.add(uid)
                new_bins.append(
                    MCPHubMappedBinarySensor(
                        coordinator, entry, mapping, entity_cfg, dev
                    )
                )

        if new_bins:
            async_add_entities(new_bins)

    _sync_mapped_binary_sensors()
    coordinator.async_add_listener(_sync_mapped_binary_sensors)


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
        self._attr_device_info = get_gateway_device_info(entry)

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
        """Return True if the server is connected."""
        data = self._get_server_data()
        return bool(data and data.get("status") == "connected")


class MCPHubMappedBinarySensor(
    CoordinatorEntity[MCPHubCoordinator], BinarySensorEntity
):
    """Dynamic binary sensor based on declarative custom mapping."""

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        entry: ConfigEntry,
        mapping: DeviceMapping,
        entity_cfg: EntityMapping,
        device_data: dict[str, Any],
        collection_item: dict[str, Any] | None = None,
    ) -> None:
        """Initialize mapped binary sensor."""
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

        self._attr_unique_id = f"{entry.entry_id}_{clean_id}_{entity_cfg.key}"
        self._attr_name = entity_cfg.name
        self._attr_has_entity_name = True

        cls_str = (entity_cfg.device_class or "").lower()
        if cls_str:
            self._attr_device_class = getattr(
                BinarySensorDeviceClass, cls_str.upper(), cls_str
            )

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

        if is_offline:
            self._attr_is_on = False
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
        self._attr_is_on = bool(val)

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
            self._update_state()
            self.async_write_ha_state()

