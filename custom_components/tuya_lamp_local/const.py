"""Constants and helper calculations for Tuya Local Lamp."""
from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)

DOMAIN = "tuya_lamp_local"

# Configuration keys
CONF_NAME = "name"
CONF_HOST = "host"
CONF_DEVICE_ID = "device_id"
CONF_LOCAL_KEY = "local_key"
CONF_PROTOCOL_VERSION = "protocol_version"
CONF_POLL_INTERVAL = "poll_interval"
CONF_MIN_KELVIN = "min_kelvin"
CONF_MAX_KELVIN = "max_kelvin"

# Discovery & Import keys
CONF_DISCOVERY_METHOD = "discovery_method"
CONF_SERVER_URL = "server_url"
CONF_API_REGION = "api_region"
CONF_API_KEY = "api_key"
CONF_API_SECRET = "api_secret"
CONF_API_DEVICE_ID = "api_device_id"
CONF_JSON_DATA = "json_data"
CONF_FILE_PATH = "file_path"
CONF_SELECTED_DEVICE = "selected_device"

DEFAULT_TUYA_LOCAL_KEY_URL = "http://localhost:8000"

METHOD_TUYA_LOCAL_KEY = "tuya_local_key"
METHOD_CLOUD = "cloud"
METHOD_MANUAL = "manual"

TUYA_REGIONS = {
    "eu": "Central Europe (eu)",
    "us": "Western America (us)",
    "us-e": "Eastern America (us-e)",
    "cn": "China (cn)",
    "in": "India (in)",
}

# Optional DP Overrides (for exotic lamps)
CONF_DP_POWER_OVERRIDE = "dp_power_override"
CONF_DP_BRIGHT_OVERRIDE = "dp_bright_override"
CONF_DP_TEMP_OVERRIDE = "dp_temp_override"
CONF_DP_COLOR_OVERRIDE = "dp_color_override"

DEFAULT_POLL_INTERVAL = 15
DEFAULT_MIN_KELVIN = 2700
DEFAULT_MAX_KELVIN = 6500

# Protocols
PROTOCOL_AUTO = "auto"
PROTOCOL_31 = "3.1"
PROTOCOL_33 = "3.3"
PROTOCOL_34 = "3.4"
PROTOCOL_35 = "3.5"
PROTOCOLS = [PROTOCOL_AUTO, PROTOCOL_33, PROTOCOL_34, PROTOCOL_35, PROTOCOL_31]

# Datapoint schema definitions
# Modern DP layout (Type 20-24)
DP_MODERN_POWER = "20"
DP_MODERN_MODE = "21"
DP_MODERN_BRIGHTNESS = "22"
DP_MODERN_COLOR_TEMP = "23"
DP_MODERN_COLOR = "24"
DP_MODERN_SCENE = "25"

# Legacy DP layout (Type 1-5)
DP_LEGACY_POWER = "1"
DP_LEGACY_MODE = "2"
DP_LEGACY_BRIGHTNESS = "3"
DP_LEGACY_COLOR_TEMP = "4"
DP_LEGACY_COLOR = "5"

# Modes
MODE_WHITE = "white"
MODE_COLOUR = "colour"
MODE_SCENE = "scene"
MODE_MUSIC = "music"


def ha_brightness_to_tuya(ha_val: int, min_tuya: int = 10, max_tuya: int = 1000) -> int:
    """Convert Home Assistant brightness (1-255) to Tuya range (10-1000 or 10-255)."""
    if ha_val <= 0:
        return min_tuya
    ratio = max(0.0, min(1.0, ha_val / 255.0))
    return int(round(min_tuya + ratio * (max_tuya - min_tuya)))


def tuya_brightness_to_ha(tuya_val: int, min_tuya: int = 10, max_tuya: int = 1000) -> int:
    """Convert Tuya brightness range to Home Assistant brightness (1-255)."""
    if tuya_val <= min_tuya:
        return 1
    if tuya_val >= max_tuya:
        return 255
    ratio = (tuya_val - min_tuya) / float(max_tuya - min_tuya)
    return max(1, min(255, int(round(ratio * 255.0))))


def ha_kelvin_to_tuya(
    kelvin: int,
    min_kelvin: int = DEFAULT_MIN_KELVIN,
    max_kelvin: int = DEFAULT_MAX_KELVIN,
    max_tuya: int = 1000,
) -> int:
    """Convert Home Assistant color temperature (Kelvin) to Tuya integer (0-1000)."""
    clamped_k = max(min_kelvin, min(max_kelvin, kelvin))
    ratio = (clamped_k - min_kelvin) / float(max_kelvin - min_kelvin)
    return int(round(ratio * max_tuya))


def tuya_to_ha_kelvin(
    tuya_val: int,
    min_kelvin: int = DEFAULT_MIN_KELVIN,
    max_kelvin: int = DEFAULT_MAX_KELVIN,
    max_tuya: int = 1000,
) -> int:
    """Convert Tuya color temperature (0-1000) to Home Assistant Kelvin."""
    clamped_tuya = max(0, min(max_tuya, tuya_val))
    ratio = clamped_tuya / float(max_tuya)
    return int(round(min_kelvin + ratio * (max_kelvin - min_kelvin)))


def ha_hs_to_tuya_hex(hs: tuple[float, float], brightness_ha: int = 255) -> str:
    """Convert Home Assistant HS (hue 0-360, saturation 0-100) and brightness (1-255) to 12-char Tuya Hex (HHHHSSSSVVVV)."""
    hue, sat = hs
    h_int = int(round(hue)) % 360
    s_int = int(round((sat / 100.0) * 1000.0))
    v_int = int(round((brightness_ha / 255.0) * 1000.0))

    # Clamp values
    s_int = max(0, min(1000, s_int))
    v_int = max(10, min(1000, v_int))

    return f"{h_int:04x}{s_int:04x}{v_int:04x}"


def tuya_hex_to_ha_hs(hex_str: str) -> tuple[tuple[float, float], int] | None:
    """Parse 12-character Tuya HSV hex string into ((hue, saturation), brightness_ha)."""
    if not hex_str or len(hex_str) < 12:
        return None
    try:
        h_val = int(hex_str[0:4], 16)
        s_val = int(hex_str[4:8], 16)
        v_val = int(hex_str[8:12], 16)

        hue = float(h_val % 360)
        sat = float((s_val / 1000.0) * 100.0)
        bright_ha = int(round((v_val / 1000.0) * 255.0))
        return ((hue, max(0.0, min(100.0, sat))), max(1, min(255, bright_ha)))
    except (ValueError, IndexError) as err:
        _LOGGER.warning("Could not parse Tuya HSV hex '%s': %s", hex_str, err)
        return None
