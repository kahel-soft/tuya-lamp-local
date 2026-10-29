"""Unit tests for Tuya Local Lamp component."""
import pytest
from unittest.mock import MagicMock

from custom_components.tuya_lamp_local.const import (
    COLOR_TYPE_HSV_HEX_12,
    COLOR_TYPE_RGBHSV_HEX_14,
    COLOR_TYPE_RGB_HEX_6,
    DEFAULT_BRIGHTNESS_MAX,
    DEFAULT_BRIGHTNESS_MIN,
    DP_AUX_BRIGHTNESS,
    DP_AUX_COLOR,
    DP_AUX_POWER,
    DP_LEGACY_BRIGHTNESS,
    DP_LEGACY_COLOR,
    DP_LEGACY_COLOR_TEMP,
    DP_LEGACY_MODE,
    DP_LEGACY_POWER,
    DP_MAIN_POWER,
    DP_MODERN_POWER,
    ha_brightness_to_tuya,
    ha_hs_to_rgb,
    ha_hs_to_tuya_hex,
    ha_hs_to_tuya_hex_14,
    ha_kelvin_to_tuya,
    ha_rgb_to_hs,
    ha_rgb_to_tuya_hex,
    tuya_brightness_to_ha,
    tuya_hex_14_to_ha_hs,
    tuya_hex_to_ha_hs,
    tuya_hex_to_ha_rgb,
    tuya_to_ha_kelvin,
)
from custom_components.tuya_lamp_local.coordinator import TuyaLampCoordinator


def test_brightness_conversions():
    # Modern range 10-1000
    assert ha_brightness_to_tuya(255, 10, 1000) == 1000
    assert ha_brightness_to_tuya(1, 10, 1000) >= 10
    assert tuya_brightness_to_ha(1000, 10, 1000) == 255
    assert tuya_brightness_to_ha(10, 10, 1000) == 1

    # Legacy Type A range 25-255
    assert ha_brightness_to_tuya(255, 25, 255) == 255
    assert ha_brightness_to_tuya(1, 25, 255) >= 25
    assert tuya_brightness_to_ha(255, 25, 255) == 255
    assert tuya_brightness_to_ha(25, 25, 255) == 1
    # Mid-brightness
    tuya_mid = ha_brightness_to_tuya(128, 25, 255)
    ha_mid = tuya_brightness_to_ha(tuya_mid, 25, 255)
    assert abs(ha_mid - 128) <= 2


def test_color_temp_conversions():
    # Modern range 0-1000
    assert ha_kelvin_to_tuya(2700, 2700, 6500, 0, 1000) == 0
    assert ha_kelvin_to_tuya(6500, 2700, 6500, 0, 1000) == 1000
    assert tuya_to_ha_kelvin(0, 2700, 6500, 0, 1000) == 2700
    assert tuya_to_ha_kelvin(1000, 2700, 6500, 0, 1000) == 6500

    # Legacy Type A range 0-255
    assert ha_kelvin_to_tuya(2700, 2700, 6500, 0, 255) == 0
    assert ha_kelvin_to_tuya(6500, 2700, 6500, 0, 255) == 255
    assert tuya_to_ha_kelvin(0, 2700, 6500, 0, 255) == 2700
    assert tuya_to_ha_kelvin(255, 2700, 6500, 0, 255) == 6500


