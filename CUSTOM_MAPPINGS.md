# MCPHub Custom Mapping Architecture & Guide

This guide describes how to dynamically map arbitrary Model Context Protocol (MCP) servers and tools into native Home Assistant devices and entities without writing hardcoded Python code.

---

## 1. Overview & Architecture

MCPHub connects Home Assistant to over 40+ MCP servers. While standard servers expose zero-argument query tools automatically as diagnostic sensors, rich hardware devices (such as Android TV, smartphones, IPP printers, 3D printers, vacuums) require full domain entities (`media_player`, `remote`, `sensor`, `switch`, `button`) with:
1. **Dynamic Device Info:** Real hardware manufacturer (e.g. `TCL`, `Google`, `HP`), real model name, software/firmware version, serial numbers, and configuration URLs.
2. **Network & OpenWrt MAC Linking:** Automatic MAC address extraction and formatting registered into `(CONNECTION_NETWORK_MAC, mac)` so Home Assistant links the device directly to OpenWrt router tracking, DHCP leases, and network topologies.
3. **Graceful Offline Handling:** When a device or printer is switched off, the integration handles it cleanly (showing state as `off` or `offline`) rather than crashing or spamming `UpdateFailed` tracebacks.
4. **Action & Command Execution:** Templated mapping of Home Assistant entity services (e.g., `media_play`, `turn_on`, `turn_off`, `volume_set`, `select_source`, `send_command`, `press`) to MCP tool calls.

---

## 2. Configuration via Home Assistant OptionsFlow

All custom mappings can be viewed, modified, or added directly in the Home Assistant UI:
1. Navigate to **Settings** → **Devices & Services** → **MCPHub Gateway**.
2. Click **Configure** (Options).
3. The options form includes:
   - **Poll Interval (seconds)**
   - **Default Group**
   - **Auto-import new servers**
   - **Enabled Servers**
   - **Custom Mappings (JSON)**: An interactive JSON editor containing all active mappings.
4. You can edit existing mappings, paste new ones, or tweak argument templates. Clicking **Submit** validates the JSON and reloads the entities dynamically.

---

## 3. Schema Specification

A custom mapping is defined as a list of `DeviceMapping` objects in JSON:

### DeviceMapping Top-Level Fields

| Field | Type | Description |
|---|---|---|
| `id` | `string` | Unique identifier for this mapping (e.g. `"android_adb"`, `"printer_ipp"`). |
| `name` | `string` | Friendly display name. |
| `server_name` | `string` | Target MCP server name in MCPHub (e.g. `"android-adb"`, `"printer"`). |
| `discovery_tool` | `string` | MCP tool called by the coordinator to fetch device data. |
| `discovery_params` | `object` | Arguments passed to the discovery tool (default `{}`). |
| `is_multi_device` | `boolean` | `true` if discovery returns an array of devices; `false` if single device. |
| `devices_path` | `string` | Dot-notation path to the array of devices (e.g. `"devices"`). |
| `device_identifier_key` | `string` | Field in device payload for unique identifier (`"serial"`, `"uuid"`). |
| `device_info` | `object` | Rules for extracting hardware specifications and MAC address. |
| `offline_policy` | `object` | Handling of powered-off or unreachable states. |
| `entities` | `array` | List of entity definitions (`EntityMapping`) generated under this device. |
| `enabled` | `boolean` | Whether this mapping is active (default `true`). |

### Device Info Mapping (`device_info`)

- `name_path`: Path to friendly name (e.g. `"name"` or `"model"`).
- `manufacturer_path`: Path to hardware manufacturer (e.g. `"manufacturer"`).
- `model_path`: Path to model name (e.g. `"model"`).
- `sw_version_path`: Path to firmware or OS version (e.g. `"sw_version"`, `"androidVersion"`).
- `serial_path`: Path to device serial number.
- `mac_path`: Path to MAC address string or array of MACs. Automatically formatted and added to device connections.
- `configuration_url_path`: Path to device web portal or AirPrint page.

### Offline Policy (`offline_policy`)

- `status_key`: Field in payload indicating status (`"online"`, `"state"`, `"power"`).
- `offline_values`: List of values considered offline (`[false, "offline", "unreachable", "off"]`).
- `available_when_offline`: If `true`, entities remain available in Home Assistant rather than becoming unavailable.
- `default_state_when_offline`: State to publish when offline (`"off"`, `"offline"`).

### Entity Mapping (`entities`)

- `platform`: Target domain (`"media_player"`, `"remote"`, `"sensor"`, `"switch"`, `"button"`).
- `key`: Entity key suffix (e.g. `"media_player"`, `"uptime"`, `"marker"`, `"power"`).
- `name`: Display name or template (e.g. `null` to inherit device name, `"{item.name}"`, `"Betriebszeit"`).
- `device_class`: Home Assistant device class (`"tv"`, `"enum"`, `"timestamp"`).
- `state_class`: State class (`"measurement"`, `"total_increasing"`).
- `unit_of_measurement`: Unit string (e.g. `"%"`).
- `options`: List of valid enum options for enum sensors.
- `is_collection`: `true` to generate an entity per item in an array (e.g. toner cartridges).
- `collection_path`: Dot-notation path to the array (e.g. `"markers"`).
- `collection_id_key`: Field used for sub-entity unique ID (e.g. `"name"`).
- `value_path`: Dot-notation path to the primary state value.
- `attributes`: Key-value map of `{ "ha_attribute": "payload_path" }`.
- `state_map`: Optional value replacement dictionary.
- `source_list`: Dictionary of `{ "Friendly App Name": "package.name" }` for media players.
- `current_source_path`: Path to active package/source.
- `actions`: Map of actions to tool calls with `args_template`.

