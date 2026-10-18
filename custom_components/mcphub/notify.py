"""Dynamic notify entities for MCPHub communication tools (e.g. Rocket.Chat, Signal)."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.notify import NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .client import MCPHubClient
from .const import (
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
    """Set up dynamic MCPHub notification entities."""
    coordinator: MCPHubCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    client: MCPHubClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]

    entities: list[NotifyEntity] = []

    for server in coordinator.data.get("servers", []):
        server_name = server.get("name", "")
        if not server_name or not _is_server_enabled(entry, server_name):
            continue

        tools = server.get("tools", [])
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            tool_name = tool.get("name", "")
            schema = tool.get("inputSchema") or {}
            props = schema.get("properties", {})

            # Detect message sending / chat dispatch tools
            has_msg_param = any(
                p in props for p in ("message", "text", "body", "content")
            )
            is_notify_tool = any(
                term in tool_name.lower()
                for term in (
                    "send_message",
                    "post_message",
                    "send_notification",
                    "notify",
                    "send_sms",
                )
            )

            if is_notify_tool or (
                has_msg_param
                and any(
                    k in server_name.lower()
                    for k in (
                        "chat",
                        "signal",
                        "telegram",
                        "slack",
                        "discord",
                        "matrix",
                    )
                )
            ):
                entities.append(
                    MCPHubNotifyEntity(coordinator, client, entry, server_name, tool)
                )

    async_add_entities(entities)


class MCPHubNotifyEntity(CoordinatorEntity[MCPHubCoordinator], NotifyEntity):
    """Dynamic notification entity routing into an MCP messaging tool."""

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        client: MCPHubClient,
        entry: ConfigEntry,
        server_name: str,
        tool: dict[str, Any],
    ) -> None:
        """Initialize the dynamic notify entity."""
        super().__init__(coordinator)
        self._client = client
        self._server_name = server_name
        self._tool = tool

        raw_name = tool.get("name", "")
        clean_name = (
            raw_name.split("-")[-1]
            .replace(f"{server_name}_", "")
            .replace("_", " ")
            .title()
        )

        self._attr_unique_id = f"{entry.entry_id}_{server_name}_notify_{raw_name}"
        self._attr_has_entity_name = True
        self._attr_name = f"Notify ({clean_name})"
        self._attr_icon = "mdi:message-fast"

        server_data = next(
            (
                s
                for s in coordinator.data.get("servers", [])
                if s.get("name") == server_name
            ),
            None,
        )
        self._attr_device_info = get_server_device_info(entry, server_name, server_data)

    async def async_send_message(
        self,
        message: str,
        title: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Send a message via the dynamic MCP tool call."""
        tool_name = self._tool.get("name", "")
        schema = self._tool.get("inputSchema") or {}
        props = schema.get("properties", {})
        payload_data = dict(data or {})

        args: dict[str, Any] = {}

        # 1. Map message text parameter
        if "text" in props:
            args["text"] = f"{title}: {message}" if title else message
        elif "message" in props:
            args["message"] = f"{title}: {message}" if title else message
        elif "body" in props:
            args["body"] = f"{title}: {message}" if title else message
        elif "content" in props:
            args["content"] = f"{title}: {message}" if title else message

        # 2. Check for target recipient or room parameter
        if "room" in props:
            args["room"] = (
                payload_data.get("room") or payload_data.get("target") or "general"
            )
        if "recipient" in props:
            args["recipient"] = (
                payload_data.get("recipient") or payload_data.get("target") or ""
            )
        if "target" in props and "target" not in args:
            args["target"] = payload_data.get("target") or ""

        # 3. Handle explicit confirmation flags if required by tool safety policy
        if "confirm" in props:
            args["confirm"] = True

        # 4. Merge any remaining custom parameters from automation data
        for k, v in payload_data.items():
            if k in props and k not in args:
                args[k] = v

        _LOGGER.info(
            "Dispatching notification via MCP tool %s on %s with args: %s",
            tool_name,
            self._server_name,
            args,
        )
        await self._client.async_call_tool(self._server_name, tool_name, args)
