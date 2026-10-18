"""Tests for the MCPHub Android remote platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.mcphub.const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN
from custom_components.mcphub.remote import MCPHubAndroidRemote, async_setup_entry


@pytest.fixture
def mock_adb_coordinator(hass: MagicMock, mock_client: MagicMock) -> MagicMock:
    """Create a coordinator with android-adb server and device data."""
    coordinator = MagicMock()
    coordinator.hass = hass
    coordinator.data = {
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
            },
            {
                "serial": "192.168.1.50:5555",
                "state": "offline",
                "model": "Pixel_10_Pro",
            },
        ],
    }
    coordinator.async_add_listener = MagicMock()
    return coordinator


async def test_remote_setup(
    hass: MagicMock,
    mock_config_entry: MagicMock,
    mock_client: MagicMock,
    mock_adb_coordinator: MagicMock,
) -> None:
    """Test remote platform setup and entity creation."""
    hass.data[DOMAIN] = {
        mock_config_entry.entry_id: {
            DATA_COORDINATOR: mock_adb_coordinator,
            DATA_CLIENT: mock_client,
        }
    }

    added_entities: list[MCPHubAndroidRemote] = []
    await async_setup_entry(
        hass, mock_config_entry, lambda entities: added_entities.extend(entities)
    )

    assert len(added_entities) == 2
    tv_remote = next(e for e in added_entities if "85" in e.unique_id)
    assert tv_remote.name == "Remote"
    assert tv_remote.is_on is True


async def test_remote_send_command(
    hass: MagicMock,
    mock_config_entry: MagicMock,
    mock_client: MagicMock,
    mock_adb_coordinator: MagicMock,
) -> None:
    """Test sending navigation commands via the remote."""
    mock_client.async_call_tool = AsyncMock(return_value={"result": "ok"})

    remote = MCPHubAndroidRemote(
        mock_adb_coordinator,
        mock_client,
        mock_config_entry,
        {"serial": "192.168.1.85:5555", "model": "Smart_TV_Pro", "state": "device"},
    )

    # Test mapped command (home) and custom command (KEYCODE_TV_INPUT)
    await remote.async_send_command(["home", "KEYCODE_TV_INPUT"])

    assert mock_client.async_call_tool.call_count == 2
    mock_client.async_call_tool.assert_any_call(
        "android-adb",
        "adb_keyevent",
        {"device": "192.168.1.85:5555", "keycode": "HOME"},
    )
    mock_client.async_call_tool.assert_any_call(
        "android-adb",
        "adb_keyevent",
        {"device": "192.168.1.85:5555", "keycode": "KEYCODE_TV_INPUT"},
    )


async def test_remote_turn_on_off(
    hass: MagicMock,
    mock_config_entry: MagicMock,
    mock_client: MagicMock,
    mock_adb_coordinator: MagicMock,
) -> None:
    """Test remote power control."""
    mock_client.async_call_tool = AsyncMock(return_value={"result": "ok"})

    remote = MCPHubAndroidRemote(
        mock_adb_coordinator,
        mock_client,
        mock_config_entry,
        {"serial": "192.168.1.85:5555", "model": "Smart_TV_Pro", "state": "device"},
    )

    await remote.async_turn_off()
    assert remote.is_on is False

    await remote.async_turn_on()
    assert remote.is_on is True
