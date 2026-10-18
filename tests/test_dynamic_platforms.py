"""Tests for dynamic text, number, update, and image platforms."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.mcphub.image import async_setup_entry as async_setup_image
from custom_components.mcphub.number import async_setup_entry as async_setup_number
from custom_components.mcphub.text import async_setup_entry as async_setup_text
from custom_components.mcphub.update import async_setup_entry as async_setup_update


@pytest.mark.asyncio
async def test_dynamic_text_platform(hass: HomeAssistant) -> None:
    """Test text entity creation and invocation."""
    coordinator = MagicMock()
    coordinator.data = {
        "servers": [
            {
                "name": "github",
                "status": "connected",
                "tools": [
                    {
                        "name": "github-search_repositories",
                        "description": "Search repos",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                            },
                            "required": ["query"],
                        },
                    }
                ],
            }
        ]
    }
    client = MagicMock()
    client.async_call_tool = AsyncMock(return_value={"repositories": []})

    entry = MagicMock()
    entry.entry_id = "test_text_entry"
    entry.data = {}
    entry.options = {}

    hass.data.setdefault("mcphub", {})[entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    added_entities = []
    await async_setup_text(
        hass, entry, lambda entities: added_entities.extend(entities)
    )

    assert len(added_entities) == 1
    text_entity = added_entities[0]
    text_entity.hass = hass
    text_entity.async_write_ha_state = MagicMock()

    await text_entity.async_set_value("homeassistant")
    assert text_entity.native_value == "homeassistant"
    client.async_call_tool.assert_called_once_with(
        server="github",
        tool_name="github-search_repositories",
        arguments={"query": "homeassistant"},
    )


@pytest.mark.asyncio
async def test_dynamic_number_platform(hass: HomeAssistant) -> None:
    """Test number entity creation and invocation."""
    coordinator = MagicMock()
    coordinator.data = {
        "servers": [
            {
                "name": "shielddns",
                "status": "connected",
                "tools": [
                    {
                        "name": "shielddns-get_queries",
                        "description": "Get query log",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "limit": {
                                    "type": "integer",
                                    "minimum": 10,
                                    "maximum": 500,
                                    "default": 50,
                                },
                            },
                            "required": ["limit"],
                        },
                    }
                ],
            }
        ]
    }
    client = MagicMock()
    client.async_call_tool = AsyncMock(return_value={"queries": []})

    entry = MagicMock()
    entry.entry_id = "test_number_entry"
    entry.data = {}
    entry.options = {}

    hass.data.setdefault("mcphub", {})[entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    added_entities = []
    await async_setup_number(
        hass, entry, lambda entities: added_entities.extend(entities)
    )

    assert len(added_entities) == 1
    number_entity = added_entities[0]
    number_entity.hass = hass
    number_entity.async_write_ha_state = MagicMock()

    await number_entity.async_set_native_value(100)
    assert number_entity.native_value == 100
    client.async_call_tool.assert_called_once_with(
        server="shielddns",
        tool_name="shielddns-get_queries",
        arguments={"limit": 100},
    )


@pytest.mark.asyncio
async def test_dynamic_update_platform(hass: HomeAssistant) -> None:
    """Test update entity creation and install invocation."""
    coordinator = MagicMock()
    coordinator.async_request_refresh = AsyncMock()
    coordinator.data = {
        "servers": [
            {
                "name": "jarvis",
                "status": "connected",
                "version": "1.2.3",
                "tools": [
                    {
                        "name": "jarvis-jarvis_check_update",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "jarvis-jarvis_trigger_update",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ],
            }
        ]
    }
    client = MagicMock()
    client.async_call_tool = AsyncMock(return_value={"status": "updating"})

    entry = MagicMock()
    entry.entry_id = "test_update_entry"
    entry.data = {}
    entry.options = {}

    hass.data.setdefault("mcphub", {})[entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    added_entities = []
    await async_setup_update(
        hass, entry, lambda entities: added_entities.extend(entities)
    )

    assert len(added_entities) == 1
    update_entity = added_entities[0]
    assert update_entity.installed_version == "1.2.3"

    await update_entity.async_install(version=None, backup=False)
    client.async_call_tool.assert_called_once_with(
        server="jarvis",
        tool_name="jarvis-jarvis_trigger_update",
        arguments={},
    )


@pytest.mark.asyncio
async def test_dynamic_image_platform(hass: HomeAssistant) -> None:
    """Test image entity creation and fetching."""
    coordinator = MagicMock()
    coordinator.data = {
        "servers": [
            {
                "name": "playwright",
                "status": "connected",
                "tools": [
                    {
                        "name": "playwright-browser_take_screenshot",
                        "inputSchema": {"type": "object", "properties": {}},
                    }
                ],
            }
        ]
    }
    client = MagicMock()
    # Mock base64 image data (1x1 transparent png)
    b64_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAA="
    client.async_call_tool = AsyncMock(
        return_value={"content": [{"type": "image", "data": b64_data}]}
    )

    entry = MagicMock()
    entry.entry_id = "test_image_entry"
    entry.data = {}
    entry.options = {}

    hass.data.setdefault("mcphub", {})[entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    added_entities = []
    await async_setup_image(
        hass, entry, lambda entities: added_entities.extend(entities)
    )

    assert len(added_entities) == 1
    image_entity = added_entities[0]
    img_bytes = await image_entity.async_image()
    assert img_bytes is not None
    assert len(img_bytes) > 0
