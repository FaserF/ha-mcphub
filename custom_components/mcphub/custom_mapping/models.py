"""Data models for dynamic MCP custom device and entity mappings."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ActionMapping:
    """Defines how a Home Assistant action maps to an MCP tool call."""

    tool: str
    args_template: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionMapping:
        """Create ActionMapping from dictionary."""
        return cls(
            tool=data.get("tool", ""),
            args_template=data.get("args_template", {}) or {},
        )


@dataclass
class EntityMapping:
    """Defines an entity to generate under a custom mapped MCP device."""

    platform: str
    key: str
    name: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    unit_of_measurement: str | None = None
    options: list[str] | None = None
    is_collection: bool = False
    collection_path: str = ""
    collection_id_key: str = "name"
    value_path: str = ""
    attributes: dict[str, str] = field(default_factory=dict)
    state_map: dict[str, Any] = field(default_factory=dict)
    actions: dict[str, ActionMapping] = field(default_factory=dict)
    source_list: dict[str, str] = field(default_factory=dict)
    current_source_path: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EntityMapping:
        """Create EntityMapping from dictionary."""
        raw_actions = data.get("actions", {}) or {}
        parsed_actions = {
            k: ActionMapping.from_dict(v)
            if isinstance(v, dict)
            else ActionMapping(tool=str(v))
            for k, v in raw_actions.items()
        }
        return cls(
            platform=data.get("platform", "sensor"),
            key=data.get("key", "default"),
            name=data.get("name"),
            device_class=data.get("device_class"),
            state_class=data.get("state_class"),
            unit_of_measurement=data.get("unit_of_measurement"),
            options=data.get("options"),
            is_collection=bool(data.get("is_collection", False)),
            collection_path=data.get("collection_path", ""),
            collection_id_key=data.get("collection_id_key", "name"),
            value_path=data.get("value_path", ""),
            attributes=data.get("attributes", {}) or {},
            state_map=data.get("state_map", {}) or {},
            actions=parsed_actions,
            source_list=data.get("source_list", {}) or {},
            current_source_path=data.get("current_source_path", ""),
        )


@dataclass
class DeviceInfoMapping:
    """Defines how hardware and network info is extracted from MCP payloads."""

    name_path: str = "name"
    manufacturer_path: str = "manufacturer"
    model_path: str = "model"
    sw_version_path: str = "sw_version"
    serial_path: str = "serial"
    mac_path: str = "mac"
    configuration_url_path: str = "configuration_url"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeviceInfoMapping:
        """Create DeviceInfoMapping from dictionary."""
        return cls(
            name_path=data.get("name_path", "name"),
            manufacturer_path=data.get("manufacturer_path", "manufacturer"),
            model_path=data.get("model_path", "model"),
            sw_version_path=data.get("sw_version_path", "sw_version"),
            serial_path=data.get("serial_path", "serial"),
            mac_path=data.get("mac_path", "mac"),
            configuration_url_path=data.get(
                "configuration_url_path", "configuration_url"
            ),
        )


@dataclass
class OfflinePolicy:
    """Defines how offline or unreachable states are handled gracefully."""

    status_key: str = "online"
    offline_values: list[Any] = field(
        default_factory=lambda: [False, "offline", "unreachable", "off"]
    )
    available_when_offline: bool = True
    default_state_when_offline: str = "off"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OfflinePolicy:
        """Create OfflinePolicy from dictionary."""
        return cls(
            status_key=data.get("status_key", "online"),
            offline_values=data.get(
                "offline_values", [False, "offline", "unreachable", "off"]
            ),
            available_when_offline=bool(data.get("available_when_offline", True)),
            default_state_when_offline=data.get("default_state_when_offline", "off"),
        )


@dataclass
class DeviceMapping:
    """Defines a full MCP server device and entity mapping."""

    id: str
    name: str
    server_name: str
    discovery_tool: str
    discovery_params: dict[str, Any] = field(default_factory=dict)
    is_multi_device: bool = False
    devices_path: str = "devices"
    device_identifier_key: str = "serial"
    device_info: DeviceInfoMapping = field(default_factory=DeviceInfoMapping)
    offline_policy: OfflinePolicy = field(default_factory=OfflinePolicy)
    entities: list[EntityMapping] = field(default_factory=list)
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeviceMapping:
        """Create DeviceMapping from dictionary."""
        dev_info = DeviceInfoMapping.from_dict(data.get("device_info", {}) or {})
        offline = OfflinePolicy.from_dict(data.get("offline_policy", {}) or {})
        entities = [
            EntityMapping.from_dict(e)
            for e in data.get("entities", [])
            if isinstance(e, dict)
        ]
        return cls(
            id=data.get("id", data.get("server_name", "custom")),
            name=data.get("name", "Custom MCP Device"),
            server_name=data.get("server_name", ""),
            discovery_tool=data.get("discovery_tool", ""),
            discovery_params=data.get("discovery_params", {}) or {},
            is_multi_device=bool(data.get("is_multi_device", False)),
            devices_path=data.get("devices_path", "devices"),
            device_identifier_key=data.get("device_identifier_key", "serial"),
            device_info=dev_info,
            offline_policy=offline,
            entities=entities,
            enabled=bool(data.get("enabled", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert DeviceMapping to serializable dictionary."""
        return asdict(self)
