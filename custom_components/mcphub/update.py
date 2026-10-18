"""Dynamic update entities for MCPHub update-capable tools."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
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
    """Set up dynamic MCPHub update entities."""
    coordinator: MCPHubCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    client: MCPHubClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]

    entities: list[UpdateEntity] = []

    for server in coordinator.data.get("servers", []):
        server_name = server.get("name", "")
        if not server_name or not _is_server_enabled(entry, server_name):
            continue

        tools = server.get("tools", [])
        tool_names = [t.get("name", "").lower() for t in tools if isinstance(t, dict)]

        # Check if server has check_update or trigger_update tools
        has_update_tool = any(
            term in t
            for t in tool_names
            for term in ("check_update", "trigger_update", "upgrade", "firmware_update")
        )
        if has_update_tool:
            entities.append(
                MCPHubServerUpdateEntity(
                    coordinator=coordinator,
                    client=client,
                    entry=entry,
                    server_name=server_name,
                )
            )

    async_add_entities(entities)


class MCPHubServerUpdateEntity(CoordinatorEntity[MCPHubCoordinator], UpdateEntity):
    """Update entity for an MCP server that supports version/firmware checks."""

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        client: MCPHubClient,
        entry: ConfigEntry,
        server_name: str,
    ) -> None:
        """Initialize server update entity."""
        super().__init__(coordinator)
        self._client = client
        self._server_name = server_name

        self.entity_description = UpdateEntityDescription(
            key=f"update_{server_name}",
            name="Update",
            device_class=UpdateDeviceClass.FIRMWARE,
        )
        self._attr_unique_id = f"{entry.entry_id}_update_{server_name}"
        self._attr_has_entity_name = True
        self._attr_supported_features = (
            UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
        )

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
    def installed_version(self) -> str | None:
        """Return currently installed version."""
        data = self._get_server_data()
        ver = data.get("version") if data else None
        return str(ver) if ver else None

    @property
    def latest_version(self) -> str | None:
        """Return latest available version."""
        return self.installed_version

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Trigger update on the server."""
        data = self._get_server_data() or {}
        tools = data.get("tools", [])
        for tool in tools:
            t_name = tool.get("name", "")
            if any(term in t_name.lower() for term in ("trigger_update", "upgrade")):
                _LOGGER.info(
                    "Triggering update tool '%s' on '%s'", t_name, self._server_name
                )
                await self._client.async_call_tool(
                    server=self._server_name,
                    tool_name=t_name,
                    arguments={},
                )
                await self.coordinator.async_request_refresh()
                return
