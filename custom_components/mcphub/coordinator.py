"""DataUpdateCoordinator for MCPHub with dynamic custom mapping support."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import CannotConnect, InvalidAuth, MCPHubClient
from .const import DEFAULT_POLL_INTERVAL, DOMAIN
from .custom_mapping import (
    async_poll_mapped_devices,
    get_default_device_mappings,
    load_mappings_from_entry,
)

_LOGGER = logging.getLogger(__name__)


class MCPHubCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching MCPHub data from the centralized server."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: MCPHubClient,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.config_entry = config_entry
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_interval),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch status overview and poll all active custom mapped devices."""
        try:
            data = await self.client.async_get_status_overview()
        except InvalidAuth as err:
            raise UpdateFailed(f"Authentication error updating MCPHub: {err}") from err
        except CannotConnect as err:
            raise UpdateFailed(f"Connection error updating MCPHub: {err}") from err
        except Exception as err:
            raise UpdateFailed(
                f"Unexpected error communicating with MCPHub: {err}"
            ) from err

        mappings = (
            load_mappings_from_entry(self.config_entry)
            if self.config_entry
            else get_default_device_mappings()
        )
        connected_servers = {
            s.get("name")
            for s in data.get("servers", [])
            if isinstance(s, dict) and s.get("status") == "connected"
        }

        mapped_data = await async_poll_mapped_devices(
            self.client, mappings, connected_servers
        )
        data["mapped_data"] = mapped_data

        # Backward compatibility for legacy ADB queries
        adb_res = mapped_data.get("android_adb")
        if isinstance(adb_res, dict) and "devices" in adb_res:
            data["adb_devices"] = adb_res["devices"]
        else:
            data["adb_devices"] = []

        return data
