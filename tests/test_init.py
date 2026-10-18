"""Tests for MCPHub integration lifecycle."""

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.mcphub import async_setup_entry, async_unload_entry
from custom_components.mcphub.const import DOMAIN


@pytest.mark.asyncio
async def test_async_setup_and_unload_entry(
    hass, mock_client, mock_config_entry
) -> None:
    """Test full setup and unload of entry."""
    with (
        patch("custom_components.mcphub.MCPHubClient", return_value=mock_client),
        patch("custom_components.mcphub.async_setup_services", new_callable=AsyncMock),
        patch("custom_components.mcphub.async_unload_services", new_callable=AsyncMock),
    ):
        assert await async_setup_entry(hass, mock_config_entry) is True
        assert mock_config_entry.entry_id in hass.data[DOMAIN]

        assert await async_unload_entry(hass, mock_config_entry) is True
        assert mock_config_entry.entry_id not in hass.data[DOMAIN]
