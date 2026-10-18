"""Media Player platform for MCPHub with Android ADB device integration."""

from __future__ import annotations

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

_LOGGER = logging.getLogger(__name__)

SUPPORT_ANDROID_TV = (
    MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
)

DEFAULT_APP_MAP: dict[str, str] = {
    "YouTube": "com.google.android.youtube.tv",
    "SmartTube": "org.smarttube.stable",
    "SmartTube Beta": "com.liskovsoft.smarttubetv.beta",
    "Netflix": "com.netflix.ninja",
    "Prime Video": "com.amazon.amazonvideo.livingroom",
    "Disney+": "com.disney.disneyplus",
    "Jellyfin": "org.jellyfin.androidtv",
    "Emby": "tv.emby.embyatv",
    "Plex": "com.plexapp.android",
    "Plezy": "com.edde746.plezy",
    "Moonfin": "org.moonfin.androidtv",
    "Cloudstream": "com.lagradost.cloudstream3",
    "Kodi": "org.xbmc.kodi",
    "Crunchyroll": "com.crunchyroll.crunchyroid",
    "Twitch": "tv.twitch.android.app",
    "ARD Mediathek": "de.swr.avp.ard.tv",
    "ZDF Mediathek": "com.zdf.android.mediathek",
    "Joyn": "de.prosiebensat1digital.seventv",
    "Spotify": "com.spotify.tv.android",
    "SoundCloud": "com.soundcloud.android",
    "Bilibili": "com.bstar.intl.tv",
    "Cast Receiver": "com.instantbits.cast.receiver",
    "File Manager": "com.rs.explorer.filemanager",
    "APKMirror": "com.apkmirror.helper.prod",
    "Hermes Link": "de.fabiseitz.hermeslink.tv",
    "Settings": "com.android.tv.settings",
    "Home Screen": "com.google.android.tvlauncher",
}

