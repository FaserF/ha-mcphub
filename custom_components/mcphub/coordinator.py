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
            return await self.client.async_get_status_overview()
        except InvalidAuth as err:
            raise UpdateFailed(f"Authentication error updating MCPHub: {err}") from err
        except CannotConnect as err:
            raise UpdateFailed(f"Connection error updating MCPHub: {err}") from err
        except Exception as err:
            raise UpdateFailed(
                f"Unexpected error communicating with MCPHub: {err}"
            ) from err
