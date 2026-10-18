"""Tests for MCPHub config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.mcphub.client import CannotConnect, InvalidAuth
from custom_components.mcphub.config_flow import MCPHubConfigFlow
from custom_components.mcphub.const import (
    CONF_API_KEY,
    CONF_API_URL,
    CONF_AUTO_IMPORT_NEW,
    CONF_DEFAULT_GROUP,
    CONF_ENABLED_SERVERS,
    DEFAULT_API_URL,
)


@pytest.mark.asyncio
async def test_flow_user_step_success(hass) -> None:
    """Test successful user step proceeding to servers step."""
    flow = MCPHubConfigFlow()
    flow.hass = hass

    with patch(
        "custom_components.mcphub.client.MCPHubClient.async_get_servers",
        new_callable=AsyncMock,
        return_value=[
            {"name": "finance", "status": "connected", "tools": ["t1"]},
            {"name": "openwrt", "status": "connected", "tools": ["t2"]},
        ],
    ):
        result = await flow.async_step_user(
            {
                CONF_API_URL: DEFAULT_API_URL,
                CONF_API_KEY: "valid_token",
                CONF_DEFAULT_GROUP: "$smart",
            }
        )

    assert result["type"] == "form"
    assert result["step_id"] == "servers"

    # Now submit servers selection
    result2 = await flow.async_step_servers(
        {
            CONF_AUTO_IMPORT_NEW: True,
            CONF_ENABLED_SERVERS: ["finance"],
        }
    )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "MCPHub Gateway"
    assert result2["data"][CONF_API_URL] == DEFAULT_API_URL
    assert result2["data"][CONF_ENABLED_SERVERS] == ["finance"]


@pytest.mark.asyncio
async def test_flow_user_step_invalid_auth(hass) -> None:
    """Test user step with invalid authentication."""
    flow = MCPHubConfigFlow()
    flow.hass = hass

    with patch(
        "custom_components.mcphub.client.MCPHubClient.async_get_servers",
        side_effect=InvalidAuth,
    ):
        result = await flow.async_step_user(
            {
                CONF_API_URL: DEFAULT_API_URL,
                CONF_API_KEY: "wrong_token",
                CONF_DEFAULT_GROUP: "$smart",
            }
        )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "invalid_auth"


@pytest.mark.asyncio
async def test_flow_user_step_cannot_connect(hass) -> None:
    """Test user step with connection error."""
    flow = MCPHubConfigFlow()
    flow.hass = hass

    with patch(
        "custom_components.mcphub.client.MCPHubClient.async_get_servers",
        side_effect=CannotConnect,
    ):
        result = await flow.async_step_user(
            {
                CONF_API_URL: DEFAULT_API_URL,
                CONF_API_KEY: "token",
                CONF_DEFAULT_GROUP: "$smart",
            }
        )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "cannot_connect"
