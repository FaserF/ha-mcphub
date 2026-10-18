"""Buttons for MCPHub integration with dynamic executable actions and custom mapping support."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
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
from .custom_mapping import (
    DeviceMapping,
    EntityMapping,
    async_execute_mapping_action,
    extract_device_info,
    get_nested_value,
    load_mappings_from_entry,
    sync_device_registry,
)
from .helpers import get_gateway_device_info, get_server_device_info

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
    """Set up MCPHub buttons."""
    coordinator: MCPHubCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    client: MCPHubClient = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]

    entities: list[ButtonEntity] = [
        MCPHubClearCacheButton(coordinator, client, entry),
        MCPHubRefreshButton(coordinator, entry),
    ]

    for server in coordinator.data.get("servers", []):
        name = server.get("name", "")
        if not name or not _is_server_enabled(entry, name):
            continue

        entities.append(MCPHubReloadServerButton(coordinator, client, entry, name))

        tools = server.get("tools", [])
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            tool_name = tool.get("name", "")
            req_params = (tool.get("inputSchema") or {}).get("required", [])

            is_action = any(
                act in tool_name.lower()
                for act in (
                    "clear",
                    "flush",
                    "reboot",
                    "restart",
                    "start",
                    "wake",
                    "sync",
                    "run",
                )
            )

            if (not req_params or len(req_params) == 0) and is_action:
                entities.append(
                    MCPHubDynamicToolButton(
                        coordinator=coordinator,
                        client=client,
                        entry=entry,
                        server_name=name,
                        tool=tool,
                    )
                )

    async_add_entities(entities)

    # Process dynamically mapped buttons (e.g. Printer power on & wait)
    tracked_buttons: set[str] = set()

    def _sync_mapped_buttons() -> None:
        mappings = load_mappings_from_entry(entry)
        btn_mappings = [
            (m, e)
            for m in mappings
            if m.enabled
            for e in m.entities
            if e.platform == "button"
        ]
        if not btn_mappings:
            return

        mapped_data = coordinator.data.get("mapped_data", {})
        new_buttons: list[ButtonEntity] = []

        for mapping, entity_cfg in btn_mappings:
            payload = mapped_data.get(mapping.id)
            devices_to_process: list[dict[str, Any]] = []

            if mapping.is_multi_device:
                devices_to_process = list(
                    get_nested_value(payload, mapping.devices_path, []) or []
                )
            elif isinstance(payload, dict):
                devices_to_process = [payload]

            for dev in devices_to_process:
                ident_val = str(
                    get_nested_value(dev, mapping.device_identifier_key, mapping.id)
                )
                clean_id = ident_val.replace(":", "_").replace(".", "_")
                uid = f"{entry.entry_id}_{clean_id}_{entity_cfg.key}"

                sync_device_registry(hass, entry, mapping, dev)

                if uid in tracked_buttons:
                    continue

                tracked_buttons.add(uid)
                new_buttons.append(
                    MCPHubMappedButton(
                        coordinator, client, entry, mapping, entity_cfg, dev
                    )
                )

        if new_buttons:
            async_add_entities(new_buttons)

    _sync_mapped_buttons()
    coordinator.async_add_listener(_sync_mapped_buttons)


class MCPHubClearCacheButton(CoordinatorEntity[MCPHubCoordinator], ButtonEntity):
    """Button to clear MCPHub server caches."""

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        client: MCPHubClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize clear cache button."""
        super().__init__(coordinator)
        self._client = client
        self._entry = entry
        self.entity_description = ButtonEntityDescription(
            key="clear_cache",
            name="Clear Tool Cache",
            icon="mdi:cached",
        )
        self._attr_unique_id = f"{entry.entry_id}_clear_cache"
        self._attr_has_entity_name = True
        self._attr_device_info = get_gateway_device_info(entry)

    async def async_press(self) -> None:
        """Clear cache in MCPHub."""
        await self._client.async_clear_cache()
        await self.coordinator.async_request_refresh()


