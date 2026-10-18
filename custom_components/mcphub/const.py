"""Constants for the MCPHub integration."""

from __future__ import annotations

import logging
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "mcphub"
LOGGER: Final = logging.getLogger(__package__)

DEFAULT_NAME: Final = "MCPHub Gateway"
DEFAULT_API_URL: Final = "http://mcphub.tailnet.fabiseitz.de:3000"
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

# Known native or existing integrations in Fabian's setup to warn or unselect by default
KNOWN_DUPLICATE_SERVERS: Final[dict[str, str]] = {
    "home-assistant": "Native Home Assistant Instance",
    "omniroute": "ha-omniroute integration",
    "shielddns": "ha-shielddns integration",
    "komodo": "ha-komodo integration",
    "cloudflare": "ha-cloudflare integration",
    "openwrt": "ha-openwrt integration",
    "aegisbot": "ha-aegisbot integration",
    "paseo": "ha-paseo integration",
    "google-jules": "ha-jules integration",
}

# Known web URLs for visit device actions
SERVER_VISIT_URLS: Final[dict[str, str]] = {
    "mcphub": "http://mcphub.tailnet.fabiseitz.de:3000",
    "omniroute": "http://omniroute.tailnet.fabiseitz.de:20128",
    "shielddns": "https://dns.fabiseitz.de",
    "komodo": "https://komodo.tailnet.fabiseitz.de",
    "paseo": "http://code.tailnet.fabiseitz.de:6767",
    "jellyfin": "http://code.tailnet.fabiseitz.de:8096",
    "media-arr": "http://code.tailnet.fabiseitz.de:7878",
    "paperless": "https://paperless.tailnet.fabiseitz.de",
    "entramirror": "https://entra.tailnet.fabiseitz.de",
    "jarvis": "http://jarvis.tailnet.fabiseitz.de:8090",
}

# Supported platforms
PLATFORMS: Final[list[Platform]] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SWITCH,
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
