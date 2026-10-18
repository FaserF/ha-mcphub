"""Tests for MCPHub button entities."""

import pytest

from custom_components.mcphub.button import async_setup_entry
from custom_components.mcphub.const import (
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
)
from custom_components.mcphub.coordinator import MCPHubCoordinator


@pytest.mark.asyncio
async def test_button_setup_and_press(hass, mock_client, mock_config_entry) -> None:
    """Test setup and press of MCPHub buttons."""
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

    assert len(added_entities) >= 4

    clear_btn = [
        e
        for e in added_entities
        if getattr(e, "entity_description", None)
        and e.entity_description.key == "clear_cache"
    ][0]
    await clear_btn.async_press()
    assert mock_client.async_clear_cache.called