class MCPHubRefreshButton(CoordinatorEntity[MCPHubCoordinator], ButtonEntity):
    """Button to force coordinator update."""

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize refresh button."""
        super().__init__(coordinator)
        self._entry = entry
        self.entity_description = ButtonEntityDescription(
            key="refresh",
            name="Refresh All",
            icon="mdi:refresh",
        )
        self._attr_unique_id = f"{entry.entry_id}_refresh"
        self._attr_has_entity_name = True
        self._attr_device_info = get_gateway_device_info(entry)

    async def async_press(self) -> None:
        """Request immediate coordinator refresh."""
        await self.coordinator.async_request_refresh()


class MCPHubReloadServerButton(CoordinatorEntity[MCPHubCoordinator], ButtonEntity):
    """Button to reload a specific MCP server."""

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        client: MCPHubClient,
        entry: ConfigEntry,
        server_name: str,
    ) -> None:
        """Initialize reload button."""
        super().__init__(coordinator)
        self._client = client
        self._server_name = server_name
        self.entity_description = ButtonEntityDescription(
            key=f"reload_{server_name}",
            name="Reload Server",
            icon="mdi:restart",
        )
        self._attr_unique_id = f"{entry.entry_id}_server_reload_{server_name}"
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

    async def async_press(self) -> None:
        """Reload the server in MCPHub."""
        await self._client.async_reload_server(self._server_name)
        await self.coordinator.async_request_refresh()


class MCPHubDynamicToolButton(CoordinatorEntity[MCPHubCoordinator], ButtonEntity):
    """Button to invoke zero-argument action tools."""

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        client: MCPHubClient,
        entry: ConfigEntry,
        server_name: str,
        tool: dict[str, Any],
    ) -> None:
        """Initialize dynamic tool button."""
        super().__init__(coordinator)
        self._client = client
        self._server_name = server_name
        self._tool = tool
        raw_name = tool.get("name", "")
        short_name = (
            raw_name.split("-")[-1]
            .replace(f"{server_name}_", "")
            .replace("_", " ")
            .title()
        )

        self._attr_unique_id = f"{entry.entry_id}_{server_name}_button_{raw_name}"
        self._attr_has_entity_name = True
        self._attr_name = short_name
        self._attr_icon = "mdi:play"

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

    async def async_press(self) -> None:
        """Execute the tool."""
        await self._client.async_call_tool(
            self._server_name,
            self._tool.get("name", ""),
            {},
        )
        await self.coordinator.async_request_refresh()


class MCPHubMappedButton(CoordinatorEntity[MCPHubCoordinator], ButtonEntity):
    """Dynamically mapped button for custom MCP devices."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MCPHubCoordinator,
        client: MCPHubClient,
        entry: ConfigEntry,
        mapping: DeviceMapping,
        entity_cfg: EntityMapping,
        device_data: dict[str, Any],
    ) -> None:
        """Initialize mapped button."""
        super().__init__(coordinator)
        self._client = client
        self._entry = entry
        self._mapping = mapping
        self._entity_cfg = entity_cfg
        self._device_data = dict(device_data)

        ident_val = str(
            get_nested_value(device_data, mapping.device_identifier_key, mapping.id)
        )
        clean_id = ident_val.replace(":", "_").replace(".", "_")

        self._attr_unique_id = f"{entry.entry_id}_{clean_id}_{entity_cfg.key}"
        self._attr_name = entity_cfg.name
        self._attr_icon = "mdi:power"

    @property
    def device_info(self) -> DeviceInfo:
        """Return dynamic device information extracted via custom mapping."""
        return extract_device_info(self._entry, self._mapping, self._device_data)

    async def async_press(self) -> None:
        """Execute the mapped button action."""
        action = self._entity_cfg.actions.get("press")
        if action:
            await async_execute_mapping_action(
                self._client, action, self._mapping.server_name, self._device_data, {}
            )
            await self.coordinator.async_request_refresh()
