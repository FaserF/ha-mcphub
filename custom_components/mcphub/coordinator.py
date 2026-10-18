"""DataUpdateCoordinator for MCPHub."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import CannotConnect, InvalidAuth, MCPHubClient
from .const import DEFAULT_POLL_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class MCPHubCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching MCPHub data from the centralized server."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: MCPHubClient,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_interval),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch status overview and all servers from MCPHub."""
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

        # Check if android-adb server is registered and connected
        servers = data.get("servers", [])
        has_adb = any(
            isinstance(s, dict)
            and s.get("name") == "android-adb"
            and s.get("status") == "connected"
            for s in servers
        )

        data["adb_devices"] = []
        if has_adb:
            try:
                res = await self.client.async_call_tool(
                    "android-adb", "adb_devices", {}
                )
                raw_text = ""
                content = res.get("content", []) if isinstance(res, dict) else []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        raw_text = item.get("text", "")
                        break
                if raw_text:
                    import json

                    parsed_devs = json.loads(raw_text)
                    data["adb_devices"] = parsed_devs.get("devices", [])
                elif isinstance(res, dict) and "devices" in res:
                    data["adb_devices"] = res.get("devices", [])
            except Exception as err:
                _LOGGER.debug(
                    "Non-fatal error querying adb_devices from android-adb: %s", err
                )

        return data
