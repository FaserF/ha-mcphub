"""Dynamic number entities for MCPHub numerical parameter tools."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberEntityDescription
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
    """Set up dynamic MCPHub number entities."""
    coordinator: MCPHubCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    client: MCPHubClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]

    entities: list[NumberEntity] = []

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

            # Check for single integer/number parameter
            num_props = [
                k
                for k, v in props.items()
                if isinstance(v, dict) and v.get("type") in ("integer", "number")
            ]
            if len(num_props) == 1 and (not req_params or req_params == num_props):
                param_name = num_props[0]
                param_def = props[param_name]
                min_val = float(param_def.get("minimum", 0))
                max_val = float(param_def.get("maximum", 1000))
                step = 1.0 if param_def.get("type") == "integer" else 0.1
                default_val = float(param_def.get("default", min_val))

                entities.append(
                    MCPHubDynamicToolNumber(
                        coordinator=coordinator,
                        client=client,
                        entry=entry,
                        server_name=server_name,
                        tool=tool,
                        param_name=param_name,
                        min_value=min_val,
                        max_value=max_val,
                        step=step,
                        default_value=default_val,
                    )
                )

    async_add_entities(entities)


class MCPHubDynamicToolNumber(CoordinatorEntity[MCPHubCoordinator], NumberEntity):
    """Dynamic number entity that triggers an MCP tool on value adjustment."""

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        client: MCPHubClient,
        entry: ConfigEntry,
        server_name: str,
        tool: dict[str, Any],
        param_name: str,
        min_value: float,
        max_value: float,
        step: float,
        default_value: float,
    ) -> None:
        """Initialize dynamic number entity."""
        super().__init__(coordinator)
        self._client = client
        self._server_name = server_name
        self._tool = tool
        self._param_name = param_name
        self._value = default_value

        tool_name = tool.get("name", "")
        clean_name = (
            tool_name.replace(f"{server_name}-", "")
            .replace(f"{server_name}_", "")
            .replace("_", " ")
            .title()
        )
        param_clean = param_name.replace("_", " ").title()

        self.entity_description = NumberEntityDescription(
            key=f"{tool_name}_{param_name}",
            name=f"{clean_name} ({param_clean})",
            native_min_value=min_value,
            native_max_value=max_value,
            native_step=step,
            icon="mdi:numeric",
        )
        self._attr_unique_id = (
            f"{entry.entry_id}_{server_name}_{tool_name}_{param_name}"
        )
        self._attr_has_entity_name = True

        server_data = self._get_server_data() or {}
        self._attr_device_info = get_server_device_info(entry, server_name, server_data)

    def _get_server_data(self) -> dict[str, Any] | None:
        """Get latest server data."""
        if not self.coordinator.data:
            return None
        for server in self.coordinator.data.get(ATTR_SERVERS, []):
            if server.get("name") == self._server_name:
                return server
        return None

    @property
    def native_value(self) -> float:
        """Return the current numerical value."""
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        """Set new value and invoke tool."""
        self._value = value
        self.async_write_ha_state()

        tool_name = self._tool.get("name", "")
        param_type = (
            self._tool.get("inputSchema", {})
            .get("properties", {})
            .get(self._param_name, {})
            .get("type")
        )
        cast_val: int | float = int(value) if param_type == "integer" else float(value)

        args = {self._param_name: cast_val}
        _LOGGER.info(
            "Executing MCP tool number '%s' on '%s' with args: %s",
            tool_name,
            self._server_name,
            args,
        )
        try:
            await self._client.async_call_tool(
                server=self._server_name,
                tool_name=tool_name,
                arguments=args,
            )
        except Exception as err:
            _LOGGER.error("Failed to execute number tool '%s': %s", tool_name, err)
            raise
