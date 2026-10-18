"""Dynamic select entities for MCPHub tools with enumerated options."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .client import MCPHubClient
from .const import (
    ATTR_SERVERS,
    CONF_AUTO_IMPORT_NEW,
    CONF_ENABLED_SERVERS,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DEFAULT_AUTO_IMPORT_NEW,
    DOMAIN,
)
from .coordinator import MCPHubCoordinator
from .helpers import get_server_device_info

_LOGGER = logging.getLogger(__name__)


def _is_server_enabled(entry: ConfigEntry, server_name: str) -> bool:
    """Check if server is enabled by user configuration."""
    auto_import = entry.options.get(
        CONF_AUTO_IMPORT_NEW,
        entry.data.get(CONF_AUTO_IMPORT_NEW, DEFAULT_AUTO_IMPORT_NEW),
    )
    enabled_servers = entry.options.get(
        CONF_ENABLED_SERVERS,
        entry.data.get(CONF_ENABLED_SERVERS),
    )
    if enabled_servers is None:
        return True
    if server_name in enabled_servers:
        return True
    return auto_import and (server_name not in enabled_servers)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up dynamic MCPHub select platform."""
    coordinator: MCPHubCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    client: MCPHubClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]

    entities: list[SelectEntity] = []

    for server in coordinator.data.get("servers", []):
        server_name = server.get("name", "")
        if not server_name or not _is_server_enabled(entry, server_name):
            continue

        tools = server.get("tools", [])
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            schema = tool.get("inputSchema") or {}
            props = schema.get("properties", {})
            req_params = schema.get("required", [])

            # Identify parameters with enum choices
            for param_name, param_def in props.items():
                if not isinstance(param_def, dict):
                    continue
                enum_opts = param_def.get("enum")
                if not enum_opts or not isinstance(enum_opts, list):
                    continue

                # Only create select entity if this parameter is the sole required param (or no required params)
                other_req = [p for p in req_params if p != param_name]
                if other_req:
                    continue

                string_opts = [str(opt) for opt in enum_opts]
                entities.append(
                    MCPHubDynamicToolSelect(
                        coordinator=coordinator,
                        client=client,
                        entry=entry,
                        server_name=server_name,
                        tool=tool,
                        param_name=param_name,
                        options=string_opts,
                    )
                )

    async_add_entities(entities)


class MCPHubDynamicToolSelect(CoordinatorEntity[MCPHubCoordinator], SelectEntity):
    """Dynamic select entity triggering an MCP tool action with an enum option."""

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        client: MCPHubClient,
        entry: ConfigEntry,
        server_name: str,
        tool: dict[str, Any],
        param_name: str,
        options: list[str],
    ) -> None:
        """Initialize the dynamic tool select entity."""
        super().__init__(coordinator)
        self._client = client
        self._server_name = server_name
        self._tool = tool
        self._param_name = param_name
        self._attr_options = options
        self._current_option: str | None = options[0] if options else None

        tool_name = tool.get("name", "")
        clean_name = (
            tool_name.replace(f"{server_name}-", "")
            .replace(f"{server_name}_", "")
            .replace("_", " ")
            .title()
        )
        param_clean = param_name.replace("_", " ").title()

        self.entity_description = SelectEntityDescription(
            key=f"{tool_name}_{param_name}",
            name=f"{clean_name} ({param_clean})",
            icon="mdi:form-select",
        )
        self._attr_unique_id = (
            f"{entry.entry_id}_{server_name}_{tool_name}_{param_name}"
        )
        self._attr_has_entity_name = True

        server_data = self._get_server_data() or {}
        self._attr_device_info = get_server_device_info(entry, server_name, server_data)

    def _get_server_data(self) -> dict[str, Any] | None:
        """Get the latest data for this server."""
        if not self.coordinator.data:
            return None
        for server in self.coordinator.data.get(ATTR_SERVERS, []):
            if server.get("name") == self._server_name:
                return server
        return None

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return self._current_option

    async def async_select_option(self, option: str) -> None:
        """Change the selected option and execute the MCP tool."""
        if option not in self.options:
            raise ValueError(
                f"Invalid option: {option}. Expected one of {self.options}"
            )

        self._current_option = option
        self.async_write_ha_state()

        tool_name = self._tool.get("name", "")
        args = {self._param_name: option}
        _LOGGER.info(
            "Executing MCP tool select '%s' on '%s' with argument: %s",
            tool_name,
            self._server_name,
            args,
        )
        try:
            res = await self._client.async_call_tool(
                server=self._server_name,
                tool_name=tool_name,
                arguments=args,
            )
            _LOGGER.debug("Select tool result: %s", res)
        except Exception as err:
            _LOGGER.error("Failed to execute select tool '%s': %s", tool_name, err)
            raise
