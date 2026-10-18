"""Predefined default custom mappings for Android ADB and IPP Printer."""

from __future__ import annotations

from typing import Any

from .models import DeviceMapping

ADB_APP_MAP: dict[str, str] = {
    "YouTube": "com.google.android.youtube.tv",
    "SmartTube": "org.smarttube.stable",
    "SmartTube Beta": "com.liskovsoft.smarttubetv.beta",
    "Netflix": "com.netflix.ninja",
    "Prime Video": "com.amazon.amazonvideo.livingroom",
    "Disney+": "com.disney.disneyplus",
    "Jellyfin": "org.jellyfin.androidtv",
    "Emby": "tv.emby.embyatv",
    "Plex": "com.plexapp.android",
    "Plezy": "com.edde746.plezy",
    "Moonfin": "org.moonfin.androidtv",
    "Cloudstream": "com.lagradost.cloudstream3",
    "Kodi": "org.xbmc.kodi",
    "Crunchyroll": "com.crunchyroll.crunchyroid",
    "Twitch": "tv.twitch.android.app",
    "ARD Mediathek": "de.swr.avp.ard.tv",
    "ZDF Mediathek": "com.zdf.android.mediathek",
    "Joyn": "de.prosiebensat1digital.seventv",
    "Spotify": "com.spotify.tv.android",
    "SoundCloud": "com.soundcloud.android",
    "Bilibili": "com.bstar.intl.tv",
    "Cast Receiver": "com.instantbits.cast.receiver",
    "File Manager": "com.rs.explorer.filemanager",
    "APKMirror": "com.apkmirror.helper.prod",
    "Hermes Link": "de.fabiseitz.hermeslink.tv",
    "Settings": "com.android.tv.settings",
    "Home Screen": "com.google.android.tvlauncher",
    "Chrome": "com.android.chrome",
    "Telegram": "org.telegram.messenger",
    "WhatsApp": "com.whatsapp",
    "Kleinanzeigen": "com.ebay.kleinanzeigen",
    "Home Assistant": "io.homeassistant.companion.android",
}

DEFAULT_ADB_MAPPING_DICT: dict[str, Any] = {
    "id": "android_adb",
    "name": "Android ADB Devices",
    "server_name": "android-adb",
    "discovery_tool": "adb_devices",
    "discovery_params": {},
    "is_multi_device": True,
    "devices_path": "devices",
    "device_identifier_key": "serial",
    "device_info": {
        "name_path": "model",
        "manufacturer_path": "manufacturer",
        "model_path": "model",
        "sw_version_path": "androidVersion",
        "serial_path": "serial",
        "mac_path": "macs",
    },
    "offline_policy": {
        "status_key": "state",
        "offline_values": ["offline", "unauthorized", "disconnected"],
        "available_when_offline": True,
        "default_state_when_offline": "off",
    },
    "entities": [
        {
            "platform": "media_player",
            "key": "media_player",
            "name": None,
            "device_class": "tv",
            "value_path": "state",
            "current_source_path": "currentApp",
            "source_list": ADB_APP_MAP,
            "actions": {
                "turn_on": {
                    "tool": "adb_keyevent",
                    "args_template": {"device": "{{ device.serial }}", "keycode": "WAKEUP"},
                },
                "turn_off": {
                    "tool": "adb_keyevent",
                    "args_template": {"device": "{{ device.serial }}", "keycode": "SLEEP"},
                },
                "play": {
                    "tool": "adb_keyevent",
                    "args_template": {"device": "{{ device.serial }}", "keycode": "MEDIA_PLAY"},
                },
                "pause": {
                    "tool": "adb_keyevent",
                    "args_template": {"device": "{{ device.serial }}", "keycode": "MEDIA_PAUSE"},
                },
                "play_pause": {
                    "tool": "adb_keyevent",
                    "args_template": {"device": "{{ device.serial }}", "keycode": "MEDIA_PLAY_PAUSE"},
                },
                "stop": {
                    "tool": "adb_keyevent",
                    "args_template": {"device": "{{ device.serial }}", "keycode": "MEDIA_STOP"},
                },
                "next_track": {
                    "tool": "adb_keyevent",
                    "args_template": {"device": "{{ device.serial }}", "keycode": "MEDIA_NEXT"},
                },
                "previous_track": {
                    "tool": "adb_keyevent",
                    "args_template": {"device": "{{ device.serial }}", "keycode": "MEDIA_PREVIOUS"},
                },
                "volume_up": {
                    "tool": "adb_keyevent",
                    "args_template": {"device": "{{ device.serial }}", "keycode": "VOLUME_UP"},
                },
                "volume_down": {
                    "tool": "adb_keyevent",
                    "args_template": {"device": "{{ device.serial }}", "keycode": "VOLUME_DOWN"},
                },
                "volume_mute": {
                    "tool": "adb_keyevent",
                    "args_template": {"device": "{{ device.serial }}", "keycode": "VOLUME_MUTE"},
                },
                "select_source": {
                    "tool": "adb_app_launch",
                    "args_template": {
                        "app": "{{ action.app }}",
                        "device": "{{ device.serial }}",
                    },
                },
            },
        },
        {
            "platform": "remote",
            "key": "remote",
            "name": "Remote",
            "actions": {
                "turn_on": {
                    "tool": "adb_keyevent",
                    "args_template": {"device": "{{ device.serial }}", "keycode": "WAKEUP"},
                },
                "turn_off": {
                    "tool": "adb_keyevent",
                    "args_template": {"device": "{{ device.serial }}", "keycode": "SLEEP"},
                },
                "send_command": {
                    "tool": "adb_keyevent",
                    "args_template": {
                        "device": "{{ device.serial }}",
                        "keycode": "{{ action.command }}",
                    },
                },
            },
        },
    ],
}

