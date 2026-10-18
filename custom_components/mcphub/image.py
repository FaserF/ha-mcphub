"""Dynamic image entities for MCPHub screenshot and capture tools."""

from __future__ import annotations

import base64
import logging
from typing import Any

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

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
    """Set up dynamic MCPHub image entities."""
    coordinator: MCPHubCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    client: MCPHubClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]

    entities: list[ImageEntity] = []

    for server in coordinator.data.get("servers", []):
        server_name = server.get("name", "")
        if not server_name or not _is_server_enabled(entry, server_name):
            continue

        tools = server.get("tools", [])
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            tool_name = tool.get("name", "")
            tool_lower = tool_name.lower()

            if any(
                term in tool_lower
                for term in ("screenshot", "snapshot", "capture_screen")
            ):
                entities.append(
                    MCPHubDynamicToolImage(
                        hass=hass,
                        coordinator=coordinator,
                        client=client,
                        entry=entry,
                        server_name=server_name,
                        tool=tool,
                    )
                )

    async_add_entities(entities)


class MCPHubDynamicToolImage(CoordinatorEntity[MCPHubCoordinator], ImageEntity):
    """Dynamic image entity that renders captured screenshots from MCP tools."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: MCPHubCoordinator,
        client: MCPHubClient,
        entry: ConfigEntry,
        server_name: str,
        tool: dict[str, Any],
    ) -> None:
        """Initialize dynamic image entity."""
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)
        self._client = client
        self._server_name = server_name
        self._tool = tool
        self._image_bytes: bytes | None = None

        tool_name = tool.get("name", "")
        clean_name = (
            tool_name.replace(f"{server_name}-", "")
            .replace(f"{server_name}_", "")
            .replace("_", " ")
            .title()
        )

        self._attr_name = clean_name
        self._attr_unique_id = f"{entry.entry_id}_{server_name}_{tool_name}_image"
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

    async def async_image(self) -> bytes | None:
        """Fetch image on demand from the MCP tool."""
        tool_name = self._tool.get("name", "")
        try:
            res = await self._client.async_call_tool(
                server=self._server_name,
                tool_name=tool_name,
                arguments={},
            )
            content = res.get("content", [])
            for item in content:
                if isinstance(item, dict) and item.get("type") == "image":
                    b64 = item.get("data", "")
                    if b64:
                        self._image_bytes = base64.b64decode(b64)
                        self._attr_image_last_updated = dt_util.utcnow()
                        return self._image_bytes
        except Exception as err:
            _LOGGER.debug("Could not fetch image for %s: %s", tool_name, err)
        return self._image_bytes
