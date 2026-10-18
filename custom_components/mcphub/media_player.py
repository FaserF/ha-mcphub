"""Media Player platform for MCPHub with dynamic custom mapping support."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MCPHub media players based on dynamic custom mappings."""
    coordinator: MCPHubCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    client: MCPHubClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]

    tracked_entities: set[str] = set()

    def _sync_mapped_media_players() -> None:
        mappings = load_mappings_from_entry(entry)
        media_mappings = [
            (m, e)
            for m in mappings
            if m.enabled
            for e in m.entities
            if e.platform == "media_player"
        ]
        if not media_mappings:
            return

        mapped_data = coordinator.data.get("mapped_data", {})
        new_entities: list[MCPHubMappedMediaPlayer] = []

        for mapping, entity_cfg in media_mappings:
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
                    MCPHubMappedMediaPlayer(
                        coordinator, client, entry, mapping, entity_cfg, dev
                    )
                )

        if new_entities:
            async_add_entities(new_entities)

    _sync_mapped_media_players()
    coordinator.async_add_listener(_sync_mapped_media_players)


class MCPHubMappedMediaPlayer(CoordinatorEntity[MCPHubCoordinator], MediaPlayerEntity):
    """Dynamically mapped media player for MCP devices (e.g. Android TV / phone)."""

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
        """Initialize the mapped media player."""
        super().__init__(coordinator)
        self._client = client
        self._entry = entry

        # Support backward-compatible signature (coordinator, client, entry, device_data)
        if device_data is None and isinstance(mapping, dict):
            device_data = mapping
            default_map = get_default_device_mappings()[0]
            self._mapping = default_map
            self._entity_cfg = default_map.entities[0]
        else:
            self._mapping = mapping  # type: ignore[assignment]
            self._entity_cfg = (
                entity_cfg or get_default_device_mappings()[0].entities[0]
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

        cls_str = (self._entity_cfg.device_class or "").lower()
        if cls_str == "tv":
            self._attr_device_class = MediaPlayerDeviceClass.TV
        elif cls_str == "receiver":
            self._attr_device_class = MediaPlayerDeviceClass.RECEIVER
        elif cls_str == "speaker":
            self._attr_device_class = MediaPlayerDeviceClass.SPEAKER
        else:
            self._attr_device_class = MediaPlayerDeviceClass.TV

        features = 0
        actions = self._entity_cfg.actions
        if "turn_on" in actions:
            features |= MediaPlayerEntityFeature.TURN_ON
        if "turn_off" in actions:
            features |= MediaPlayerEntityFeature.TURN_OFF
        if "play" in actions:
            features |= MediaPlayerEntityFeature.PLAY
        if "pause" in actions:
            features |= MediaPlayerEntityFeature.PAUSE
        if "stop" in actions:
            features |= MediaPlayerEntityFeature.STOP
        if "next_track" in actions:
            features |= MediaPlayerEntityFeature.NEXT_TRACK
        if "previous_track" in actions:
            features |= MediaPlayerEntityFeature.PREVIOUS_TRACK
        if "volume_up" in actions or "volume_down" in actions:
            features |= MediaPlayerEntityFeature.VOLUME_STEP
        if "volume_set" in actions:
            features |= MediaPlayerEntityFeature.VOLUME_SET
        if "volume_mute" in actions:
            features |= MediaPlayerEntityFeature.VOLUME_MUTE
        if "select_source" in actions and self._entity_cfg.source_list:
            features |= MediaPlayerEntityFeature.SELECT_SOURCE

        self._attr_supported_features = features
        self._attr_source_list = (
            list(self._entity_cfg.source_list.keys())
            if self._entity_cfg.source_list
            else None
        )
        self._reverse_source_map = (
            {v: k for k, v in self._entity_cfg.source_list.items()}
            if self._entity_cfg.source_list
            else {}
        )

        self._attr_state = MediaPlayerState.OFF
        self._attr_available = True
        self._attr_source: str | None = None
        self._attr_app_id: str | None = None
        self._attr_app_name: str | None = None
        self._attr_volume_level: float | None = None
        self._attr_is_volume_muted: bool | None = False

        self._update_state_from_data(self._device_data)

    @property
    def device_info(self) -> DeviceInfo:
        """Return dynamic device information extracted via custom mapping."""
        return extract_device_info(self._entry, self._mapping, self._device_data)

    def _update_state_from_data(self, data: dict[str, Any]) -> None:
        """Parse entity state and source safely."""
        status_val = get_nested_value(data, self._mapping.offline_policy.status_key)
        offline_vals = self._mapping.offline_policy.offline_values

        if status_val in offline_vals or (
            isinstance(status_val, str)
            and status_val.lower() in [str(x).lower() for x in offline_vals]
        ):
            self._attr_state = MediaPlayerState.OFF
            self._attr_available = self._mapping.offline_policy.available_when_offline
            return

        self._attr_available = True
        raw_state = str(
            get_nested_value(data, self._entity_cfg.value_path, "device")
        ).lower()
        if raw_state in ("device", "online", "idle", "playing", "on"):
            self._attr_state = MediaPlayerState.ON
        else:
            self._attr_state = MediaPlayerState.OFF

        if self._entity_cfg.current_source_path:
            raw_src = get_nested_value(data, self._entity_cfg.current_source_path)
            if raw_src and raw_src not in ("Unknown", "null", ""):
                self._attr_app_id = str(raw_src)
                self._attr_app_name = self._reverse_source_map.get(
                    str(raw_src), str(raw_src)
                )
                self._attr_source = self._attr_app_name

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

    async def async_update(self) -> None:
        """Poll device state directly or via dumpsys."""
        if not self._client or self._mapping.server_name != "android-adb":
            return
        serial = self._device_data.get("serial", "")
        if not serial:
            return

        cmd = "dumpsys power | grep mWakefulness ; dumpsys audio | grep -i 'streamVolume:' ; dumpsys media_session | grep -i 'state=PlaybackState' ; dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'"
        try:
            res = await self._client.async_call_tool(
                "android-adb",
                "adb_shell",
                {"command": cmd, "device": serial, "serial": serial},
            )
            raw_text = ""
            for item in res.get("content", []) if isinstance(res, dict) else []:
                if isinstance(item, dict) and item.get("type") == "text":
                    raw_text = item.get("text", "")
                    break
            if raw_text:
                self._parse_dumpsys_output(raw_text)
        except Exception:
            self._attr_state = MediaPlayerState.OFF
            self._attr_available = True

    def _parse_dumpsys_output(self, out: str) -> None:
        """Parse awake, volume, and playback state from adb output."""
        if "mWakefulness=Asleep" in out or "mWakefulness=Dozing" in out:
            self._attr_state = MediaPlayerState.OFF
            return

        vol_match = re.search(r"streamVolume:\s*(\d+)", out)
        if vol_match:
            try:
                self._attr_volume_level = round(int(vol_match.group(1)) / 100.0, 2)
            except Exception:
                pass

        if "state=3" in out:
            self._attr_state = MediaPlayerState.PLAYING
        elif "state=2" in out:
            self._attr_state = MediaPlayerState.PAUSED
        elif "state=1" in out:
            self._attr_state = MediaPlayerState.IDLE
        elif "mWakefulness=Awake" in out:
            self._attr_state = MediaPlayerState.ON

        app_match = re.search(r"Window\{[^\}]*\s+([a-zA-Z0-9_\.]+)/", out)
        if app_match:
            pkg = app_match.group(1)
            self._attr_app_id = pkg
            self._attr_app_name = self._reverse_source_map.get(pkg, pkg)
            self._attr_source = self._attr_app_name

    async def _execute_action(
        self, action_key: str, action_params: dict[str, Any] | None = None
    ) -> None:
        """Execute a mapped action with automatic ADB fallback."""
        action_mapping = self._entity_cfg.actions.get(action_key)
        dev_ctx = dict(self._device_data)
        if "serial" in dev_ctx and "device" not in dev_ctx:
            dev_ctx["device"] = dev_ctx["serial"]

        if action_mapping:
            ctx = dict(action_params or {})
            await async_execute_mapping_action(
                self._client,
                action_mapping,
                self._mapping.server_name,
                dev_ctx,
                ctx,
            )
        elif self._mapping.server_name == "android-adb":
            cmd_map = {
                "play": "MEDIA_PLAY",
                "pause": "MEDIA_PAUSE",
                "play_pause": "MEDIA_PLAY_PAUSE",
                "stop": "MEDIA_STOP",
                "next_track": "MEDIA_NEXT",
                "previous_track": "MEDIA_PREVIOUS",
                "turn_on": "WAKEUP",
                "turn_off": "SLEEP",
            }
            if action_key in cmd_map:
                await self._client.async_call_tool(
                    "android-adb",
                    "adb_keyevent",
                    {
                        "device": dev_ctx.get("serial", ""),
                        "keycode": cmd_map[action_key],
                    },
                )
            else:
                _LOGGER.warning(
                    "Action %s not mapped for %s", action_key, self.entity_id
                )
                return
        else:
            _LOGGER.warning("Action %s not mapped for %s", action_key, self.entity_id)
            return

        if action_key == "turn_on":
            self._attr_state = MediaPlayerState.ON
        elif action_key == "turn_off":
            self._attr_state = MediaPlayerState.OFF
        elif action_key == "play":
            self._attr_state = MediaPlayerState.PLAYING
        elif action_key == "pause":
            self._attr_state = MediaPlayerState.PAUSED
        elif action_key == "play_pause":
            self._attr_state = (
                MediaPlayerState.PAUSED
                if self._attr_state == MediaPlayerState.PLAYING
                else MediaPlayerState.PLAYING
            )
        elif action_key == "stop":
            self._attr_state = MediaPlayerState.IDLE

        if self._mapping.server_name == "android-adb":
            try:
                await self.async_update()
            except Exception:
                pass

        if self.hass:
            self.async_write_ha_state()
        if self.coordinator:
            ref = self.coordinator.async_request_refresh()
            if asyncio.iscoroutine(ref):
                await ref

    async def async_turn_on(self) -> None:
        """Turn on the media player."""
        await self._execute_action("turn_on")

    async def async_turn_off(self) -> None:
        """Turn off the media player."""
        await self._execute_action("turn_off")

    async def async_media_play(self) -> None:
        """Send play command."""
        await self._execute_action("play")

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._execute_action("pause")

    async def async_media_play_pause(self) -> None:
        """Send play/pause toggle command."""
        if "play_pause" in self._entity_cfg.actions:
            await self._execute_action("play_pause")
        elif self._attr_state == MediaPlayerState.PLAYING:
            await self.async_media_pause()
        else:
            await self.async_media_play()

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._execute_action("stop")

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._execute_action("next_track")

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self._execute_action("previous_track")

    async def async_volume_up(self) -> None:
        """Volume up."""
        await self._execute_action("volume_up")

    async def async_volume_down(self) -> None:
        """Volume down."""
        await self._execute_action("volume_down")

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level."""
        await self._execute_action("volume_set", {"volume": volume})

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        pkg = self._entity_cfg.source_list.get(source, source)
        self._attr_source = source
        self._attr_app_name = source
        self._attr_app_id = pkg
        await self._execute_action("select_source", {"source": pkg, "app": pkg})


# Backward compatibility alias
MCPHubAndroidMediaPlayer = MCPHubMappedMediaPlayer
