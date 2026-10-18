"""Dynamic text entities for MCPHub single-input tools."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.text import TextEntity, TextEntityDescription
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
    """Set up dynamic MCPHub text entities."""
    coordinator: MCPHubCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    client: MCPHubClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]

    entities: list[TextEntity] = []

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

            # Check if there is exactly 1 string parameter that isn't an enum or covered by notify
            str_props = [
                k for k, v in props.items()
                if isinstance(v, dict) and v.get("type") == "string" and "enum" not in v
            ]
            if len(str_props) == 1 and (not req_params or req_params == str_props):
                param_name = str_props[0]
                # Skip if already handled by notify platform
                if any(p in param_name.lower() for p in ("message", "text", "body", "content")):
                    tool_name_lower = tool.get("name", "").lower()
                    if any(t in tool_name_lower for t in ("notify", "send_message", "post_message")):
                        continue

                entities.append(
                    MCPHubDynamicToolText(
                        coordinator=coordinator,
                        client=client,
                        entry=entry,
                        server_name=server_name,
                        tool=tool,
                        param_name=param_name,
                    )
                )

    async_add_entities(entities)


class MCPHubDynamicToolText(CoordinatorEntity[MCPHubCoordinator], TextEntity):
    """Dynamic text entity that executes an MCP tool on text input submission."""

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        client: MCPHubClient,
        entry: ConfigEntry,
        server_name: str,
        tool: dict[str, Any],
        param_name: str,
    ) -> None:
        """Initialize the dynamic tool text entity."""
        super().__init__(coordinator)
        self._client = client
        self._server_name = server_name
        self._tool = tool
        self._param_name = param_name
        self._value: str = ""

        tool_name = tool.get("name", "")
        clean_name = (
            tool_name.replace(f"{server_name}-", "")
            .replace(f"{server_name}_", "")
            .replace("_", " ")
            .title()
        )
        param_clean = param_name.replace("_", " ").title()

        self.entity_description = TextEntityDescription(
            key=f"{tool_name}_{param_name}",
            name=f"{clean_name} ({param_clean})",
            icon="mdi:form-textbox",
        )
        self._attr_unique_id = f"{entry.entry_id}_{server_name}_{tool_name}_{param_name}"
        self._attr_has_entity_name = True

        server_data = self._get_server_data() or {}
        self._attr_device_info = get_server_device_info(entry, server_name, server_data)

    def _get_server_data(self) -> dict[str, Any] | None:
        """Get latest data for this server."""
        if not self.coordinator.data:
            return None
        for server in self.coordinator.data.get(ATTR_SERVERS, []):
            if server.get("name") == self._server_name:
                return server
        return None

    @property
    def native_value(self) -> str:
        """Return the current text value."""
        return self._value

    async def async_set_value(self, value: str) -> None:
        """Set new text value and invoke MCP tool."""
        self._value = value
        self.async_write_ha_state()

        tool_name = self._tool.get("name", "")
        args = {self._param_name: value}
        _LOGGER.info(
            "Executing MCP tool text '%s' on '%s' with args: %s",
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
            _LOGGER.error("Failed to execute text tool '%s': %s", tool_name, err)
            raise