PACKAGE_TO_APP_NAME: dict[str, str] = {v: k for k, v in DEFAULT_APP_MAP.items()}
PACKAGE_TO_APP_NAME.update(
    {
        "com.google.android.youtube": "YouTube",
        "app.revanced.android.youtube": "YouTube (ReVanced)",
        "app.revanced.android.apps.youtube.music": "YouTube Music",
        "com.google.android.apps.youtube.music": "YouTube Music",
        "com.spotify.music": "Spotify",
        "org.jellyfin.mobile": "Jellyfin",
        "com.amazon.avod.thirdpartyclient": "Prime Video",
        "io.homeassistant.companion.android": "Home Assistant",
        "com.android.settings": "Settings",
        "com.android.chrome": "Chrome",
        "com.google.android.apps.nexuslauncher": "Home Screen",
        "de.fabiseitz.hermeslink": "Hermes Link",
        "com.ebay.kleinanzeigen": "Kleinanzeigen",
        "org.telegram.messenger": "Telegram",
        "com.whatsapp": "WhatsApp",
        "com.anthropic.claude": "Claude",
        "sh.paseo": "Paseo",
        "com.google.android.keep": "Google Keep",
        "com.google.android.apps.chromecast.app": "Google Home",
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MCPHub media player platform."""
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

        new_entities: list[MCPHubAndroidMediaPlayer] = []
        for dev in devices_to_process:
            serial = dev.get("serial", "")
            if not serial or serial.startswith("emulator-"):
                continue
            if serial in tracked_serials:
                continue

            tracked_serials.add(serial)
            new_entities.append(
                MCPHubAndroidMediaPlayer(coordinator, client, entry, dev)
            )

        if new_entities:
            async_add_entities(new_entities)

    _check_and_add_devices()
    coordinator.async_add_listener(_check_and_add_devices)


class MCPHubAndroidMediaPlayer(CoordinatorEntity[MCPHubCoordinator], MediaPlayerEntity):
    """Representation of an Android device / TV via ADB MCP server."""

    _attr_has_entity_name = True
    _attr_supported_features = SUPPORT_ANDROID_TV
    _attr_source_list = list(DEFAULT_APP_MAP.keys())

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        client: MCPHubClient,
        entry: ConfigEntry,
        device_data: dict[str, Any],
    ) -> None:
        """Initialize the Android media player."""
        super().__init__(coordinator)
        self._client = client
        self._entry = entry
        self._serial = device_data.get("serial", "")
        self._model = device_data.get("model", "Android Device").replace("_", " ")

        clean_id = self._serial.replace(":", "_").replace(".", "_")
        self._attr_unique_id = f"{entry.entry_id}_{clean_id}_media_player"
        self._attr_name = None

        is_tv = "tv" in self._model.lower() or "85" in self._serial
        self._attr_device_class = (
            MediaPlayerDeviceClass.TV if is_tv else MediaPlayerDeviceClass.RECEIVER
        )

        self._attr_state = MediaPlayerState.OFF
        self._attr_available = True
        self._attr_volume_level: float | None = None
        self._attr_is_volume_muted: bool | None = False
        self._attr_source: str | None = None
        self._attr_app_id: str | None = None
        self._attr_app_name: str | None = None

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
        """Parse basic device status from coordinator data without error logging."""
        state = device_data.get("state")
        if state != "device":
            self._attr_state = MediaPlayerState.OFF
            self._attr_available = True
            return

        app = device_data.get("currentApp")
        if app and app != "Unknown":
            self._attr_app_id = app
            self._attr_app_name = PACKAGE_TO_APP_NAME.get(app, app)
            self._attr_source = self._attr_app_name

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        adb_devices = self.coordinator.data.get("adb_devices", [])
        dev = next((d for d in adb_devices if d.get("serial") == self._serial), None)
        if dev:
            self._parse_device_state(dev)
        super()._handle_coordinator_update()

    async def async_update(self) -> None:
        """Poll device for wakefulness, volume, and playback state."""
        cmd = (
            "dumpsys power | grep -m1 'mWakefulness='; "
            "dumpsys audio | grep -m1 'streamVolume:'; "
            "dumpsys media_session | grep -m1 'state=PlaybackState'; "
            "dumpsys window | grep -m1 'mCurrentFocus='"
        )
        try:
            res = await self._client.async_call_tool(
                "android-adb",
                "adb_shell",
                {"command": cmd, "device": self._serial},
            )
            raw_text = ""
            content = res.get("content", []) if isinstance(res, dict) else []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    raw_text = item.get("text", "")
                    break

            if not raw_text or "device offline" in raw_text.lower():
                self._attr_state = MediaPlayerState.OFF
                self._attr_available = True
                return

            if "mWakefulness=Awake" in raw_text:
                self._attr_state = MediaPlayerState.ON
            else:
                self._attr_state = MediaPlayerState.OFF
                self._attr_available = True
                return

            vol_match = re.search(r"streamVolume:(\d+)", raw_text)
            if vol_match:
                vol_val = int(vol_match.group(1))
                max_vol = 100.0 if vol_val > 30 else 25.0
                self._attr_volume_level = min(1.0, max(0.0, vol_val / max_vol))

            play_match = re.search(r"state=(\d+)", raw_text)
            if play_match:
                p_code = int(play_match.group(1))
                if p_code == 3:
                    self._attr_state = MediaPlayerState.PLAYING
                elif p_code == 2:
                    self._attr_state = MediaPlayerState.PAUSED

            app_match = re.search(
                r"mCurrentFocus=Window\{[^\s]+ [^\s]+ ([^\s/]+)", raw_text
            )
            if app_match:
                pkg = app_match.group(1).strip()
                self._attr_app_id = pkg
                self._attr_app_name = PACKAGE_TO_APP_NAME.get(pkg, pkg)
                self._attr_source = self._attr_app_name

        except Exception as err:
            _LOGGER.debug(
                "Android device %s is offline or sleeping during update: %s",
                self._serial,
                err,
            )
            self._attr_state = MediaPlayerState.OFF
            self._attr_available = True

    async def async_turn_on(self) -> None:
        """Wake Android device from standby."""
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
            _LOGGER.debug("Wake command error on %s: %s", self._serial, err)
        self._attr_state = MediaPlayerState.ON
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Put Android device into standby/sleep."""
        try:
            await self._client.async_call_tool(
                "android-adb",
                "adb_keyevent",
                {"device": self._serial, "keycode": "SLEEP"},
            )
        except Exception as err:
            _LOGGER.debug("Sleep command error on %s: %s", self._serial, err)
        self._attr_state = MediaPlayerState.OFF
        self.async_write_ha_state()

    async def async_media_play(self) -> None:
        """Send play command."""
        await self._client.async_call_tool(
            "android-adb",
            "adb_keyevent",
            {"device": self._serial, "keycode": "MEDIA_PLAY"},
        )
        self._attr_state = MediaPlayerState.PLAYING
        self.async_write_ha_state()

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._client.async_call_tool(
            "android-adb",
            "adb_keyevent",
            {"device": self._serial, "keycode": "MEDIA_PAUSE"},
        )
        self._attr_state = MediaPlayerState.PAUSED
        self.async_write_ha_state()

    async def async_media_play_pause(self) -> None:
        """Toggle play/pause command."""
        await self._client.async_call_tool(
            "android-adb",
            "adb_keyevent",
            {"device": self._serial, "keycode": "MEDIA_PLAY_PAUSE"},
        )
        if self._attr_state == MediaPlayerState.PLAYING:
            self._attr_state = MediaPlayerState.PAUSED
        else:
            self._attr_state = MediaPlayerState.PLAYING
        self.async_write_ha_state()

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._client.async_call_tool(
            "android-adb",
            "adb_keyevent",
            {"device": self._serial, "keycode": "MEDIA_STOP"},
        )
        self._attr_state = MediaPlayerState.ON
        self.async_write_ha_state()

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._client.async_call_tool(
            "android-adb",
            "adb_keyevent",
            {"device": self._serial, "keycode": "MEDIA_NEXT"},
        )

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self._client.async_call_tool(
            "android-adb",
            "adb_keyevent",
            {"device": self._serial, "keycode": "MEDIA_PREVIOUS"},
        )

    async def async_volume_up(self) -> None:
        """Send volume up command."""
        await self._client.async_call_tool(
            "android-adb",
            "adb_keyevent",
            {"device": self._serial, "keycode": "VOLUME_UP"},
        )
        if self._attr_volume_level is not None:
            self._attr_volume_level = min(1.0, self._attr_volume_level + 0.05)
            self.async_write_ha_state()

    async def async_volume_down(self) -> None:
        """Send volume down command."""
        await self._client.async_call_tool(
            "android-adb",
            "adb_keyevent",
            {"device": self._serial, "keycode": "VOLUME_DOWN"},
        )
        if self._attr_volume_level is not None:
            self._attr_volume_level = max(0.0, self._attr_volume_level - 0.05)
            self.async_write_ha_state()

    async def async_mute_volume(self, mute: bool) -> None:
        """Send volume mute command."""
        await self._client.async_call_tool(
            "android-adb",
            "adb_keyevent",
            {"device": self._serial, "keycode": "VOLUME_MUTE"},
        )
        self._attr_is_volume_muted = mute
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level."""
        target_idx = round(volume * 100)
        cmd = f"cmd media_session volume --stream 3 --set {target_idx}"
        try:
            await self._client.async_call_tool(
                "android-adb",
                "adb_shell",
                {"command": cmd, "device": self._serial},
            )
        except Exception as err:
            _LOGGER.debug("Could not set volume on %s: %s", self._serial, err)
        self._attr_volume_level = volume
        self.async_write_ha_state()

    async def async_select_source(self, source: str) -> None:
        """Launch application source on Android TV."""
        pkg = DEFAULT_APP_MAP.get(source, source)
        try:
            await self._client.async_call_tool(
                "android-adb",
                "adb_app_launch",
                {"app": pkg, "device": self._serial},
            )
        except Exception as err:
            _LOGGER.debug("Could not launch app %s on %s: %s", pkg, self._serial, err)
        self._attr_source = source
        self._attr_app_id = pkg
        self._attr_app_name = source
        self.async_write_ha_state()
