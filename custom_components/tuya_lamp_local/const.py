"""Constants and helper calculations for Tuya Local Lamp."""
from __future__ import annotations

import colorsys
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

# Granular DP (DataPoint) configuration keys
CONF_DP_POWER = "dp_power"
CONF_DP_MODE = "dp_mode"
CONF_DP_BRIGHTNESS = "dp_brightness"
CONF_BRIGHTNESS_MIN = "brightness_min"
CONF_BRIGHTNESS_MAX = "brightness_max"

CONF_DP_COLOR_TEMP = "dp_color_temp"
CONF_COLOR_TEMP_MIN = "color_temp_min"
CONF_COLOR_TEMP_MAX = "color_temp_max"
CONF_COLOR_TEMP_REVERSE = "color_temp_reverse"
CONF_MIN_KELVIN = "min_kelvin"
CONF_MAX_KELVIN = "max_kelvin"

CONF_DP_COLOR = "dp_color"
CONF_COLOR_TYPE = "color_type"

# Device categorization & type overrides
CONF_CATEGORY = "category"
CONF_DEVICE_TYPE = "device_type"

DEVICE_TYPE_AUTO = "auto"
DEVICE_TYPE_LIGHT = "light"
DEVICE_TYPE_SWITCH = "switch"
DEVICE_TYPES = [DEVICE_TYPE_AUTO, DEVICE_TYPE_LIGHT, DEVICE_TYPE_SWITCH]

# Tuya device category codes
CATEGORY_SOCKETS = {"cz", "pc", "wk", "kg", "dlq", "tdq"}
CATEGORY_LIGHTS = {"dj", "dd", "xdd", "dc", "tyndj", "sbd", "fwd", "tgq"}

# Multi-light / Secondary (Aux / Base / Sockel) DP keys
CONF_DP_MAIN_POWER = "dp_main_power"
CONF_DP_AUX_POWER = "dp_aux_power"
CONF_DP_AUX_BRIGHTNESS = "dp_aux_brightness"
CONF_DP_AUX_COLOR = "dp_aux_color"
CONF_DP_AUX_MODE = "dp_aux_mode"
CONF_DP_AUX_COLOR_TEMP = "dp_aux_color_temp"
CONF_AUX_BRIGHTNESS_MIN = "aux_brightness_min"
CONF_AUX_BRIGHTNESS_MAX = "aux_brightness_max"

DEFAULT_AUX_BRIGHTNESS_MIN = 10
DEFAULT_AUX_BRIGHTNESS_MAX = 1000

# Color formats
COLOR_TYPE_HSV_HEX_12 = "hsv_hex_12"
COLOR_TYPE_RGBHSV_HEX_14 = "rgbhsv_hex_14"
COLOR_TYPE_RGB_HEX_6 = "rgb_hex_6"
COLOR_TYPES = [COLOR_TYPE_HSV_HEX_12, COLOR_TYPE_RGBHSV_HEX_14, COLOR_TYPE_RGB_HEX_6]

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
CONF_SELECTED_DEVICES = "selected_devices"

DEFAULT_TUYA_LOCAL_KEY_URL = "http://localhost:8000"

METHOD_CACHED = "cached"
METHOD_TUYA_LOCAL_KEY_SERVER = "tuya_local_key_server"
METHOD_TUYA_LOCAL_KEY_JSON = "tuya_local_key_json"
METHOD_CLOUD = "cloud"
METHOD_MANUAL = "manual"

TUYA_REGIONS = {
    "eu": "Central Europe (eu)",
    "us": "Western America (us)",
    "us-e": "Eastern America (us-e)",
    "cn": "China (cn)",
    "in": "India (in)",
}

DEFAULT_POLL_INTERVAL = 15
DEFAULT_MIN_KELVIN = 2700
DEFAULT_MAX_KELVIN = 6500

DEFAULT_BRIGHTNESS_MIN = 10
DEFAULT_BRIGHTNESS_MAX = 1000
DEFAULT_COLOR_TEMP_MIN = 0
DEFAULT_COLOR_TEMP_MAX = 1000

# Protocols
PROTOCOL_AUTO = "auto"
PROTOCOL_31 = "3.1"
PROTOCOL_33 = "3.3"
PROTOCOL_34 = "3.4"
PROTOCOL_35 = "3.5"
PROTOCOLS = [PROTOCOL_AUTO, PROTOCOL_33, PROTOCOL_34, PROTOCOL_35, PROTOCOL_31]

# Default Datapoint schema definitions
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