DEFAULT_PRINTER_MAPPING_DICT: dict[str, Any] = {
    "id": "printer_ipp",
    "name": "HP LaserJet MFP M426fdw IPP",
    "server_name": "printer",
    "discovery_tool": "printer_status",
    "discovery_params": {},
    "is_multi_device": False,
    "device_identifier_key": "uuid",
    "device_info": {
        "name_path": "name",
        "manufacturer_path": "manufacturer",
        "model_path": "model",
        "sw_version_path": "sw_version",
        "serial_path": "serial",
        "mac_path": "mac",
        "configuration_url_path": "more_info",
    },
    "offline_policy": {
        "status_key": "online",
        "offline_values": [False, "false", "offline", "unreachable"],
        "available_when_offline": True,
        "default_state_when_offline": "offline",
    },
    "entities": [
        {
            "platform": "sensor",
            "key": "printer_status",
            "name": None,
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
                "more_info": "more_info",
            },
        },
        {
            "platform": "sensor",
            "key": "uptime",
            "name": "Betriebszeit",
            "device_class": "timestamp",
            "value_path": "booted_at",
        },
        {
            "platform": "sensor",
            "key": "marker",
            "is_collection": True,
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
                "color": "color",
            },
        },
        {
            "platform": "sensor",
            "key": "pages_completed",
            "name": "Gedruckte Seiten",
            "state_class": "total_increasing",
            "value_path": "counters.pages_completed",
        },
        {
            "platform": "switch",
            "key": "power",
            "name": "Drucker Strom",
            "value_path": "power",
            "actions": {
                "turn_on": {
                    "tool": "printer_power_on",
                    "args_template": {"wait_for_online": False},
                },
                "turn_off": {
                    "tool": "printer_power_off",
                    "args_template": {},
                },
            },
        },
        {
            "platform": "button",
            "key": "power_on_wait",
            "name": "Drucker Einschalten & Warten",
            "actions": {
                "press": {
                    "tool": "printer_power_on",
                    "args_template": {"wait_for_online": True},
                },
            },
        },
        {
            "platform": "binary_sensor",
            "key": "media_empty",
            "name": "Papier leer",
            "device_class": "problem",
            "value_path": "flags.media_empty",
        },
        {
            "platform": "binary_sensor",
            "key": "media_jam",
            "name": "Papierstau",
            "device_class": "problem",
            "value_path": "flags.media_jam",
        },
        {
            "platform": "binary_sensor",
            "key": "cover_open",
            "name": "Klappe offen",
            "device_class": "door",
            "value_path": "flags.cover_open",
        },
        {
            "platform": "binary_sensor",
            "key": "adf_loaded",
            "name": "Dokumenteneinzug (ADF) geladen",
            "device_class": "occupancy",
            "value_path": "flags.adf_loaded",
        },
        {
            "platform": "button",
            "key": "scan_to_paperless",
            "name": "Dokument Scannen & an Paperless senden",
            "actions": {
                "press": {
                    "tool": "printer_scan",
                    "args_template": {
                        "source": "Platen",
                        "color_mode": "RGB24",
                        "resolution": 300,
                        "upload_to_paperless": True,
                    },
                },
            },
        },
        {
            "platform": "button",
            "key": "scan_adf_to_paperless",
            "name": "Einzug (ADF) Scannen & an Paperless senden",
            "actions": {
                "press": {
                    "tool": "printer_scan",
                    "args_template": {
                        "source": "Feeder",
                        "color_mode": "RGB24",
                        "resolution": 300,
                        "duplex": True,
                        "upload_to_paperless": True,
                    },
                },
            },
        },
    ],
}

DEFAULT_MAPPINGS: list[dict[str, Any]] = [
    DEFAULT_ADB_MAPPING_DICT,
    DEFAULT_PRINTER_MAPPING_DICT,
]


def get_default_device_mappings() -> list[DeviceMapping]:
    """Return parsed default DeviceMapping list."""
    return [DeviceMapping.from_dict(d) for d in DEFAULT_MAPPINGS]
