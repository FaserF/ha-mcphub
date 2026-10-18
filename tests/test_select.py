"""Tests for MCPHub select platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.mcphub.const import DOMAIN
from custom_components.mcphub.select import (
    MCPHubDynamicToolSelect,
    async_setup_entry,
)


@pytest.mark.asyncio
async def test_dynamic_select_setup_and_execution(hass: HomeAssistant) -> None:
    """Test dynamic select discovery and option execution."""
    coordinator = MagicMock()
    coordinator.data = {
        "servers": [
            {
                "name": "jarvis",
                "status": "connected",
                "tools": [
                    {
                        "name": "jarvis-jarvis_restart",
                        "description": "Restart jarvis with method",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "method": {
                                    "type": "string",
                                    "enum": ["soft", "hard", "graceful"],
                                }
                            },
                            "required": ["method"],
                        },
                    }
                ],
            }
        ]
    }
    client = MagicMock()
    client.async_call_tool = AsyncMock(return_value={"status": "restarted"})

    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {}
    entry.options = {}

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    added_entities: list[MCPHubDynamicToolSelect] = []

    def mock_add_entities(entities: list[MCPHubDynamicToolSelect]) -> None:
        added_entities.extend(entities)

    await async_setup_entry(hass, entry, mock_add_entities)

    assert len(added_entities) == 1
    select_entity = added_entities[0]
    assert select_entity.options == ["soft", "hard", "graceful"]
    assert select_entity.current_option == "soft"

    select_entity.hass = hass
    select_entity.async_write_ha_state = MagicMock()

    await select_entity.async_select_option("graceful")

    assert select_entity.current_option == "graceful"
    client.async_call_tool.assert_called_once_with(
        server="jarvis",
        tool_name="jarvis-jarvis_restart",
        arguments={"method": "graceful"},
    )
