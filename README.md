# Home Assistant MCPHub Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/FaserF/ha-mcphub)](https://github.com/FaserF/ha-mcphub/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An intelligent, full-featured Home Assistant custom integration for **MCPHub** — the open-source central Model Context Protocol (MCP) gateway and control plane.

Dynamically maps all your registered MCP servers into dedicated, first-class Home Assistant devices, generates native sensors, switches, and action buttons for zero-parameter tools, and exposes the full catalog of over 750 tools to Home Assistant automations, scripts, and voice agents.

---

## ✨ Features

- 🌐 **Central Gateway Overview**: Real-time telemetry for gateway latency, connected servers, total registered servers, and total tools count.
- 🧩 **First-Class MCP Server Devices**: Each selected MCP server becomes its own Home Assistant device with firmware version, transport type (`stdio`, `streamable-http`, `sse`), and direct Visit Web UI button.
- ⚡ **Intelligent Dynamic Entities**: Automatically discovers zero-argument tools (status checks, health probes, statistics, cache flushes, wake actions) and generates native sensors and buttons.
- 🔄 **Smart Conflict Avoidance**: Automatically warns and deselects servers that are already handled natively in Home Assistant (e.g. `ha-omniroute`, `ha-shielddns`, `ha-komodo`, `ha-openwrt`).
- 🎛️ **Server Lifecycle Controls**: Turn servers on/off via switches and trigger on-demand reloads with buttons.
- 🛠️ **Full Automation Services**:
  - `mcphub.call_tool`: Execute any MCP tool across any server or `$smart` routing group with full JSON response support.
  - `mcphub.reload_server`: Restart and reconnect any MCP server.
  - `mcphub.toggle_server`: Enable or disable servers on the fly.
  - `mcphub.clear_cache`: Flush discovery and schema caches.
  - `mcphub.discover_tools`: List available tools and input schemas dynamically.

---

## 📦 Installation via HACS

1. Open **HACS** in your Home Assistant.
2. Click the three dots in the upper right corner and select **Custom repositories**.
3. Add `https://github.com/FaserF/ha-mcphub` with category **Integration**.
4. Search for **MCPHub Gateway** and click **Download**.
5. Restart Home Assistant.

---

## ⚙️ Configuration

1. Go to **Settings** -> **Devices & Services** -> **Add Integration**.
2. Search for **MCPHub Gateway**.
3. Enter your MCPHub Server Base URL (`http://mcphub.tailnet.fabiseitz.de:3000`) and Bearer API Key.
4. Select which discovered MCP servers to map into Home Assistant devices.

---

## 📄 License

MIT © [Fabian Seitz](https://github.com/FaserF)
