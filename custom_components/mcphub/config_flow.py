"""Config flow and options flow for MCPHub integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import CannotConnect, InvalidAuth, MCPHubClient
from .const import (
    CONF_API_KEY,
    CONF_API_URL,
    CONF_AUTO_IMPORT_NEW,
    CONF_CUSTOM_MAPPINGS,
    CONF_DEFAULT_GROUP,
    CONF_ENABLED_SERVERS,
    CONF_POLL_INTERVAL,
    DEFAULT_API_URL,
    DEFAULT_AUTO_IMPORT_NEW,
    DEFAULT_DEFAULT_GROUP,
    DEFAULT_NAME,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    HACS_DEFAULT_INTEGRATIONS_URL,
    detect_duplicate_conflict,
)

_LOGGER = logging.getLogger(__name__)


class MCPHubConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MCPHub."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._api_url: str | None = None
        self._api_key: str | None = None
        self._default_group: str = DEFAULT_DEFAULT_GROUP
        self._discovered_servers: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial connection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._api_url = user_input[CONF_API_URL].rstrip("/")
            self._api_key = user_input[CONF_API_KEY].strip()
            self._default_group = user_input.get(
                CONF_DEFAULT_GROUP, DEFAULT_DEFAULT_GROUP
            )

            await self.async_set_unique_id(self._api_url)
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            client = MCPHubClient(self._api_url, self._api_key, session=session)

            try:
                self._discovered_servers = await client.async_get_servers()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception connecting to MCPHub")
                errors["base"] = "unknown"
            else:
                return await self.async_step_servers()

        schema = vol.Schema(
            {
                vol.Required(CONF_API_URL, default=DEFAULT_API_URL): str,
                vol.Required(CONF_API_KEY): str,
                vol.Optional(CONF_DEFAULT_GROUP, default=DEFAULT_DEFAULT_GROUP): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_servers(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select which MCP servers to map into Home Assistant devices."""
        if user_input is not None:
            enabled_servers = user_input.get(CONF_ENABLED_SERVERS, [])
            auto_import = user_input.get(CONF_AUTO_IMPORT_NEW, DEFAULT_AUTO_IMPORT_NEW)
            return self.async_create_entry(
                title=DEFAULT_NAME,
                data={
                    CONF_API_URL: self._api_url,
                    CONF_API_KEY: self._api_key,
                    CONF_DEFAULT_GROUP: self._default_group,
                    CONF_AUTO_IMPORT_NEW: auto_import,
                    CONF_ENABLED_SERVERS: enabled_servers,
                },
            )

        # Try to fetch live HACS default integrations list with timeout
        hacs_catalog: list[str] | None = None
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(HACS_DEFAULT_INTEGRATIONS_URL, timeout=3) as resp:
                if resp.status == 200:
                    hacs_catalog = await resp.json(content_type=None)
        except Exception as err:
            _LOGGER.debug("Could not fetch live HACS catalog: %s", err)

        # Build options dictionary for multiselect
        server_options: dict[str, str] = {}
        defaults: list[str] = []

        for server in self._discovered_servers:
            name = server.get("name", "")
            if not name:
                continue
            tools_cnt = len(server.get("tools", []))
            conflict_desc = detect_duplicate_conflict(name, hacs_catalog)
            dup_notice = f" ⚠️ ({conflict_desc})" if conflict_desc else ""
            server_options[name] = f"{name} ({tools_cnt} Tools){dup_notice}"

            # Only select by default if NOT known duplicate and connected
            if not conflict_desc and server.get("status") == "connected":
                defaults.append(name)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_AUTO_IMPORT_NEW, default=DEFAULT_AUTO_IMPORT_NEW
                ): bool,
                vol.Optional(
                    CONF_ENABLED_SERVERS,
                    default=defaults,
                ): cv.multi_select(server_options),
            }
        )

        return self.async_show_form(
            step_id="servers",
            data_schema=schema,
            description_placeholders={
                "server_count": str(len(self._discovered_servers)),
            },
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
    ) -> ConfigFlowResult:
        """Manage global and per-server options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            raw_mappings = user_input.get(CONF_CUSTOM_MAPPINGS)
            if raw_mappings:
                import json
                try:
                    parsed = json.loads(raw_mappings)
                    if not isinstance(parsed, list):
                        errors[CONF_CUSTOM_MAPPINGS] = "invalid_json_list"
                    else:
                        user_input[CONF_CUSTOM_MAPPINGS] = parsed
                except Exception:
                    errors[CONF_CUSTOM_MAPPINGS] = "invalid_json"

            if not errors:
                return self.async_create_entry(title="", data=user_input)

        current_poll = self.config_entry.options.get(
            CONF_POLL_INTERVAL,
            self.config_entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        )
        current_group = self.config_entry.options.get(
            CONF_DEFAULT_GROUP,
            self.config_entry.data.get(CONF_DEFAULT_GROUP, DEFAULT_DEFAULT_GROUP),
        )
        auto_import = self.config_entry.options.get(
            CONF_AUTO_IMPORT_NEW,
            self.config_entry.data.get(CONF_AUTO_IMPORT_NEW, DEFAULT_AUTO_IMPORT_NEW),
        )
        current_enabled = self.config_entry.options.get(
            CONF_ENABLED_SERVERS,
            self.config_entry.data.get(CONF_ENABLED_SERVERS, []),
        )

        import json
        from .custom_mapping import DEFAULT_MAPPINGS

        current_mappings = self.config_entry.options.get(
            CONF_CUSTOM_MAPPINGS,
            self.config_entry.data.get(CONF_CUSTOM_MAPPINGS),
        )
        if current_mappings is None:
            current_mappings_str = json.dumps(DEFAULT_MAPPINGS, indent=2)
        elif isinstance(current_mappings, (list, dict)):
            current_mappings_str = json.dumps(current_mappings, indent=2)
        else:
            current_mappings_str = str(current_mappings)

        # Get discovered servers from coordinator if available
        domain_data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id, {})
        coordinator = domain_data.get("coordinator")
        servers = (
            coordinator.data.get("servers", [])
            if coordinator and coordinator.data
            else []
        )

        server_options: dict[str, str] = {}
        for s in servers:
            name = s.get("name", "")
            if not name:
                continue
            tools_cnt = len(s.get("tools", []))
            conflict_desc = detect_duplicate_conflict(name)
            dup = f" ⚠️ ({conflict_desc})" if conflict_desc else ""
            server_options[name] = f"{name} ({tools_cnt} Tools){dup}"

        if not server_options:
            for name in current_enabled:
                server_options[name] = name

        schema = vol.Schema(
            {
                vol.Optional(CONF_POLL_INTERVAL, default=current_poll): int,
                vol.Optional(CONF_DEFAULT_GROUP, default=current_group): str,
                vol.Optional(CONF_AUTO_IMPORT_NEW, default=auto_import): bool,
                vol.Optional(
                    CONF_ENABLED_SERVERS, default=current_enabled
                ): cv.multi_select(server_options),
                vol.Optional(
                    CONF_CUSTOM_MAPPINGS, default=current_mappings_str
                ): cv.string,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
