"""Tests for MCPHub binary sensors."""

import pytest

from custom_components.mcphub.binary_sensor import async_setup_entry
from custom_components.mcphub.const import (
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
)
from custom_components.mcphub.coordinator import MCPHubCoordinator


@pytest.mark.asyncio
async def test_binary_sensor_setup(hass, mock_client, mock_config_entry) -> None:
    """Test setup of MCPHub binary sensors."""
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

    assert len(added_entities) >= 3

    gateway_bin = [
        e
        for e in added_entities
        if getattr(e, "entity_description", None)
        and e.entity_description.key == "connectivity"
    ][0]
    assert gateway_bin.is_on is True