def test_14_char_color_encoding_and_decoding():
    # Test vectors directly from live test on Flur-Lampe (device 192.168.178.186):
    # Red: R=255, G=0, B=0, H=0, S=100%, V=100% -> ff00000000ffff
    red_hex = ha_hs_to_tuya_hex_14((0.0, 100.0), 255)
    assert red_hex == "ff00000000ffff"
    parsed_red = tuya_hex_14_to_ha_hs(red_hex)
    assert parsed_red is not None
    (h, s), v = parsed_red
    assert round(h) == 0
    assert round(s) == 100
    assert v == 255
    assert tuya_hex_to_ha_rgb(red_hex) == (255, 0, 0)

    # Green: R=0, G=255, B=0, H=120, S=100%, V=100% -> 00ff000078ffff
    green_hex = ha_hs_to_tuya_hex_14((120.0, 100.0), 255)
    assert green_hex == "00ff000078ffff"
    parsed_green = tuya_hex_14_to_ha_hs(green_hex)
    assert parsed_green is not None
    (h, s), v = parsed_green
    assert round(h) == 120
    assert round(s) == 100
    assert v == 255
    assert tuya_hex_to_ha_rgb(green_hex) == (0, 255, 0)

    # Blue: R=0, G=0, B=255, H=240, S=100%, V=100% -> 0000ff00f0ffff
    blue_hex = ha_hs_to_tuya_hex_14((240.0, 100.0), 255)
    assert blue_hex == "0000ff00f0ffff"
    parsed_blue = tuya_hex_14_to_ha_hs(blue_hex)
    assert parsed_blue is not None
    (h, s), v = parsed_blue
    assert round(h) == 240
    assert round(s) == 100
    assert v == 255
    assert tuya_hex_to_ha_rgb(blue_hex) == (0, 0, 255)

    # Auto-detection in tuya_hex_to_ha_hs
    assert tuya_hex_to_ha_hs(red_hex) == ((0.0, 100.0), 255)
    assert tuya_hex_to_ha_hs("000003e803e8") is not None  # 12-char format


def test_coordinator_type_a_lamp_detection():
    hass = MagicMock()
    entry = MagicMock()
    entry.title = "Flur - Lampe OG"
    entry.data = {
        "host": "192.168.178.186",
        "device_id": "bfa4bac177e534a935d6pm",
        "local_key": "dummy_key",
        "category": "dj",
    }
    entry.options = {}

    coord = TuyaLampCoordinator(hass, entry)

    # Simulate device reporting ONLY {'1': False} (the exact live behavior in standby)
    coord._detect_datapoint_layout({"1": False})

    assert coord.is_light is True
    assert coord.dp_power == "1"
    assert coord.dp_mode == "2"
    assert coord.dp_brightness == "3"
    assert coord.brightness_min == 25
    assert coord.brightness_max == 255
    assert coord.dp_color_temp == "4"
    assert coord.color_temp_min == 0
    assert coord.color_temp_max == 255
    assert coord.dp_color == "5"
    assert coord.color_type == COLOR_TYPE_RGBHSV_HEX_14
    assert coord.has_brightness is True
    assert coord.has_color_temp is True
    assert coord.has_color is True
    assert coord.has_aux_light is False


def test_coordinator_dual_fixture_lamp_detection():
    hass = MagicMock()
    entry = MagicMock()
    entry.title = "Wohnzimmer Stehlampe"
    entry.data = {
        "host": "192.168.178.100",
        "device_id": "dummy_dual_fixture_id",
        "local_key": "dummy_key",
        "category": "dj",
    }
    entry.options = {}

    coord = TuyaLampCoordinator(hass, entry)

    # Simulate dual fixture lamp reporting master 20, main 101, aux 102
    coord._detect_datapoint_layout({
        "20": True,
        "101": True,
        "102": False,
        "103": 500,
        "104": 200,
        "105": "000003e803e8",
        "106": "colour",
    })

    assert coord.is_light is True
    assert coord.dp_power == "101"
    assert coord.dp_master_power == "20"
    assert coord.has_aux_light is True
    assert coord.dp_aux_power == "102"
    assert coord.dp_aux_brightness == "103"
    assert coord.dp_aux_color == "105"
    assert coord.dp_aux_mode == "106"
    assert coord.has_aux_brightness is True
    assert coord.has_aux_color is True


def test_coordinator_socket_detection():
    hass = MagicMock()
    entry = MagicMock()
    entry.title = "Wohnzimmer Steckdose"
    entry.data = {
        "host": "192.168.178.101",
        "device_id": "dummy_socket_id",
        "local_key": "dummy_key",
        "category": "cz",
    }
    entry.options = {}

    coord = TuyaLampCoordinator(hass, entry)
    coord._detect_datapoint_layout({"1": True})

    assert coord.is_switch is True
    assert coord.is_socket is True
    assert coord.is_light is False
    assert "1" in coord.switch_dps


