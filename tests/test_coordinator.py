"""Tests for MCPHub coordinator."""

from unittest.mock import AsyncMock

import pytest

from custom_components.mcphub.client import CannotConnect
from custom_components.mcphub.coordinator import MCPHubCoordinator


@pytest.mark.asyncio
async def test_coordinator_update_success(hass, mock_client) -> None:
    """Test successful coordinator data update."""
    coordinator = MCPHubCoordinator(hass, mock_client)
    data = await coordinator._async_update_data()

    assert data["total_servers"] == 2
    assert data["connected_servers"] == 2
    assert data["total_tools"] == 2


@pytest.mark.asyncio
async def test_coordinator_update_failure(hass, mock_client) -> None:
    """Test coordinator update failure handling."""
    mock_client.async_get_status_overview = AsyncMock(
        side_effect=CannotConnect("Conn err")
    )
    coordinator = MCPHubCoordinator(hass, mock_client)

    from homeassistant.helpers.update_coordinator import UpdateFailed

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
