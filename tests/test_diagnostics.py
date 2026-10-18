"""Tests for MCPHub diagnostics."""

from unittest.mock import MagicMock

import pytest

from custom_components.mcphub.const import (
    DATA_COORDINATOR,
    DOMAIN,
)
from custom_components.mcphub.diagnostics import async_get_config_entry_diagnostics


@pytest.mark.asyncio
async def test_diagnostics(hass, mock_config_entry) -> None:
    """Test diagnostics generation and redaction."""
    coordinator = MagicMock()
    coordinator.data = {"total_servers": 2, "servers": []}
    coordinator.last_update_success = True

    hass.data = {
        DOMAIN: {
            mock_config_entry.entry_id: {
                DATA_COORDINATOR: coordinator,
            }
        }
    }

    diag = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert diag["entry"]["api_key"] == "REDACTED"
    assert diag["coordinator_data"]["total_servers"] == 2
