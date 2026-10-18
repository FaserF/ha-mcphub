"""Diagnostics support for MCPHub."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_API_KEY, CONF_API_URL, DATA_COORDINATOR, DOMAIN
from .coordinator import MCPHubCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: MCPHubCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    # Redact sensitive information
    data = coordinator.data.copy() if coordinator.data else {}
    sanitized_entry_data = {
        CONF_API_URL: entry.data.get(CONF_API_URL),
        CONF_API_KEY: "REDACTED" if entry.data.get(CONF_API_KEY) else None,
    }

    return {
        "entry": sanitized_entry_data,
        "options": dict(entry.options),
        "coordinator_data": data,
        "last_update_success": coordinator.last_update_success,
    }
