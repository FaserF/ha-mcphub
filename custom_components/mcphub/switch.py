"""Switches for MCPHub integration with per-server control and dynamic custom mapping support."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
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
from .custom_mapping import (
    DeviceMapping,
    EntityMapping,
    async_execute_mapping_action,
    extract_device_info,
    get_nested_value,
    load_mappings_from_entry,
    sync_device_registry,
)
from .helpers import get_server_device_info

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
    """Set up MCPHub switch platform."""
    coordinator: MCPHubCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    client: MCPHubClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]

    entities: list[SwitchEntity] = []

    for server in coordinator.data.get("servers", []):
        name = server.get("name", "")
        if not name or not _is_server_enabled(entry, name):
            continue
        entities.append(MCPHubServerEnableSwitch(coordinator, client, entry, name))

        tools = server.get("tools", [])
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            schema = tool.get("inputSchema") or {}
            props = schema.get("properties", {})
            req_params = schema.get("required", [])

            bool_props = [
                k
                for k, v in props.items()
                if isinstance(v, dict) and v.get("type") == "boolean"
            ]
            if len(bool_props) == 1:
                bool_param = bool_props[0]
                other_req = [p for p in req_params if p != bool_param]
                if not other_req:
                    entities.append(
                        MCPHubDynamicToolSwitch(
                            coordinator=coordinator,
                            client=client,
                            entry=entry,
                            server_name=name,
                            tool=tool,
                            param_name=bool_param,
                        )
                    )

    async_add_entities(entities)

    # Process dynamically mapped switches (e.g. Printer power switch)
    tracked_switches: set[str] = set()

    def _sync_mapped_switches() -> None:
        mappings = load_mappings_from_entry(entry)
        switch_mappings = [
            (m, e)
            for m in mappings
            if m.enabled
            for e in m.entities
            if e.platform == "switch"
        ]
        if not switch_mappings:
            return

        mapped_data = coordinator.data.get("mapped_data", {})
        new_switches: list[SwitchEntity] = []

        for mapping, entity_cfg in switch_mappings:
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
                uid = f"{entry.entry_id}_{clean_id}_{entity_cfg.key}"

                sync_device_registry(hass, entry, mapping, dev)

                if uid in tracked_switches:
                    continue

                tracked_switches.add(uid)
                new_switches.append(
                    MCPHubMappedSwitch(
                        coordinator, client, entry, mapping, entity_cfg, dev
                    )
                )

        if new_switches:
            async_add_entities(new_switches)

    _sync_mapped_switches()
    coordinator.async_add_listener(_sync_mapped_switches)


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
            icon="mdi:toggle-switch-outline",
        )
        self._attr_unique_id = f"{entry.entry_id}_server_enable_{server_name}"
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
        server = self._get_server_data()
        return bool(server.get("enabled", True)) if server else True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the server in MCPHub."""
        await self._client.async_toggle_server(self._server_name, enable=True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the server in MCPHub."""
        await self._client.async_toggle_server(self._server_name, enable=False)
        await self.coordinator.async_request_refresh()


class MCPHubDynamicToolSwitch(CoordinatorEntity[MCPHubCoordinator], SwitchEntity):
    """Switch that calls a single-boolean tool on turn_on / turn_off."""

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        client: MCPHubClient,
        entry: ConfigEntry,
        server_name: str,
        tool: dict[str, Any],
        param_name: str,
    ) -> None:
        """Initialize the tool switch."""
        super().__init__(coordinator)
        self._client = client
        self._server_name = server_name
        self._tool = tool
        self._param_name = param_name
        raw_name = tool.get("name", "")
        short_name = (
            raw_name.split("-")[-1]
            .replace(f"{server_name}_", "")
            .replace("_", " ")
            .title()
        )

        self._attr_unique_id = f"{entry.entry_id}_{server_name}_switch_{raw_name}"
        self._attr_has_entity_name = True
        self._attr_name = short_name
        self._attr_icon = "mdi:tune"
        self._is_on = False

        server_data = self._get_server_data() or {}
        self._attr_device_info = get_server_device_info(entry, server_name, server_data)

    def _get_server_data(self) -> dict[str, Any] | None:
        """Get latest data for this server."""
        if not self.coordinator.data:
            return None
        for server in self.coordinator.data.get(ATTR_SERVERS, []):
            if server.get("name") == self._server_name:
                return server
        return None

    @property
    def is_on(self) -> bool:
        """Return cached on state."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Call tool with True."""
        await self._client.async_call_tool(
            server=self._server_name,
            tool_name=self._tool.get("name", ""),
            arguments={self._param_name: True},
        )
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Call tool with False."""
        await self._client.async_call_tool(
            server=self._server_name,
            tool_name=self._tool.get("name", ""),
            arguments={self._param_name: False},
        )
        self._is_on = False
        self.async_write_ha_state()


class MCPHubMappedSwitch(CoordinatorEntity[MCPHubCoordinator], SwitchEntity):
    """Dynamically mapped switch for custom MCP devices."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        client: MCPHubClient,
        entry: ConfigEntry,
        mapping: DeviceMapping,
        entity_cfg: EntityMapping,
        device_data: dict[str, Any],
    ) -> None:
        """Initialize mapped switch."""
        super().__init__(coordinator)
        self._client = client
        self._entry = entry
        self._mapping = mapping
        self._entity_cfg = entity_cfg
        self._device_data = dict(device_data)

        ident_val = str(
            get_nested_value(device_data, mapping.device_identifier_key, mapping.id)
        )
        self._ident_val = ident_val
        clean_id = ident_val.replace(":", "_").replace(".", "_")

        self._attr_unique_id = f"{entry.entry_id}_{clean_id}_{entity_cfg.key}"
        self._attr_name = entity_cfg.name
        self._attr_is_on = False
        self._attr_available = True

        self._update_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return dynamic device information extracted via custom mapping."""
        return extract_device_info(self._entry, self._mapping, self._device_data)

    def _update_state(self) -> None:
        """Parse switch state safely."""
        val = get_nested_value(self._device_data, self._entity_cfg.value_path)
        if isinstance(val, bool):
            self._attr_is_on = val
        elif isinstance(val, str):
            self._attr_is_on = val.lower() in ("on", "true", "1")
        else:
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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on switch via mapped action."""
        action = self._entity_cfg.actions.get("turn_on")
        if action:
            await async_execute_mapping_action(
                self._client, action, self._mapping.server_name, self._device_data, {}
            )
            self._attr_is_on = True
            self.async_write_ha_state()
            if self.coordinator:
                ref = self.coordinator.async_request_refresh()
                if asyncio.iscoroutine(ref):
                    await ref

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off switch via mapped action."""
        action = self._entity_cfg.actions.get("turn_off")
        if action:
            await async_execute_mapping_action(
                self._client, action, self._mapping.server_name, self._device_data, {}
            )
            self._attr_is_on = False
            self.async_write_ha_state()
            if self.coordinator:
                ref = self.coordinator.async_request_refresh()
                if asyncio.iscoroutine(ref):
                    await ref
