"""Tests for the MCPHub Android media player platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerState,
)

from custom_components.mcphub.const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN
from custom_components.mcphub.media_player import (
    MCPHubAndroidMediaPlayer,
    async_setup_entry,
)


@pytest.fixture
def mock_adb_coordinator(hass: MagicMock, mock_client: MagicMock) -> MagicMock:
    """Create a coordinator with android-adb server and device data."""
    coordinator = MagicMock()
    coordinator.hass = hass
    coordinator.data = {
        "latency_ms": 15.0,
        "total_servers": 1,
        "connected_servers": 1,
        "total_tools": 10,
        "servers": [
            {
                "name": "android-adb",
                "version": "1.0.0",
                "status": "connected",
                "enabled": True,
                "tools": [{"name": "android-adb-adb_devices"}],
            }
        ],
        "adb_devices": [
            {
                "serial": "192.168.1.85:5555",
                "state": "device",
                "model": "Smart_TV_Pro",
                "battery": "50%",
                "currentApp": "org.smarttube.stable",
            },
            {
                "serial": "192.168.1.50:5555",
                "state": "device",
                "model": "Pixel_10_Pro",
                "battery": "80%",
                "currentApp": "com.android.chrome",
            },
            {
                "serial": "emulator-5574",
                "state": "offline",
                "model": "Unknown",
                "battery": "Unknown",
                "currentApp": "Unknown",
            },
        ],
    }
    coordinator.last_update_success = True
    coordinator.async_add_listener = MagicMock()
    return coordinator


async def test_media_player_setup(
    hass: MagicMock,
    mock_config_entry: MagicMock,
    mock_client: MagicMock,
    mock_adb_coordinator: MagicMock,
) -> None:
    """Test media player setup and entity creation."""
    hass.data[DOMAIN] = {
        mock_config_entry.entry_id: {
            DATA_COORDINATOR: mock_adb_coordinator,
            DATA_CLIENT: mock_client,
        }
    }

    added_entities: list[MCPHubAndroidMediaPlayer] = []
    await async_setup_entry(
        hass, mock_config_entry, lambda entities: added_entities.extend(entities)
    )

    # Emulator should be ignored; TV and Pixel should be created
    assert len(added_entities) == 2
    tv = next(e for e in added_entities if "85" in e.unique_id)
    assert tv.name is None
    assert tv.device_class == MediaPlayerDeviceClass.TV
    assert tv.available is True


async def test_media_player_offline_graceful(
    hass: MagicMock,
    mock_config_entry: MagicMock,
    mock_client: MagicMock,
    mock_adb_coordinator: MagicMock,
) -> None:
    """Test offline Android TV handles status updates without throwing errors."""
    mock_client.async_call_tool = AsyncMock(
        side_effect=Exception("ADB SSH error: adb: device offline")
    )

    player = MCPHubAndroidMediaPlayer(
        mock_adb_coordinator,
        mock_client,
        mock_config_entry,
        {"serial": "192.168.1.85:5555", "model": "Smart_TV_Pro", "state": "offline"},
    )

    # Initial state should be OFF and available
    assert player.state == MediaPlayerState.OFF
    assert player.available is True

    # Poll update when offline should silently remain OFF without exception
    await player.async_update()
    assert player.state == MediaPlayerState.OFF
    assert player.available is True


async def test_media_player_awake_and_playback_parsing(
    hass: MagicMock,
    mock_config_entry: MagicMock,
    mock_client: MagicMock,
    mock_adb_coordinator: MagicMock,
) -> None:
    """Test parsing wakefulness, volume, and playback state from adb output."""
    composite_output = (
        "mWakefulness=Awake\n"
        "   streamVolume:40\n"
        "      state=PlaybackState {state=3, position=12000}\n"
        "  mCurrentFocus=Window{123 u0 org.jellyfin.androidtv/org.jellyfin.MainActivity}\n"
    )
    mock_client.async_call_tool = AsyncMock(
        return_value={"content": [{"type": "text", "text": composite_output}]}
    )

    player = MCPHubAndroidMediaPlayer(
        mock_adb_coordinator,
        mock_client,
        mock_config_entry,
        {"serial": "192.168.1.85:5555", "model": "Smart_TV_Pro", "state": "device"},
    )

    await player.async_update()
    assert player.state == MediaPlayerState.PLAYING
    assert player.volume_level == 0.4
    assert player.source == "Jellyfin"


async def test_media_player_control_actions(
    hass: MagicMock,
    mock_config_entry: MagicMock,
    mock_client: MagicMock,
    mock_adb_coordinator: MagicMock,
) -> None:
    """Test turn on/off, play, pause, volume, and app launch actions."""
    mock_client.async_call_tool = AsyncMock(return_value={"result": "ok"})

    player = MCPHubAndroidMediaPlayer(
        mock_adb_coordinator,
        mock_client,
        mock_config_entry,
        {"serial": "192.168.1.85:5555", "model": "Smart_TV_Pro", "state": "device"},
    )

    # Turn on
    await player.async_turn_on()
    assert player.state == MediaPlayerState.ON

    # Turn off
    await player.async_turn_off()
    assert player.state == MediaPlayerState.OFF

    # Play & Pause
    await player.async_media_play()
    assert player.state == MediaPlayerState.PLAYING

    await player.async_media_pause()
    assert player.state == MediaPlayerState.PAUSED

    # Source selection (YouTube)
    await player.async_select_source("YouTube")
    assert player.source == "YouTube"
    mock_client.async_call_tool.assert_called_with(
        "android-adb",
        "adb_app_launch",
        {"app": "com.google.android.youtube.tv", "device": "192.168.1.85:5555"},
    )


async def test_media_player_device_info_mac_linking(
    mock_config_entry: MagicMock,
    mock_client: MagicMock,
    mock_adb_coordinator: MagicMock,
) -> None:
    """Test device info publishes real manufacturer, model, sw_version, and MAC connections for OpenWrt linking."""
    from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, format_mac
    if hasattr(format_mac, "side_effect"):
        format_mac.side_effect = lambda m: str(m).lower()

    tv_player = MCPHubAndroidMediaPlayer(
        mock_adb_coordinator,
        mock_client,
        mock_config_entry,
        {
            "serial": "192.168.1.85:5555",
            "model": "Smart_TV_Pro",
            "manufacturer": "TCL",
            "androidVersion": "Android 11",
            "macs": ["dc:72:23:9d:ec:19", "34:51:80:d0:44:29"],
            "state": "device",
        },
    )
    dev_info = tv_player.device_info
    assert dev_info["manufacturer"] == "TCL"
    assert "Smart TV Pro" in dev_info["model"]
    assert dev_info["sw_version"] == "Android 11"
    assert (CONNECTION_NETWORK_MAC, "dc:72:23:9d:ec:19") in dev_info["connections"]

    pixel_player = MCPHubAndroidMediaPlayer(
        mock_adb_coordinator,
        mock_client,
        mock_config_entry,
        {
            "serial": "192.168.1.50:5555",
            "model": "Pixel_10_Pro",
            "manufacturer": "Google",
            "androidVersion": "Android 17",
            "macs": ["64:9d:38:c4:99:06"],
            "state": "device",
        },
    )
    pixel_info = pixel_player.device_info
    assert pixel_info["manufacturer"] == "Google"
    assert "Pixel 10 Pro" in pixel_info["model"]
    assert pixel_info["sw_version"] == "Android 17"
    assert (CONNECTION_NETWORK_MAC, "64:9d:38:c4:99:06") in pixel_info["connections"]

