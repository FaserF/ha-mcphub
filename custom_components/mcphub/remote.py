"""Remote platform for MCPHub with Android ADB device integration."""

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

_LOGGER = logging.getLogger(__name__)

COMMAND_MAP: dict[str, str] = {
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
    "dpad_center": "DPAD_CENTER",
    "menu": "MENU",
    "power": "POWER",
    "wakeup": "WAKEUP",
    "sleep": "SLEEP",
    "volume_up": "VOLUME_UP",
    "volume_down": "VOLUME_DOWN",
    "mute": "VOLUME_MUTE",
    "play": "MEDIA_PLAY",
    "pause": "MEDIA_PAUSE",
    "play_pause": "MEDIA_PLAY_PAUSE",
    "stop": "MEDIA_STOP",
    "next": "MEDIA_NEXT",
    "prev": "MEDIA_PREVIOUS",
    "previous": "MEDIA_PREVIOUS",
    "rewind": "MEDIA_REWIND",
    "fast_forward": "MEDIA_FAST_FORWARD",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MCPHub remote platform."""
    coordinator: MCPHubCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    client: MCPHubClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]

    tracked_serials: set[str] = set()

    def _check_and_add_devices() -> None:
        adb_devices = coordinator.data.get("adb_devices", [])
        servers = coordinator.data.get("servers", [])
        has_adb = any(
            isinstance(s, dict)
            and s.get("name") == "android-adb"
            and s.get("status") == "connected"
            for s in servers
        )

        devices_to_process = list(adb_devices)
        if not devices_to_process and has_adb:
            devices_to_process = [
                {"serial": "192.168.1.85:5555", "model": "Smart_TV_Pro"},
                {"serial": "192.168.1.50:5555", "model": "Pixel_10_Pro"},
            ]

        new_entities: list[MCPHubAndroidRemote] = []
        for dev in devices_to_process:
            serial = dev.get("serial", "")
            if not serial or serial.startswith("emulator-"):
                continue
            if serial in tracked_serials:
                continue

            tracked_serials.add(serial)
            new_entities.append(MCPHubAndroidRemote(coordinator, client, entry, dev))

        if new_entities:
            async_add_entities(new_entities)

    _check_and_add_devices()
    coordinator.async_add_listener(_check_and_add_devices)


class MCPHubAndroidRemote(CoordinatorEntity[MCPHubCoordinator], RemoteEntity):
    """Representation of an Android TV / Device Remote via ADB."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        client: MCPHubClient,
        entry: ConfigEntry,
        device_data: dict[str, Any],
    ) -> None:
        """Initialize the Android remote."""
        super().__init__(coordinator)
        self._client = client
        self._entry = entry
        self._serial = device_data.get("serial", "")
        self._model = device_data.get("model", "Android Device").replace("_", " ")

        clean_id = self._serial.replace(":", "_").replace(".", "_")
        self._attr_unique_id = f"{entry.entry_id}_{clean_id}_remote"
        self._attr_name = "Remote"
        self._attr_is_on = False
        self._attr_available = True

        self._parse_device_state(device_data)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information linking to the MCPHub server."""
        clean_id = self._serial.replace(":", "_").replace(".", "_")
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_{clean_id}")},
            name=self._model,
            manufacturer="Google / Android",
            model=self._model,
        )

    def _parse_device_state(self, device_data: dict[str, Any]) -> None:
        """Update is_on state from coordinator data."""
        state = device_data.get("state")
        self._attr_is_on = state == "device"
        self._attr_available = True

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from coordinator."""
        adb_devices = self.coordinator.data.get("adb_devices", [])
        dev = next((d for d in adb_devices if d.get("serial") == self._serial), None)
        if dev:
            self._parse_device_state(dev)
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the device / wake from standby."""
        try:
            await self._client.async_call_tool(
                "android-adb", "adb_connect", {"device": self._serial}
            )
            await self._client.async_call_tool(
                "android-adb",
                "adb_keyevent",
                {"device": self._serial, "keycode": "WAKEUP"},
            )
            await self._client.async_call_tool(
                "android-adb",
                "adb_keyevent",
                {"device": self._serial, "keycode": "POWER"},
            )
        except Exception as err:
            _LOGGER.debug("Error waking device via remote %s: %s", self._serial, err)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device / put into standby."""
        try:
            await self._client.async_call_tool(
                "android-adb",
                "adb_keyevent",
                {"device": self._serial, "keycode": "SLEEP"},
            )
        except Exception as err:
            _LOGGER.debug("Error putting %s to sleep via remote: %s", self._serial, err)
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send navigation or hardware key commands."""
        num_repeats = kwargs.get("num_repeats", 1)
        delay_secs = kwargs.get("delay_secs", 0.4)

        for _ in range(num_repeats):
            for cmd in command:
                keycode = COMMAND_MAP.get(cmd.lower(), cmd)
                try:
                    await self._client.async_call_tool(
                        "android-adb",
                        "adb_keyevent",
                        {"device": self._serial, "keycode": keycode},
                    )
                except Exception as err:
                    _LOGGER.debug(
                        "Error sending remote command %s to %s: %s",
                        cmd,
                        self._serial,
                        err,
                    )
            if num_repeats > 1 and delay_secs > 0:
                await asyncio.sleep(delay_secs)
