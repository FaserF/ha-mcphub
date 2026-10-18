"""Constants for the MCPHub integration."""

from __future__ import annotations

import logging
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "mcphub"
LOGGER: Final = logging.getLogger(__package__)

DEFAULT_NAME: Final = "MCPHub Gateway"
DEFAULT_API_URL: Final = "http://localhost:3000"
DEFAULT_MANUFACTURER: Final = "MCPHub"
DEFAULT_MODEL: Final = "Model Context Protocol Gateway"

DATA_COORDINATOR: Final = "coordinator"
DATA_CLIENT: Final = "client"

# Configuration & Options keys
CONF_API_URL: Final = "api_url"
CONF_API_KEY: Final = "api_key"
CONF_DEFAULT_GROUP: Final = "default_group"
CONF_POLL_INTERVAL: Final = "poll_interval"
CONF_AUTO_IMPORT_NEW: Final = "auto_import_new"
CONF_ENABLED_SERVERS: Final = "enabled_servers"

DEFAULT_DEFAULT_GROUP: Final = "$smart"
DEFAULT_POLL_INTERVAL: Final = 30
DEFAULT_AUTO_IMPORT_NEW: Final = True

# Comprehensive mapping of MCP server names or keywords to official Home Assistant integrations and custom integrations
KNOWN_DUPLICATE_SERVERS: Final[dict[str, str]] = {
    # Core Home Assistant
    "home-assistant": "Native Home Assistant Instance",
    "homeassistant": "Native Home Assistant Instance",
    "ha": "Native Home Assistant Instance",

    # Official HA Integrations & Standard Services
    "github": "Official GitHub Integration",
    "cloudflare": "Official Cloudflare / Advanced Cloudflare Integration",
    "dwd": "Official DWD Weather / Weather Warnings Integration",
    "steam": "Official Steam Integration",
    "jellyfin": "Official Jellyfin Integration",
    "paperless": "Official Paperless-ngx Integration",
    "signal": "Official Signal Messenger Integration",
    "rocketchat": "Official Rocket.Chat Integration",
    "postgres": "Official SQL / PostgreSQL Sensor Integration",
    "sqlite": "Official SQL / SQLite Sensor Integration",
    "m365": "Microsoft 365 / O365 Integration",
    "google": "Official Google Calendars / Photos / Home Integration",
    "google-keep": "Google Keep Integration",
    "google-news": "Google News RSS Feed Integration",
    "youtube": "Official YouTube Integration",
    "ytmusic": "YouTube Music Integration",
    "openwrt": "Official OpenWrt / ha-openwrt Integration",
    "media-arr": "Official Sonarr / Radarr / Lidarr Integrations",
    "sonarr": "Official Sonarr Integration",
    "radarr": "Official Radarr Integration",
    "tautulli": "Official Tautulli Integration",
    "plex": "Official Plex Integration",
    "pi-hole": "Official Pi-hole Integration",
    "adguard": "Official AdGuard Home Integration",
    "esphome": "Official ESPHome Integration",
    "zigbee2mqtt": "Official MQTT / Zigbee Integration",
    "zwave_js": "Official Z-Wave JS Integration",
    "synology": "Official Synology DSM Integration",
    "unifi": "Official Ubiquiti UniFi Integration",
    "fritzbox": "Official AVM FRITZ!Box Integration",
    "wireguard": "Official WireGuard Integration",
    "tailscale": "Official Tailscale Integration",
    "transmission": "Official Transmission Integration",
    "qbittorrent": "Official qBittorrent Integration",
    "nextcloud": "Official Nextcloud Integration",
    "grafana": "Official Grafana Integration",
    "influxdb": "Official InfluxDB Integration",
    "prometheus": "Official Prometheus Integration",
    "mqtt": "Official MQTT Integration",
    "modbus": "Official Modbus Integration",
    "snmp": "Official SNMP Integration",
    "wled": "Official WLED Integration",
    "tasmota": "Official Tasmota Integration",
    "shelly": "Official Shelly Integration",
    "hue": "Official Philips Hue Integration",
    "tradfri": "Official IKEA Trådfri Integration",
    "tuya": "Official Tuya / Smart Life Integration",
    "matter": "Official Matter Integration",

    # Custom & Specialized Integrations
    "omniroute": "ha-omniroute integration",
    "shielddns": "ha-shielddns integration",
    "komodo": "ha-komodo integration",
    "aegisbot": "ha-aegisbot integration",
    "paseo": "ha-paseo integration",
    "google-jules": "ha-jules integration",
}


def detect_duplicate_conflict(server_name: str) -> str | None:
    """Detect if an MCP server name conflicts with an official or custom HA integration."""
    normalized = server_name.lower().strip()
    # Direct match
    if normalized in KNOWN_DUPLICATE_SERVERS:
        return KNOWN_DUPLICATE_SERVERS[normalized]

    # Prefix or sub-server matching (e.g. google-jules-* or media-arr-*)
    for key, description in KNOWN_DUPLICATE_SERVERS.items():
        if normalized.startswith(f"{key}-") or normalized.startswith(f"{key}_"):
            return description
        if f"-{key}" in normalized or f"_{key}" in normalized:
            return description

    return None

# Known web URLs for visit device actions
SERVER_VISIT_URLS: Final[dict[str, str]] = {}

# Supported platforms
PLATFORMS: Final[list[Platform]] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SWITCH,
    Platform.NOTIFY,
    Platform.SELECT,
]

# Service definitions
SERVICE_CALL_TOOL: Final = "call_tool"
SERVICE_RELOAD_SERVER: Final = "reload_server"
SERVICE_TOGGLE_SERVER: Final = "toggle_server"
SERVICE_CLEAR_CACHE: Final = "clear_cache"
SERVICE_DISCOVER_TOOLS: Final = "discover_tools"

# Attributes
ATTR_SERVERS: Final = "servers"
ATTR_CONNECTED_SERVERS: Final = "connected_servers"
ATTR_TOTAL_SERVERS: Final = "total_servers"
ATTR_TOTAL_TOOLS: Final = "total_tools"
ATTR_LATENCY_MS: Final = "latency_ms"
ATTR_TOOL_NAME: Final = "tool_name"
ATTR_SERVER_NAME: Final = "server_name"
ATTR_RESULT: Final = "result"
ATTR_IS_ERROR: Final = "is_error"
