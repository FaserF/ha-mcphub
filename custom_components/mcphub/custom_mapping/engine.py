"""Execution engine for dynamic MCP custom device and entity mappings."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)

from ..client import MCPHubClient
from ..const import CONF_CUSTOM_MAPPINGS, DOMAIN
from .defaults import get_default_device_mappings
from .models import ActionMapping, DeviceMapping

_LOGGER = logging.getLogger(__name__)


def get_nested_value(data: Any, path: str, default: Any = None) -> Any:
    """Safely traverse a nested dictionary or list using dotted syntax."""
    if not path:
        return data
    current = data
    for part in path.split("."):
        if current is None:
            return default
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, (list, tuple)):
            try:
                idx = int(part)
                current = current[idx] if 0 <= idx < len(current) else default
            except ValueError:
                return default
        else:
            return default
    return current if current is not None else default


def render_template_str(template: str, context: dict[str, Any]) -> str:
    """Render double curly or single curly placeholder templates."""
    if not template or not isinstance(template, str):
        return str(template)

    def _replacer(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        val = get_nested_value(context, key, "")
        return str(val) if val is not None else ""

    # Replace {{ path }} or {path}
    res = re.sub(r"\{\{\s*([a-zA-Z0-9_\.]+)\s*\}\}", _replacer, template)
    return re.sub(r"\{([a-zA-Z0-9_\.]+)\}", _replacer, res)


def render_args_template(
    template_dict: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    """Recursively render argument templates with action and device context."""
    rendered: dict[str, Any] = {}
    for k, v in template_dict.items():
        if isinstance(v, str):
            # Check for pure value replacement e.g. "{{ action.volume }}" -> float/int
            stripped = v.strip()
            match = re.fullmatch(r"\{\{\s*([a-zA-Z0-9_\.]+)\s*\}\}", stripped)
            if match:
                raw_val = get_nested_value(context, match.group(1).strip())
                rendered[k] = raw_val if raw_val is not None else v
            else:
                rendered[k] = render_template_str(v, context)
        elif isinstance(v, dict):
            rendered[k] = render_args_template(v, context)
        else:
            rendered[k] = v
    return rendered


def extract_mac_connections(raw_macs: Any) -> set[tuple[str, str]]:
    """Parse and format MAC addresses for OpenWrt and HA device linking."""
    connections: set[tuple[str, str]] = set()
    if not raw_macs:
        return connections

    candidates = raw_macs if isinstance(raw_macs, (list, tuple, set)) else [raw_macs]
    for c in candidates:
        if isinstance(c, str) and c.strip():
            try:
                formatted = format_mac(c.strip())
                if formatted and formatted != "00:00:00:00:00:00":
                    connections.add((CONNECTION_NETWORK_MAC, formatted))
            except Exception:
                pass
    return connections


def extract_device_info(
    entry: ConfigEntry, mapping: DeviceMapping, device_data: dict[str, Any]
) -> DeviceInfo:
    """Build HA DeviceInfo from dynamic payload with automatic MAC linking."""
    ident_val = str(
        get_nested_value(device_data, mapping.device_identifier_key, mapping.id)
    )
    clean_id = ident_val.replace(":", "_").replace(".", "_")

    name = get_nested_value(
        device_data, mapping.device_info.name_path, mapping.name
    )
    if isinstance(name, str):
        name = name.replace("_", " ")

    manufacturer = get_nested_value(
        device_data, mapping.device_info.manufacturer_path, "Unknown"
    )
    model = get_nested_value(device_data, mapping.device_info.model_path, mapping.name)
    if isinstance(model, str):
        model = model.replace("_", " ")

    sw_version = get_nested_value(device_data, mapping.device_info.sw_version_path)
    serial = get_nested_value(device_data, mapping.device_info.serial_path)
    config_url = get_nested_value(
        device_data, mapping.device_info.configuration_url_path
    )

    raw_macs = get_nested_value(device_data, mapping.device_info.mac_path)
    connections = extract_mac_connections(raw_macs)

    info_kwargs: dict[str, Any] = {
        "identifiers": {(DOMAIN, f"{entry.entry_id}_{clean_id}")},
        "name": name,
        "manufacturer": manufacturer if manufacturer != "Unknown" else None,
        "model": model,
    }
    if sw_version:
        info_kwargs["sw_version"] = str(sw_version)
    if serial:
        info_kwargs["serial_number"] = str(serial)
    if config_url:
        info_kwargs["configuration_url"] = str(config_url)
    if connections:
        info_kwargs["connections"] = connections

    return DeviceInfo(**info_kwargs)


def sync_device_registry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    mapping: DeviceMapping,
    device_data: dict[str, Any],
) -> None:
    """Sync dynamic hardware specs and MAC network addresses to HA device registry."""
    ident_val = str(
        get_nested_value(device_data, mapping.device_identifier_key, mapping.id)
    )
    clean_id = ident_val.replace(":", "_").replace(".", "_")
    identifiers = {(DOMAIN, f"{entry.entry_id}_{clean_id}")}

    raw_mfr = get_nested_value(device_data, mapping.device_info.manufacturer_path)
    raw_model = get_nested_value(device_data, mapping.device_info.model_path)
    if isinstance(raw_model, str):
        raw_model = raw_model.replace("_", " ")
    raw_sw = get_nested_value(device_data, mapping.device_info.sw_version_path)
    raw_macs = get_nested_value(device_data, mapping.device_info.mac_path)
    connections = extract_mac_connections(raw_macs)

    try:
        dev_reg = dr.async_get(hass)
        device_entry = dev_reg.async_get_device(identifiers=identifiers)
        if device_entry:
            update_kwargs: dict[str, Any] = {}
            if raw_mfr and raw_mfr != "Unknown" and device_entry.manufacturer != raw_mfr:
                update_kwargs["manufacturer"] = str(raw_mfr)
            if raw_model and device_entry.model != raw_model:
                update_kwargs["model"] = str(raw_model)
            if raw_sw and device_entry.sw_version != str(raw_sw):
                update_kwargs["sw_version"] = str(raw_sw)
            if connections:
                update_kwargs["merge_connections"] = connections
            if update_kwargs:
                dev_reg.async_update_device(device_entry.id, **update_kwargs)
    except Exception as err:
        _LOGGER.debug("Device registry sync warning for %s: %s", clean_id, err)


def load_mappings_from_entry(entry: ConfigEntry) -> list[DeviceMapping]:
    """Load and merge user-defined custom mappings with system defaults."""
    raw_user_mappings = entry.options.get(
        CONF_CUSTOM_MAPPINGS,
        entry.data.get(CONF_CUSTOM_MAPPINGS),
    )

    defaults = {m.id: m for m in get_default_device_mappings()}
    if not raw_user_mappings:
        return list(defaults.values())

    user_mappings: list[DeviceMapping] = []
    if isinstance(raw_user_mappings, str):
        try:
            raw_user_mappings = json.loads(raw_user_mappings)
        except Exception:
            raw_user_mappings = []

    if isinstance(raw_user_mappings, list):
        for item in raw_user_mappings:
            if isinstance(item, dict):
                try:
                    user_mappings.append(DeviceMapping.from_dict(item))
                except Exception as exc:
                    _LOGGER.warning("Could not parse custom mapping %s: %s", item, exc)

    # Merge user mappings with defaults (user overrides by mapping id)
    merged: dict[str, DeviceMapping] = dict(defaults)
    for um in user_mappings:
        merged[um.id] = um

    return list(merged.values())


async def async_execute_mapping_action(
    client: MCPHubClient,
    action_mapping: ActionMapping,
    server_name: str,
    device_data: dict[str, Any],
    action_context: dict[str, Any],
) -> Any:
    """Execute an MCP tool call defined in an ActionMapping."""
    context = {
        "device": device_data,
        "action": action_context,
    }
    rendered_args = render_args_template(action_mapping.args_template, context)
    return await client.async_call_tool(server_name, action_mapping.tool, rendered_args)


async def async_poll_mapped_devices(
    client: MCPHubClient,
    mappings: list[DeviceMapping],
    connected_servers: set[str],
) -> dict[str, Any]:
    """Poll discovery tools for all active mappings without failing or raising exceptions."""
    results: dict[str, Any] = {}

    for mapping in mappings:
        if not mapping.enabled or mapping.server_name not in connected_servers:
            continue

        try:
            res = await client.async_call_tool(
                mapping.server_name, mapping.discovery_tool, mapping.discovery_params
            )
            parsed_payload: Any = None
            raw_text = ""
            content = res.get("content", []) if isinstance(res, dict) else []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    raw_text = item.get("text", "")
                    break

            if raw_text:
                try:
                    parsed_payload = json.loads(raw_text)
                except Exception:
                    parsed_payload = raw_text
            elif isinstance(res, dict):
                parsed_payload = res

            if parsed_payload is not None:
                results[mapping.id] = parsed_payload
        except Exception as err:
            _LOGGER.debug(
                "Graceful handling of offline/polling error for mapping %s: %s",
                mapping.id,
                err,
            )

    return results