@pytest.mark.asyncio
async def test_tuya_local_light_type_a_operations():
    from custom_components.tuya_lamp_local.light import TuyaLocalLight
    from custom_components.tuya_lamp_local.const import (
        COLOR_TYPE_RGBHSV_HEX_14,
        MODE_COLOUR,
        MODE_WHITE,
    )
    from homeassistant.components.light import ColorMode

    hass = MagicMock()
    entry = MagicMock()
    entry.title = "Flur - Lampe OG"
    entry.data = {
        "host": "192.168.178.186",
        "device_id": "bfa4bac177e534a935d6pm",
        "category": "dj",
    }
    entry.options = {}

    coord = TuyaLampCoordinator(hass, entry)
    coord._detect_datapoint_layout({"1": True})

    # Mock async_send_dps
    sent_payloads = []
    async def mock_send_dps(payload):
        sent_payloads.append(payload)
    coord.async_send_dps = mock_send_dps

    light = TuyaLocalLight(coord, entry)

    # 1. Supported modes
    modes = light.supported_color_modes
    assert ColorMode.HS in modes
    assert ColorMode.COLOR_TEMP in modes

    # 2. Turn on Red (RGB)
    await light.async_turn_on(rgb_color=(255, 0, 0), brightness=255)
    assert sent_payloads[-1] == {
        "1": True,
        "2": MODE_COLOUR,
        "5": "ff00000000ffff",
    }

    # 3. Turn on Green (HS)
    await light.async_turn_on(hs_color=(120.0, 100.0), brightness=255)
    assert sent_payloads[-1] == {
        "1": True,
        "2": MODE_COLOUR,
        "5": "00ff000078ffff",
    }

    # 4. Turn on Warm White (Color Temp)
    await light.async_turn_on(color_temp_kelvin=2700, brightness=255)
    assert sent_payloads[-1] == {
        "1": True,
        "2": MODE_WHITE,
        "3": 255,
        "4": 0,
    }

    # 5. Turn on Cool White (6500K)
    await light.async_turn_on(color_temp_kelvin=6500, brightness=128)
    assert sent_payloads[-1] == {
        "1": True,
        "2": MODE_WHITE,
        "3": ha_brightness_to_tuya(128, min_tuya=25, max_tuya=255),
        "4": 255,
    }

    # 6. Turn off
    await light.async_turn_off()
    assert sent_payloads[-1] == {"1": False}


@pytest.mark.asyncio
async def test_tuya_local_aux_light_dual_fixture_operations():
    from custom_components.tuya_lamp_local.light import TuyaLocalAuxLight
    from custom_components.tuya_lamp_local.const import MODE_COLOUR, MODE_WHITE

    hass = MagicMock()
    entry = MagicMock()
    entry.title = "Wohnzimmer Lampe"
    entry.data = {
        "host": "192.168.178.100",
        "device_id": "dummy_dual_id",
        "category": "dj",
    }
    entry.options = {}

    coord = TuyaLampCoordinator(hass, entry)
    coord._detect_datapoint_layout({"20": True, "101": True, "102": True})

    sent_payloads = []
    async def mock_send_dps(payload):
        sent_payloads.append(payload)
    coord.async_send_dps = mock_send_dps

    aux = TuyaLocalAuxLight(coord, entry)

    # 1. Turn on Aux Color
    await aux.async_turn_on(hs_color=(0.0, 100.0), brightness=255)
    assert sent_payloads[-1]["102"] is True
    assert sent_payloads[-1]["106"] == MODE_COLOUR
    assert "105" in sent_payloads[-1]

    # 2. Turn on Aux White
    await aux.async_turn_on(color_temp_kelvin=2700, brightness=200)
    assert sent_payloads[-1]["102"] is True
    assert sent_payloads[-1]["106"] == MODE_WHITE
    assert "103" in sent_payloads[-1]

    # 3. Turn off Aux
    await aux.async_turn_off()
    assert sent_payloads[-1]["102"] is False