# Multi-light & Auxiliary DPs (Standard Tuya dual-channel lighting, e.g. Floor lamp + Base/Sockel)
DP_MAIN_POWER = "101"
DP_AUX_POWER = "102"
DP_AUX_BRIGHTNESS = "103"
DP_AUX_COLOR_TEMP = "104"
DP_AUX_COLOR = "105"
DP_AUX_MODE = "106"
DP_AUX_SCENE = "107"

# Modes
MODE_WHITE = "white"
MODE_COLOUR = "colour"
MODE_SCENE = "scene"
MODE_MUSIC = "music"


def to_bool(val: Any, default: bool = False) -> bool:
    """Safely convert boolean, integer, or string representation to a boolean."""
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    if isinstance(val, str):
        v = val.strip().lower()
        if v in ("true", "1", "on", "yes", "t"):
            return True
        if v in ("false", "0", "off", "no", "f", ""):
            return False
    return default


def ha_brightness_to_tuya(
    ha_val: int | float | None,
    min_tuya: int = DEFAULT_BRIGHTNESS_MIN,
    max_tuya: int = DEFAULT_BRIGHTNESS_MAX,
) -> int:
    """Convert Home Assistant brightness (1-255) to Tuya range."""
    if ha_val is None or ha_val <= 0:
        return min_tuya
    try:
        val = float(ha_val)
    except (ValueError, TypeError):
        return min_tuya
    ratio = max(0.0, min(1.0, val / 255.0))
    return int(round(min_tuya + ratio * (max_tuya - min_tuya)))


def tuya_brightness_to_ha(
    tuya_val: int | str | None,
    min_tuya: int = DEFAULT_BRIGHTNESS_MIN,
    max_tuya: int = DEFAULT_BRIGHTNESS_MAX,
) -> int:
    """Convert Tuya brightness range to Home Assistant brightness (1-255)."""
    if tuya_val is None:
        return 1
    try:
        val = int(tuya_val)
    except (ValueError, TypeError):
        return 1
    if max_tuya <= min_tuya:
        return 255 if val >= max_tuya else 1
    if val <= min_tuya:
        return 1
    if val >= max_tuya:
        return 255
    ratio = (val - min_tuya) / float(max_tuya - min_tuya)
    return max(1, min(255, int(round(ratio * 255.0))))


def ha_kelvin_to_tuya(
    kelvin: int | float | None,
    min_kelvin: int = DEFAULT_MIN_KELVIN,
    max_kelvin: int = DEFAULT_MAX_KELVIN,
    min_tuya: int = DEFAULT_COLOR_TEMP_MIN,
    max_tuya: int = DEFAULT_COLOR_TEMP_MAX,
    reverse: bool = False,
) -> int:
    """Convert Home Assistant color temperature (Kelvin) to Tuya integer."""
    if kelvin is None:
        return min_tuya
    try:
        k = float(kelvin)
    except (ValueError, TypeError):
        return min_tuya
    clamped_k = max(min_kelvin, min(max_kelvin, k))
    if max_kelvin <= min_kelvin:
        ratio = 0.0
    else:
        ratio = (clamped_k - min_kelvin) / float(max_kelvin - min_kelvin)
    if reverse:
        ratio = 1.0 - ratio
    return int(round(min_tuya + ratio * (max_tuya - min_tuya)))


def tuya_to_ha_kelvin(
    tuya_val: int | str | None,
    min_kelvin: int = DEFAULT_MIN_KELVIN,
    max_kelvin: int = DEFAULT_MAX_KELVIN,
    min_tuya: int = DEFAULT_COLOR_TEMP_MIN,
    max_tuya: int = DEFAULT_COLOR_TEMP_MAX,
    reverse: bool = False,
) -> int:
    """Convert Tuya color temperature to Home Assistant Kelvin."""
    if tuya_val is None:
        return min_kelvin
    try:
        val = int(tuya_val)
    except (ValueError, TypeError):
        return min_kelvin
    clamped_tuya = max(min_tuya, min(max_tuya, val))
    if max_tuya <= min_tuya:
        ratio = 0.0
    else:
        ratio = (clamped_tuya - min_tuya) / float(max_tuya - min_tuya)
    if reverse:
        ratio = 1.0 - ratio
    return int(round(min_kelvin + ratio * (max_kelvin - min_kelvin)))


def ha_rgb_to_hs(rgb: tuple[int, int, int]) -> tuple[float, float]:
    """Convert Home Assistant RGB tuple (0-255) to HS tuple ((0-360), (0-100))."""
    r, g, b = [max(0, min(255, x)) / 255.0 for x in rgb]
    h, s, _ = colorsys.rgb_to_hsv(r, g, b)
    return (round(h * 360.0, 1), round(s * 100.0, 1))


