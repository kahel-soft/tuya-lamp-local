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
from custom_components.tuya_lamp_local.light import TuyaLocalLight, TuyaLocalAuxLight


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
    from homeassistant.components.light import ColorMode

    hass = MagicMock()
    entry = MagicMock()
    entry.title = "Wohnzimmer Lampe"
    entry.data = {
        "host": "192.168.178.100",
        "device_id": "dummy_dual_id",
        "category": "dd",
    }
    entry.options = {}

    coord = TuyaLampCoordinator(hass, entry)
    coord._detect_datapoint_layout({"20": True, "101": True, "102": True, "103": 1000, "105": "000003e803e8", "106": "white"})

    sent_payloads = []
    async def mock_send_dps(payload):
        sent_payloads.append(payload)
    coord.async_send_dps = mock_send_dps

    aux = TuyaLocalAuxLight(coord, entry)

    # 1. Verify supported color modes contain HS and WHITE
    assert ColorMode.HS in aux.supported_color_modes
    assert ColorMode.WHITE in aux.supported_color_modes

    # 2. Turn on Aux Color (saturation > 0): must send DP 105, must NOT send DP 103!
    await aux.async_turn_on(hs_color=(240.0, 100.0), brightness=255)
    assert sent_payloads[-1]["102"] is True
    assert sent_payloads[-1]["106"] == MODE_COLOUR
    assert "105" in sent_payloads[-1]
    assert "103" not in sent_payloads[-1]

    # 3. Turn on Aux White via ATTR_WHITE: must send DP 103, must NOT send DP 105!
    await aux.async_turn_on(white=200)
    assert sent_payloads[-1]["102"] is True
    assert sent_payloads[-1]["106"] == MODE_WHITE
    assert "103" in sent_payloads[-1]
    assert "105" not in sent_payloads[-1]

    # 4. Pure white selected on color wheel (hs_color saturation == 0): seamless switch to real white!
    await aux.async_turn_on(hs_color=(0.0, 0.0), brightness=150)
    assert sent_payloads[-1]["102"] is True
    assert sent_payloads[-1]["106"] == MODE_WHITE
    assert "103" in sent_payloads[-1]
    assert "105" not in sent_payloads[-1]

    # 5. Turn off Aux
    await aux.async_turn_off()
    assert sent_payloads[-1]["102"] is False

    # 6. Verify property states in WHITE mode
    coord.data = {
        "dps": {
            "20": True,
            "101": True,
            "102": True,
            "103": 500,
            "105": "000003e803e8",
            "106": MODE_WHITE,
        }
    }
    assert aux.is_on is True
    assert aux.color_mode == ColorMode.WHITE
    assert aux.hs_color is None
    assert aux.brightness == tuya_brightness_to_ha(500, min_tuya=10, max_tuya=1000)

    # 7. Verify property states in COLOUR mode
    coord.data = {
        "dps": {
            "20": True,
            "101": True,
            "102": True,
            "103": 500,
            "105": "00f003e801f4",  # Blue (240), 50% bright (500)
            "106": MODE_COLOUR,
        }
    }
    assert aux.color_mode == ColorMode.HS
    assert aux.hs_color == (240.0, 100.0)
    assert aux.brightness == int(round((500 / 1000.0) * 255.0))


