"""Config flow for MCPHub integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import CannotConnect, InvalidAuth, MCPHubClient
from .const import (
    CONF_API_KEY,
    CONF_API_URL,
    CONF_DEFAULT_GROUP,
    CONF_POLL_INTERVAL,
    DEFAULT_API_URL,
    DEFAULT_DEFAULT_GROUP,
    DEFAULT_NAME,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_URL, default=DEFAULT_API_URL): str,
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_DEFAULT_GROUP, default=DEFAULT_DEFAULT_GROUP): str,
    }
)


class MCPHubConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MCPHub."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_url = user_input[CONF_API_URL].rstrip("/")
            api_key = user_input[CONF_API_KEY].strip()

            await self.async_set_unique_id(api_url)
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            client = MCPHubClient(api_url, api_key, session=session)

            try:
                await client.async_get_servers()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception in MCPHub config flow")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Create the options flow."""
        return MCPHubOptionsFlowHandler(config_entry)


class MCPHubOptionsFlowHandler(OptionsFlow):
    """Handle options flow for MCPHub."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_poll = self.config_entry.options.get(
            CONF_POLL_INTERVAL,
            self.config_entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        )
        current_group = self.config_entry.options.get(
            CONF_DEFAULT_GROUP,
            self.config_entry.data.get(CONF_DEFAULT_GROUP, DEFAULT_DEFAULT_GROUP),
        )

        options_schema = vol.Schema(
            {
                vol.Optional(CONF_POLL_INTERVAL, default=current_poll): int,
                vol.Optional(CONF_DEFAULT_GROUP, default=current_group): str,
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema)