### Action Mapping (`actions`)

- `tool`: Name of MCP tool to invoke.
- `args_template`: Arguments template supporting `{{ device.field }}` and `{{ action.field }}` placeholders.

---

## 4. Built-in Production Examples

### Android ADB (`android_adb`)
Models media players and remotes with full app lists, volume, and playback control:

```json
{
  "id": "android_adb",
  "name": "Android ADB Devices",
  "server_name": "android-adb",
  "discovery_tool": "adb_devices",
  "is_multi_device": true,
  "devices_path": "devices",
  "device_identifier_key": "serial",
  "device_info": {
    "name_path": "model",
    "manufacturer_path": "manufacturer",
    "model_path": "model",
    "sw_version_path": "androidVersion",
    "mac_path": "macs"
  },
  "offline_policy": {
    "status_key": "state",
    "offline_values": ["offline", "unauthorized", "disconnected"],
    "available_when_offline": true,
    "default_state_when_offline": "off"
  },
  "entities": [
    {
      "platform": "media_player",
      "key": "media_player",
      "device_class": "tv",
      "value_path": "state",
      "current_source_path": "currentApp",
      "source_list": {
        "YouTube": "com.google.android.youtube.tv",
        "SmartTube": "org.smarttube.stable",
        "Netflix": "com.netflix.ninja",
        "Prime Video": "com.amazon.amazonvideo.livingroom",
        "Disney+": "com.disney.disneyplus",
        "Jellyfin": "org.jellyfin.androidtv"
      },
      "actions": {
        "turn_on": { "tool": "adb_power_toggle", "args_template": { "serial": "{{ device.serial }}" } },
        "turn_off": { "tool": "adb_key", "args_template": { "serial": "{{ device.serial }}", "key": "POWER" } },
        "play": { "tool": "adb_key", "args_template": { "serial": "{{ device.serial }}", "key": "MEDIA_PLAY" } },
        "pause": { "tool": "adb_key", "args_template": { "serial": "{{ device.serial }}", "key": "MEDIA_PAUSE" } },
        "select_source": {
          "tool": "adb_app_launch",
          "args_template": { "app": "{{ action.source }}", "device": "{{ device.serial }}" }
        }
      }
    },
    {
      "platform": "remote",
      "key": "remote",
      "name": "Remote",
      "actions": {
        "turn_on": { "tool": "adb_power_toggle", "args_template": { "serial": "{{ device.serial }}" } },
        "turn_off": { "tool": "adb_key", "args_template": { "serial": "{{ device.serial }}", "key": "POWER" } },
        "send_command": {
          "tool": "adb_keyevent",
          "args_template": { "device": "{{ device.serial }}", "keycode": "{{ action.command }}" }
        }
      }
    }
  ]
}
```

### IPP Printer (`printer_ipp`)
Provides 100% feature parity with Home Assistant IPP: printer status enum, uptime, dynamic toner/ink marker sensors with color and high/low levels, page counters, and power switch:

```json
{
  "id": "printer_ipp",
  "name": "HP LaserJet MFP M426fdw IPP",
  "server_name": "printer",
  "discovery_tool": "printer_status",
  "is_multi_device": false,
  "device_identifier_key": "uuid",
  "device_info": {
    "name_path": "name",
    "manufacturer_path": "manufacturer",
    "model_path": "model",
    "sw_version_path": "sw_version",
    "serial_path": "serial",
    "mac_path": "mac",
    "configuration_url_path": "more_info"
  },
  "offline_policy": {
    "status_key": "online",
    "offline_values": [false, "false", "offline", "unreachable"],
    "available_when_offline": true,
    "default_state_when_offline": "offline"
  },
  "entities": [
    {
      "platform": "sensor",
      "key": "printer_status",
      "name": null,
      "device_class": "enum",
      "options": ["idle", "printing", "stopped", "offline"],
      "value_path": "state",
      "attributes": {
        "printer_info": "info",
        "serial": "serial",
        "location": "location",
        "message": "state_message",
        "reasons": "state_reasons",
        "pages_completed": "counters.pages_completed",
        "media_sheets_completed": "counters.media_sheets_completed",
        "more_info": "more_info"
      }
    },
    {
      "platform": "sensor",
      "key": "uptime",
      "name": "Betriebszeit",
      "device_class": "timestamp",
      "value_path": "booted_at"
    },
    {
      "platform": "sensor",
      "key": "marker",
      "is_collection": true,
      "collection_path": "markers",
      "collection_id_key": "name",
      "name": "{item.name}",
      "unit_of_measurement": "%",
      "state_class": "measurement",
      "value_path": "level",
      "attributes": {
        "marker_type": "marker_type",
        "high_level": "high_level",
        "low_level": "low_level",
        "color": "color"
      }
    },
    {
      "platform": "sensor",
      "key": "pages_completed",
      "name": "Gedruckte Seiten",
      "state_class": "total_increasing",
      "value_path": "counters.pages_completed"
    },
    {
      "platform": "switch",
      "key": "power",
      "name": "Drucker Strom",
      "value_path": "power",
      "actions": {
        "turn_on": {
          "tool": "printer_power_on",
          "args_template": { "wait_for_online": false }
        },
        "turn_off": {
          "tool": "printer_power_off",
          "args_template": {}
        }
      }
    },
    {
      "platform": "button",
      "key": "power_on_wait",
      "name": "Drucker Einschalten & Warten",
      "actions": {
        "press": {
          "tool": "printer_power_on",
          "args_template": { "wait_for_online": true }
        }
      }
    }
  ]
}
```
