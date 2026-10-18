"""Helper utilities for MCPHub integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    CONF_API_URL,
    DEFAULT_MANUFACTURER,
    DEFAULT_MODEL,
    DEFAULT_NAME,
    DOMAIN,
    SERVER_VISIT_URLS,
)


def get_gateway_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return DeviceInfo for the central MCPHub Gateway."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=DEFAULT_NAME,
        manufacturer=DEFAULT_MANUFACTURER,
        model=DEFAULT_MODEL,
        configuration_url=entry.data.get(CONF_API_URL),
    )


def get_server_device_info(
    entry: ConfigEntry, server_name: str, server_data: dict[str, Any] | None = None
) -> DeviceInfo:
    """Return DeviceInfo for an individual registered MCP server."""
    cfg = (server_data or {}).get("config") or {}
    vis_url = SERVER_VISIT_URLS.get(server_name) or cfg.get("url")
    version_raw = (server_data or {}).get("version")
    version = str(version_raw).strip() if version_raw else None
    transport = str(cfg.get("type", "stdio")).upper()

    device_kwargs: dict[str, Any] = {
        "identifiers": {(DOMAIN, f"{entry.entry_id}_{server_name}")},
        "via_device": (DOMAIN, entry.entry_id),
        "name": f"MCP {server_name.replace('-', ' ').title()}",
        "manufacturer": "MCP Server Ecosystem",
        "model": f"MCP {transport} Service",
        "configuration_url": vis_url,
    }
    if version:
        device_kwargs["sw_version"] = version

    return DeviceInfo(**device_kwargs)
