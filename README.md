<p align="center">
  <img src="https://raw.githubusercontent.com/FaserF/ha-mcphub/main/brand/logo.png" alt="MCPHub Logo" width="380">
</p>

# MCPHub Gateway & Ecosystem Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/default)
[![CI](https://github.com/FaserF/ha-mcphub/actions/workflows/ci-orchestrator.yml/badge.svg)](https://github.com/FaserF/ha-mcphub/actions)
[![GitHub Release](https://img.shields.io/github/v/release/FaserF/ha-mcphub)](https://github.com/FaserF/ha-mcphub/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An intelligent, enterprise-grade Home Assistant custom integration for **MCPHub** — the central Model Context Protocol (MCP) gateway, router, and control plane.

Dynamically maps all your registered MCP servers into dedicated, first-class Home Assistant devices, generates native sensors, switches, and action buttons for zero-parameter tools, and exposes the full catalog of over 750 tools to Home Assistant automations, scripts, and voice agents.

---

## 🌟 Key Architecture & Intelligent Capabilities

### 1. 🌐 Central Gateway Hub & Telemetry
- **Gateway Device**: Creates a master device representing the MCPHub control plane.
- **Real-Time Health Monitoring**: Tracks roundtrip API response latency in milliseconds (`sensor.mcphub_gateway_latency`).
- **Fleet Statistics**: Tracks connected servers, total registered servers, and aggregate tool catalog counts in real-time.
- **Cache Management**: Instantly purge tool discovery and schema caches (`button.mcphub_gateway_clear_cache`).

### 2. 🧩 Intelligent First-Class Server Device Mapping
Every registered MCP server selected during setup (e.g. `finance`, `dell-worker`, `gaming-pc`, `signal`, `steam`, `rocketchat`, `postgres`, `sqlite`, etc.) is dynamically mapped into its own **dedicated Home Assistant Device** with:
- **Software Version & Transport Mode**: Displays real firmware/software versions and protocol transport (`STDIO`, `STREAMABLE-HTTP`, `SSE`).
- **Web UI Visit Shortcut**: Direct link to the service dashboard (e.g. `http://code.tailnet.fabiseitz.de:8096` for Jellyfin, `https://paperless.tailnet.fabiseitz.de` for Paperless, etc.).
- **Per-Server Online Connectivity**: Binary sensor (`binary_sensor.mcphub_<server>_online`) reflecting live MCPHub heartbeat.
- **Server Lifecycle Switch**: Power switch (`switch.mcphub_<server>_enabled`) to enable or disable individual MCP servers on demand without container restarts.
- **Service Restart Button**: Action button (`button.mcphub_<server>_restart_reload`) triggering an immediate process reconnect.

### 3. ⚡ Autonomous Zero-Parameter Tool Transformation
MCPHub integration scans the JSON schemas of all registered tools and **automatically synthesizes native Home Assistant entities**:
- **Diagnostic & Query Sensors**: Tools like `get_status`, `get_stats`, `overview`, `health_check`, `top_stories`, or `list_tables` that take zero required parameters are automatically instantiated as live state sensors with tool schemas in their attributes.
- **Action & Routine Buttons**: Tools like `reboot`, `restart`, `clear_cache`, `flush`, `wake_on_lan`, or `sync` that take zero required parameters are automatically synthesized as one-click action buttons.

### 4. 🛡️ Conflict & Native Integration Guardrails
MCPHub actively inspects your Home Assistant setup and prevents duplicate entities:
- **Smart Conflict Warning**: During the Setup Flow and Options Flow, servers already covered by native integrations (such as `ha-omniroute`, `ha-shielddns`, `ha-komodo`, `ha-openwrt`, `ha-paseo`, `ha-jules`, or `home-assistant`) are clearly flagged (`⚠️ (Native Integration)`) and unselected by default.
- **Future-Proof Auto-Import Toggle**: Choose whether newly registered servers in MCPHub should be automatically provisioned as Home Assistant devices or require manual selection.

---

## 🚀 Installation

### Option 1: HACS (Recommended)

1. Open **HACS** in your Home Assistant.
2. Click the three dots in the upper right corner and select **Custom repositories**.
3. Add `https://github.com/FaserF/ha-mcphub` with category **Integration**.
4. Search for **MCPHub Gateway** and click **Download**.
5. Restart Home Assistant.

### Option 2: Manual Installation

1. Download the latest release `.zip` from the [Releases page](https://github.com/FaserF/ha-mcphub/releases).
2. Extract and copy the `custom_components/mcphub/` directory into your Home Assistant `/config/custom_components/` folder.
3. Restart Home Assistant.

---

## ⚙️ Configuration

1. In Home Assistant, navigate to **Settings > Devices & Services > Add Integration**.
2. Search for **MCPHub Gateway**.
3. Enter your connection details:
   - **MCPHub Base URL**: e.g. `http://mcphub.tailnet.fabiseitz.de:3000`
   - **Bearer API Key**: Your MCPHub authorization token (e.g. `mcphub_...`)
   - **Default Tool Group**: Fallback routing group (default: `$smart`)
4. In the **Select MCP Servers** step, check the servers you want to expose as Home Assistant devices.

### Options Flow Settings

Click **Configure** on the MCPHub integration card to:
- Adjust polling interval (seconds).
- Switch the default smart routing group.
- Toggle automatic import for newly discovered MCP servers.
- Reconfigure enabled/disabled server devices.

---

## 🛠️ Service & Action Reference

### `mcphub.call_tool`
Execute any tool across any of the 47+ registered MCP servers or `$smart` routing group with full JSON response support.

```yaml
action: mcphub.call_tool
data:
  server: "finance"
  tool_name: "finance-finance_get_quote"
  arguments:
    symbol: "AAPL"
response_variable: quote_result
```

### `mcphub.discover_tools`
Dynamically inspect and query tool catalogs and parameter definitions for a specific server or smart routing group.

```yaml
action: mcphub.discover_tools
data:
  server_or_group: "$smart"
response_variable: catalog
```

### `mcphub.reload_server`
Instruct MCPHub to restart and reconnect an MCP server connection.

```yaml
action: mcphub.reload_server
data:
  server_name: "dell-worker"
```

### `mcphub.toggle_server`
Toggle an MCP server between enabled and disabled in MCPHub.

```yaml
action: mcphub.toggle_server
data:
  server_name: "steam"
```

### `mcphub.clear_cache`
Flush all cached tool schemas and routing caches.

```yaml
action: mcphub.clear_cache
```

---

## 📄 License

MIT © [Fabian Seitz](https://github.com/FaserF)
