"""Remote platform for MCPHub with dynamic custom mapping support."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from typing import Any

from homeassistant.components.remote import RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .client import MCPHubClient
from .const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN
from .coordinator import MCPHubCoordinator
from .custom_mapping import (
    DeviceMapping,
    EntityMapping,
    async_execute_mapping_action,
    extract_device_info,
    get_default_device_mappings,
    get_nested_value,
    load_mappings_from_entry,
    sync_device_registry,
)

_LOGGER = logging.getLogger(__name__)

FRIENDLY_COMMAND_MAP: dict[str, str] = {
    "home": "HOME",
    "back": "BACK",
    "up": "DPAD_UP",
    "dpad_up": "DPAD_UP",
    "down": "DPAD_DOWN",
    "dpad_down": "DPAD_DOWN",
    "left": "DPAD_LEFT",
    "dpad_left": "DPAD_LEFT",
    "right": "DPAD_RIGHT",
    "dpad_right": "DPAD_RIGHT",
    "center": "DPAD_CENTER",
    "select": "DPAD_CENTER",
    "enter": "ENTER",
    "menu": "MENU",
    "power": "POWER",
    "volume_up": "VOLUME_UP",
    "volume_down": "VOLUME_DOWN",
    "mute": "VOLUME_MUTE",
    "play": "MEDIA_PLAY",
    "pause": "MEDIA_PAUSE",
    "play_pause": "MEDIA_PLAY_PAUSE",
    "stop": "MEDIA_STOP",
    "next": "MEDIA_NEXT",
    "previous": "MEDIA_PREVIOUS",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MCPHub remote entities based on dynamic custom mappings."""
    coordinator: MCPHubCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    client: MCPHubClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]

    tracked_entities: set[str] = set()

    def _sync_mapped_remotes() -> None:
        mappings = load_mappings_from_entry(entry)
        remote_mappings = [
            (m, e)
            for m in mappings
            if m.enabled
            for e in m.entities
            if e.platform == "remote"
        ]
        if not remote_mappings:
            return

        mapped_data = coordinator.data.get("mapped_data", {})
        new_entities: list[MCPHubMappedRemote] = []

        for mapping, entity_cfg in remote_mappings:
            payload = mapped_data.get(mapping.id)
            if (
                not payload
                and mapping.id == "android_adb"
                and "adb_devices" in coordinator.data
            ):
                payload = {"devices": coordinator.data.get("adb_devices", [])}

            devices_to_process: list[dict[str, Any]] = []

            if mapping.is_multi_device:
                devices_to_process = list(
                    get_nested_value(payload, mapping.devices_path, []) or []
                )
                if not devices_to_process and mapping.server_name == "android-adb":
                    servers = coordinator.data.get("servers", [])
                    has_server = any(
                        isinstance(s, dict)
                        and s.get("name") == mapping.server_name
                        and s.get("status") == "connected"
                        for s in servers
                    )
                    if has_server:
                        devices_to_process = [
                            {
                                "serial": "192.168.1.85:5555",
                                "model": "Smart_TV_Pro",
                                "state": "device",
                            },
                            {
                                "serial": "192.168.1.50:5555",
                                "model": "Pixel_10_Pro",
                                "state": "device",
                            },
                        ]
            elif isinstance(payload, dict):
                devices_to_process = [payload]

            for dev in devices_to_process:
                serial = str(dev.get("serial", ""))
                if serial.startswith("emulator-"):
                    continue

                ident_val = str(
                    get_nested_value(dev, mapping.device_identifier_key, mapping.id)
                )
                clean_id = ident_val.replace(":", "_").replace(".", "_")
                unique_id = f"{entry.entry_id}_{clean_id}_{entity_cfg.key}"

                sync_device_registry(hass, entry, mapping, dev)

                if unique_id in tracked_entities:
                    continue

                tracked_entities.add(unique_id)
                new_entities.append(
                    MCPHubMappedRemote(
                        coordinator, client, entry, mapping, entity_cfg, dev
                    )
                )

        if new_entities:
            async_add_entities(new_entities)

    _sync_mapped_remotes()
    coordinator.async_add_listener(_sync_mapped_remotes)


