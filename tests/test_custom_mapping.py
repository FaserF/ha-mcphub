"""Tests for custom mapping engine and IPP printer support."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.media_player import MediaPlayerDeviceClass, MediaPlayerState
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from custom_components.mcphub.const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN
from custom_components.mcphub.custom_mapping import (
    DEFAULT_ADB_MAPPING_DICT,
    DEFAULT_PRINTER_MAPPING_DICT,
    DeviceMapping,
    extract_device_info,
    extract_mac_connections,
    get_default_device_mappings,
    get_nested_value,
    render_args_template,
    render_template_str,
)
from custom_components.mcphub.sensor import MCPHubMappedSensor
from custom_components.mcphub.switch import MCPHubMappedSwitch


def test_custom_mapping_models_and_defaults() -> None:
    """Test parsing and serialization of default mappings."""
    defaults = get_default_device_mappings()
    assert len(defaults) >= 2

    adb_map = next(m for m in defaults if m.id == "android_adb")
    assert adb_map.server_name == "android-adb"
    assert adb_map.is_multi_device is True

    printer_map = next(m for m in defaults if m.id == "printer_ipp")
    assert printer_map.server_name == "printer"
    assert printer_map.is_multi_device is False
    assert len(printer_map.entities) >= 5


def test_get_nested_value_and_templates() -> None:
    """Test nested value retrieval and template rendering."""
    data = {
        "device": {"name": "Test Device", "serial": "192.168.1.26"},
        "counters": {"pages": 1234},
        "items": [{"level": 85}],
    }
    assert get_nested_value(data, "device.name") == "Test Device"
    assert get_nested_value(data, "counters.pages") == 1234
    assert get_nested_value(data, "items.0.level") == 85
    assert get_nested_value(data, "nonexistent.key", "default") == "default"

    assert (
        render_template_str("Hello {{ device.name }}!", data)
        == "Hello Test Device!"
    )
    rendered_args = render_args_template(
        {"target": "{{ device.serial }}", "count": 5},
        data,
    )
    assert rendered_args["target"] == "192.168.1.26"
    assert rendered_args["count"] == 5


def test_extract_mac_connections() -> None:
    """Test MAC address extraction and formatting."""
    from homeassistant.helpers.device_registry import format_mac
    if hasattr(format_mac, "side_effect"):
        format_mac.side_effect = lambda m: str(m).lower()

    macs = ["DC:72:23:9D:EC:19", "invalid", ""]
    conns = extract_mac_connections(macs)
    assert (CONNECTION_NETWORK_MAC, "dc:72:23:9d:ec:19") in conns


def test_printer_device_info_and_sensor_offline(mock_config_entry: MagicMock) -> None:
    """Test IPP printer device info extraction and graceful offline handling."""
    from homeassistant.helpers.device_registry import format_mac
    if hasattr(format_mac, "side_effect"):
        format_mac.side_effect = lambda m: str(m).lower()
    printer_map = DeviceMapping.from_dict(DEFAULT_PRINTER_MAPPING_DICT)
    status_entity_cfg = next(e for e in printer_map.entities if e.key == "printer_status")
    marker_entity_cfg = next(e for e in printer_map.entities if e.key == "marker")

    offline_payload = {
        "online": False,
        "power": "off",
        "state": "offline",
        "state_message": "Printer is powered off",
        "state_reasons": ["offline"],
        "name": "HP LaserJet MFP M426fdw",
        "manufacturer": "Hewlett-Packard",
        "model": "HP LaserJet MFP M426fdw",
        "uuid": "50484238-4b32-4e36-3646-40b03425836a",
        "mac": "00:11:22:33:44:55",
        "markers": [],
    }

    dev_info = extract_device_info(mock_config_entry, printer_map, offline_payload)
    assert dev_info["manufacturer"] == "Hewlett-Packard"
    assert "LaserJet" in dev_info["model"]
    assert (CONNECTION_NETWORK_MAC, "00:11:22:33:44:55") in dev_info["connections"]

    coordinator = MagicMock()
    coordinator.data = {"mapped_data": {"printer_ipp": offline_payload}}

    # Status sensor when offline
    status_sensor = MCPHubMappedSensor(
        coordinator, mock_config_entry, printer_map, status_entity_cfg, offline_payload
    )
    assert status_sensor.native_value == "offline"
    assert status_sensor.available is True

    # Marker sensor when online
    online_payload = dict(offline_payload)
    online_payload["online"] = True
    online_payload["state"] = "idle"
    online_payload["power"] = "on"
    marker_item = {
        "name": "Black Cartridge HP CF226X",
        "level": 82,
        "high_level": 100,
        "low_level": 10,
        "marker_type": "toner",
        "color": "#000000",
    }
    marker_sensor = MCPHubMappedSensor(
        coordinator,
        mock_config_entry,
        printer_map,
        marker_entity_cfg,
        online_payload,
        collection_item=marker_item,
    )
    assert marker_sensor.name == "Black Cartridge HP CF226X"
    assert marker_sensor.native_value == 82
    assert marker_sensor.extra_state_attributes["marker_type"] == "toner"
    assert marker_sensor.extra_state_attributes["color"] == "#000000"


@pytest.mark.asyncio
async def test_printer_power_switch(
    mock_config_entry: MagicMock, mock_client: MagicMock
) -> None:
    """Test printer power switch mapping and turn on/off actions."""
    mock_client.async_call_tool = AsyncMock(return_value={"result": "ok"})
    printer_map = DeviceMapping.from_dict(DEFAULT_PRINTER_MAPPING_DICT)
    power_entity_cfg = next(e for e in printer_map.entities if e.key == "power")

    dev_data = {
        "uuid": "50484238-4b32-4e36-3646-40b03425836a",
        "power": "off",
    }
    coordinator = MagicMock()
    coordinator.data = {"mapped_data": {"printer_ipp": dev_data}}
    coordinator.async_request_refresh = MagicMock()

    switch = MCPHubMappedSwitch(
        coordinator, mock_client, mock_config_entry, printer_map, power_entity_cfg, dev_data
    )
    assert switch.is_on is False

    await switch.async_turn_on()
    mock_client.async_call_tool.assert_called_with(
        "printer", "printer_power_on", {"wait_for_online": False}
    )
    assert switch.is_on is True

    await switch.async_turn_off()
    mock_client.async_call_tool.assert_called_with(
        "printer", "printer_power_off", {}
    )
    assert switch.is_on is False
