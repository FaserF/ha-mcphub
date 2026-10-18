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
