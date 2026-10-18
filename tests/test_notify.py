"""Tests for MCPHub dynamic notify entities."""

import pytest

from custom_components.mcphub.const import (
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
)
from custom_components.mcphub.coordinator import MCPHubCoordinator
from custom_components.mcphub.notify import async_setup_entry


@pytest.mark.asyncio
async def test_notify_setup_and_send(hass, mock_client, mock_config_entry) -> None:
    """Test dynamic notify entity creation for messaging tools."""
    mock_client.async_get_status_overview.return_value = {
        "latency_ms": 10.0,
        "total_servers": 1,
        "connected_servers": 1,
        "total_tools": 1,
        "servers": [
            {
                "name": "rocketchat",
                "version": "1.0.0",
                "status": "connected",
                "enabled": True,
                "tools": [
                    {
                        "name": "rocketchat-rocketchat_post_message",
                        "description": "Send a message to a Rocket.Chat channel",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "room": {"type": "string"},
                                "text": {"type": "string"},
                                "confirm": {"type": "boolean"},
                            },
                            "required": ["room", "text", "confirm"],
                        },
                    }
                ],
            }
        ],
    }

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

    assert len(added_entities) == 1
    notify_ent = added_entities[0]
    assert "Notify (Post Message)" == notify_ent.name

    await notify_ent.async_send_message(
        "Test hello from Home Assistant!", data={"room": "general"}
    )
    assert mock_client.async_call_tool.called
