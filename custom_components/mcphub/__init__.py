"""The MCPHub Integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import MCPHubClient
from .const import (
    CONF_API_KEY,
    CONF_API_URL,
    CONF_POLL_INTERVAL,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import MCPHubCoordinator
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MCPHub from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    api_url = entry.data[CONF_API_URL]
    api_key = entry.data.get(CONF_API_KEY)
    poll_interval = entry.options.get(
        CONF_POLL_INTERVAL,
        entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
    )

    session = async_get_clientsession(hass)
    client = MCPHubClient(api_url, api_key, session=session)

    coordinator = MCPHubCoordinator(
        hass, client, poll_interval=poll_interval, config_entry=entry
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CLIENT: client,
        DATA_COORDINATOR: coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_setup_services(hass)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id, {})
        client: MCPHubClient | None = data.get(DATA_CLIENT)
        if client:
            await client.close()
        await async_unload_services(hass)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