def ha_hs_to_rgb(hs: tuple[float, float], brightness_ha: int = 255) -> tuple[int, int, int]:
    """Convert Home Assistant HS and brightness (1-255) to RGB tuple."""
    hue, sat = hs
    h = (hue % 360.0) / 360.0
    s = max(0.0, min(100.0, sat)) / 100.0
    v = max(0.0, min(255.0, brightness_ha)) / 255.0
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(round(r * 255.0)), int(round(g * 255.0)), int(round(b * 255.0)))


def ha_hs_to_tuya_hex(hs: tuple[float, float], brightness_ha: int = 255) -> str:
    """Convert Home Assistant HS and brightness (1-255) to 12-char Tuya Hex (HHHHSSSSVVVV)."""
    hue, sat = hs
    h_int = int(round(hue)) % 360
    s_int = int(round((sat / 100.0) * 1000.0))
    v_int = int(round((brightness_ha / 255.0) * 1000.0))

    s_int = max(0, min(1000, s_int))
    v_int = max(10, min(1000, v_int))

    return f"{h_int:04x}{s_int:04x}{v_int:04x}"


def ha_hs_to_tuya_hex_14(hs: tuple[float, float], brightness_ha: int = 255) -> str:
    """Convert Home Assistant HS and brightness (1-255) to 14-char Tuya Hex (RRGGBBHHHHSSVV)."""
    hue, sat = hs
    rgb = ha_hs_to_rgb(hs, brightness_ha=brightness_ha)
    rgb_hex = f"{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
    h_int = int(round(hue)) % 360
    s_int = int(round((max(0.0, min(100.0, sat)) / 100.0) * 255.0))
    s_int = max(0, min(255, s_int))
    v_int = max(1, min(255, int(round(brightness_ha))))
    return f"{rgb_hex}{h_int:04x}{s_int:02x}{v_int:02x}"


def tuya_hex_14_to_ha_hs(hex_str: str) -> tuple[tuple[float, float], int] | None:
    """Parse 14-character Tuya hex string (RRGGBBHHHHSSVV) into ((hue, saturation), brightness_ha)."""
    if not hex_str or len(hex_str.strip()) < 14:
        return None
    s = hex_str.strip()
    try:
        h_val = int(s[6:10], 16) % 360
        s_val = int(s[10:12], 16)
        v_val = int(s[12:14], 16)

        hue = float(h_val)
        sat = float((s_val / 255.0) * 100.0)
        bright_ha = max(1, min(255, v_val))
        return ((hue, max(0.0, min(100.0, sat))), bright_ha)
    except (ValueError, IndexError) as err:
        _LOGGER.warning("Could not parse 14-char Tuya hex '%s': %s", s, err)
        return None


def tuya_hex_to_ha_hs(hex_str: str) -> tuple[tuple[float, float], int] | None:
    """Parse Tuya HSV/RGB hex string (14-char, 12-char, or 6-char) into ((hue, saturation), brightness_ha)."""
    if not hex_str:
        return None
    s = str(hex_str).strip()
    if len(s) == 14:
        return tuya_hex_14_to_ha_hs(s)
    if len(s) >= 12:
        try:
            h_val = int(s[0:4], 16)
            s_val = int(s[4:8], 16)
            v_val = int(s[8:12], 16)

            hue = float(h_val % 360)
            sat = float((s_val / 1000.0) * 100.0)
            bright_ha = int(round((v_val / 1000.0) * 255.0))
            return ((hue, max(0.0, min(100.0, sat))), max(1, min(255, bright_ha)))
        except (ValueError, IndexError) as err:
            _LOGGER.warning("Could not parse Tuya HSV hex '%s': %s", s, err)
            return None
    if len(s) >= 6:
        rgb = tuya_hex_to_ha_rgb(s)
        if rgb is not None:
            return (ha_rgb_to_hs(rgb), 255)
    return None


def ha_rgb_to_tuya_hex(rgb: tuple[int, int, int]) -> str:
    """Convert Home Assistant RGB tuple to 6-char hex string (RRGGBB)."""
    r, g, b = rgb
    return f"{r:02x}{g:02x}{b:02x}"


def tuya_hex_to_ha_rgb(hex_str: str) -> tuple[int, int, int] | None:
    """Parse hex string (first 6 characters as RRGGBB) into RGB tuple."""
    if not hex_str:
        return None
    s = str(hex_str).strip()
    if len(s) < 6:
        return None
    try:
        r = int(s[0:2], 16)
        g = int(s[2:4], 16)
        b = int(s[4:6], 16)
        return (r, g, b)
    except (ValueError, IndexError):
        return None