@pytest.mark.asyncio
async def test_tuya_local_hauptlicht_without_dp22():
    from custom_components.tuya_lamp_local.light import TuyaLocalLight
    from custom_components.tuya_lamp_local.const import MODE_COLOUR, MODE_WHITE
    from homeassistant.components.light import ColorMode

    hass = MagicMock()
    entry = MagicMock()
    entry.title = "Stehlampe Links"
    entry.data = {
        "host": "192.168.178.183",
        "device_id": "bfef89a9c04629c875q24u",
        "category": "dd",
    }
    entry.options = {}

    coord = TuyaLampCoordinator(hass, entry)
    # Dual fixture layout: DP 20, 21, 24, 101, 102, 103, 105, 106 - NO DP 22!
    coord._detect_datapoint_layout({
        "20": True,
        "21": "colour",
        "24": "00ee030c01d7",
        "101": True,
        "102": True,
        "103": 1000,
        "105": "00ee030c03e8",
        "106": "colour",
    })

    assert coord.dp_power == "101"
    assert coord.dp_master_power == "20"
    assert coord.dp_brightness is None  # Confirmed: no DP 22
    assert coord.has_brightness is True

    sent_payloads = []
    async def mock_send_dps(payload):
        sent_payloads.append(payload)
    coord.async_send_dps = mock_send_dps

    light = TuyaLocalLight(coord, entry)

    # 1. Supported color modes
    assert ColorMode.HS in light.supported_color_modes
    assert ColorMode.WHITE in light.supported_color_modes

    # 2. Brightness adjustment routes to DP 24 HSV without attempting DP 22!
    await light.async_turn_on(brightness=180)
    assert sent_payloads[-1]["101"] is True
    assert "24" in sent_payloads[-1]
    assert "22" not in sent_payloads[-1]

    # 3. White mode activation routes to DP 24 (Sat=0) and DP 21='white' without DP 22
    await light.async_turn_on(white=220)
    assert sent_payloads[-1]["101"] is True
    assert sent_payloads[-1]["21"] == MODE_WHITE
    assert "24" in sent_payloads[-1]
    assert "22" not in sent_payloads[-1]

    # 4. Property verification in WHITE mode
    coord.data = {
        "dps": {
            "20": True,
            "21": MODE_WHITE,
            "24": "0000000003e8",
            "101": True,
            "102": False,
        }
    }
    assert light.is_on is True
    assert light.color_mode == ColorMode.WHITE
    assert light.hs_color is None
    assert light.brightness == 255

    # 5. Property verification in COLOUR mode
    coord.data = {
        "dps": {
            "20": True,
            "21": MODE_COLOUR,
            "24": "007803e801f4",  # Green (120), 50% bright (500)
            "101": True,
            "102": False,
        }
    }
    assert light.color_mode == ColorMode.HS
    assert light.hs_color == (120.0, 100.0)
    assert light.brightness == int(round((500 / 1000.0) * 255.0))


@pytest.mark.asyncio
async def test_type_a_lamp_with_legacy_type_b_options():
    """Verify Type A lamp (DP 1-5) cleanly overrides legacy Type B defaults (20, 21, 22, 23, 24)."""
    entry = MagicMock()
    entry.title = "Flur - Lampe OG"
    entry.options = {
        "dp_power": "1",
        "dp_mode": "21",
        "dp_brightness": "22",
        "dp_color_temp": "23",
        "dp_color": "24",
    }
    entry.data = {
        "host": "192.168.178.186",
        "device_id": "bfa4bac177e534a935d6pm",
        "local_key": ">XX0ehL!4sbr'CiK",
        "category": "dj",
    }

    coord = TuyaLampCoordinator(MagicMock(), entry)
    coord._detect_datapoint_layout({"1": True})

    # Verify DPs mapped to 1-5, NOT 20-24
    assert coord.dp_power == "1"
    assert coord.dp_mode == "2"
    assert coord.dp_brightness == "3"
    assert coord.dp_color_temp == "4"
    assert coord.dp_color == "5"
    assert coord.brightness_min == 25
    assert coord.brightness_max == 255
    assert coord.color_temp_min == 0
    assert coord.color_temp_max == 255
    assert coord.color_type == COLOR_TYPE_RGBHSV_HEX_14

    sent_payloads = []
    async def mock_send_dps(payload):
        sent_payloads.append(payload)
    coord.async_send_dps = mock_send_dps

    light = TuyaLocalLight(coord, entry)

    # 1. Setting brightness sends DP 1, 3, 2='white'
    await light.async_turn_on(brightness=150)
    assert sent_payloads[-1]["1"] is True
    assert sent_payloads[-1]["2"] == "white"
    assert "3" in sent_payloads[-1]
    assert 25 <= sent_payloads[-1]["3"] <= 255
    assert "22" not in sent_payloads[-1]

    # 2. Setting color sends DP 1, 5 (14-char hex), 2='colour'
    await light.async_turn_on(hs_color=(120.0, 100.0), brightness=200)
    assert sent_payloads[-1]["1"] is True
    assert sent_payloads[-1]["2"] == "colour"
    assert len(sent_payloads[-1]["5"]) == 14
    assert "24" not in sent_payloads[-1]

