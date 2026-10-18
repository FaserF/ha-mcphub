"""Tests for MCPHub switch entities."""

import pytest

from custom_components.mcphub.const import (
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
)
from custom_components.mcphub.coordinator import MCPHubCoordinator
from custom_components.mcphub.switch import async_setup_entry


@pytest.mark.asyncio
async def test_switch_setup_and_toggle(hass, mock_client, mock_config_entry) -> None:
    """Test setup and toggle of server enable switches."""
    coordinator = MCPHubCoordinator(hass, mock_client)
    await coordinator.async_refresh()

    hass.data = {
        DOMAIN: {
            mock_config_entry.entry_id: {
                DATA_COORDINATOR: coordinator,
                DATA_CLIENT: mock_client,
            }
        }
    }

    added_entities = []

    def mock_add_entities(entities):
        added_entities.extend(entities)

    await async_setup_entry(hass, mock_config_entry, mock_add_entities)

    assert len(added_entities) == 2

    switch = added_entities[0]
    assert switch.is_on is True

    await switch.async_turn_off()
    assert mock_client.async_toggle_server.called


@pytest.mark.asyncio
async def test_dynamic_tool_switch(hass, mock_client, mock_config_entry) -> None:
    """Test dynamic tool boolean switch creation and state change."""
    coordinator = MCPHubCoordinator(hass, mock_client)
    coordinator.data = {
        "servers": [
            {
                "name": "shielddns",
                "status": "connected",
                "tools": [
                    {
                        "name": "shielddns-toggle_global_filtering",
                        "description": "Toggle global DNS filtering",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "enabled": {"type": "boolean"},
                            },
                            "required": ["enabled"],
                        },
                    }
                ],
            }
        ]
    }

    hass.data = {
        DOMAIN: {
            mock_config_entry.entry_id: {
                DATA_COORDINATOR: coordinator,
                DATA_CLIENT: mock_client,
            }
        }
    }

    added_entities = []

    def mock_add_entities(entities):
        added_entities.extend(entities)

    await async_setup_entry(hass, mock_config_entry, mock_add_entities)

    assert len(added_entities) == 2  # Server enable switch + dynamic tool switch
    tool_switch = added_entities[1]
    tool_switch.hass = hass
    tool_switch.async_write_ha_state = lambda: None

    assert tool_switch.is_on is False

    await tool_switch.async_turn_on()
    assert tool_switch.is_on is True
    mock_client.async_call_tool.assert_called_with(
        server="shielddns",
        tool_name="shielddns-toggle_global_filtering",
        arguments={"enabled": True},
    )

    await tool_switch.async_turn_off()
    assert tool_switch.is_on is False
    mock_client.async_call_tool.assert_called_with(
        server="shielddns",
        tool_name="shielddns-toggle_global_filtering",
        arguments={"enabled": False},
    )