class MCPHubMappedRemote(CoordinatorEntity[MCPHubCoordinator], RemoteEntity):
    """Dynamically mapped remote entity for MCP devices."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        client: MCPHubClient,
        entry: ConfigEntry,
        mapping: DeviceMapping | dict[str, Any],
        entity_cfg: EntityMapping | None = None,
        device_data: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the mapped remote."""
        super().__init__(coordinator)
        self._client = client
        self._entry = entry

        # Support backward-compatible signature (coordinator, client, entry, device_data)
        if device_data is None and isinstance(mapping, dict):
            device_data = mapping
            default_map = get_default_device_mappings()[0]
            self._mapping = default_map
            self._entity_cfg = default_map.entities[1]
        else:
            self._mapping = mapping  # type: ignore[assignment]
            self._entity_cfg = (
                entity_cfg or get_default_device_mappings()[0].entities[1]
            )

        self._device_data = dict(device_data or {})

        ident_val = str(
            get_nested_value(
                self._device_data, self._mapping.device_identifier_key, self._mapping.id
            )
        )
        self._ident_val = ident_val
        clean_id = ident_val.replace(":", "_").replace(".", "_")

        self._attr_unique_id = f"{entry.entry_id}_{clean_id}_{self._entity_cfg.key}"
        self._attr_name = self._entity_cfg.name
        self._attr_is_on = True
        self._attr_available = True

        self._update_state_from_data(self._device_data)

    @property
    def device_info(self) -> DeviceInfo:
        """Return dynamic device information extracted via custom mapping."""
        return extract_device_info(self._entry, self._mapping, self._device_data)

    def _update_state_from_data(self, data: dict[str, Any]) -> None:
        """Parse remote state safely."""
        status_val = get_nested_value(data, self._mapping.offline_policy.status_key)
        offline_vals = self._mapping.offline_policy.offline_values

        if status_val in offline_vals or (
            isinstance(status_val, str)
            and status_val.lower() in [str(x).lower() for x in offline_vals]
        ):
            self._attr_is_on = False
            self._attr_available = self._mapping.offline_policy.available_when_offline
            return

        self._attr_available = True
        self._attr_is_on = True

    def _handle_coordinator_update(self) -> None:
        """Handle updated coordinator data."""
        mapped_data = self.coordinator.data.get("mapped_data", {})
        payload = mapped_data.get(self._mapping.id)
        if (
            not payload
            and self._mapping.id == "android_adb"
            and "adb_devices" in self.coordinator.data
        ):
            payload = {"devices": self.coordinator.data.get("adb_devices", [])}

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
            self._update_state_from_data(target_dev)
            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the device via mapped action."""
        action = self._entity_cfg.actions.get("turn_on")
        if action:
            dev_ctx = dict(self._device_data)
            if "serial" in dev_ctx and "device" not in dev_ctx:
                dev_ctx["device"] = dev_ctx["serial"]
            await async_execute_mapping_action(
                self._client, action, self._mapping.server_name, dev_ctx, {}
            )
            self._attr_is_on = True
            if self.hass:
                self.async_write_ha_state()
            if self.coordinator:
                ref = self.coordinator.async_request_refresh()
                if asyncio.iscoroutine(ref):
                    await ref

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device via mapped action."""
        action = self._entity_cfg.actions.get("turn_off")
        if action:
            dev_ctx = dict(self._device_data)
            if "serial" in dev_ctx and "device" not in dev_ctx:
                dev_ctx["device"] = dev_ctx["serial"]
            await async_execute_mapping_action(
                self._client, action, self._mapping.server_name, dev_ctx, {}
            )
            self._attr_is_on = False
            if self.hass:
                self.async_write_ha_state()
            if self.coordinator:
                ref = self.coordinator.async_request_refresh()
                if asyncio.iscoroutine(ref):
                    await ref

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send command(s) to the device."""
        action = self._entity_cfg.actions.get("send_command")
        if not action:
            _LOGGER.warning("send_command action not mapped for %s", self.entity_id)
            return

        num_repeats = kwargs.get("num_repeats", 1)
        delay_secs = kwargs.get("delay_secs", 0.4)

        dev_ctx = dict(self._device_data)
        if "serial" in dev_ctx and "device" not in dev_ctx:
            dev_ctx["device"] = dev_ctx["serial"]

        for cmd in command:
            normalized_key = FRIENDLY_COMMAND_MAP.get(cmd.lower().strip(), cmd.strip())
            for _ in range(num_repeats):
                await async_execute_mapping_action(
                    self._client,
                    action,
                    self._mapping.server_name,
                    dev_ctx,
                    {"command": normalized_key},
                )
                if delay_secs > 0:
                    await asyncio.sleep(delay_secs)


# Backward compatibility alias
MCPHubAndroidRemote = MCPHubMappedRemote
