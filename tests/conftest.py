"""Test setup: mock homeassistant modules so tests can run in standalone python."""
import sys
from unittest.mock import MagicMock
from enum import StrEnum
from typing import Generic, TypeVar

T = TypeVar("T")

# Create mock homeassistant package
ha = MagicMock()
sys.modules["homeassistant"] = ha
sys.modules["homeassistant.core"] = MagicMock()
sys.modules["homeassistant.config_entries"] = MagicMock()
sys.modules["homeassistant.helpers"] = MagicMock()
sys.modules["homeassistant.helpers.update_coordinator"] = MagicMock()

class UpdateFailed(Exception):
    pass

class DataUpdateCoordinator(Generic[T]):
    def __init__(self, hass, logger, name, update_interval):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.data = {}

class CoordinatorEntity(Generic[T]):
    def __init__(self, coordinator):
        self.coordinator = coordinator

sys.modules["homeassistant.helpers.update_coordinator"].UpdateFailed = UpdateFailed
sys.modules["homeassistant.helpers.update_coordinator"].DataUpdateCoordinator = DataUpdateCoordinator
sys.modules["homeassistant.helpers.update_coordinator"].CoordinatorEntity = CoordinatorEntity

# Mock light platform
ha_light = MagicMock()
sys.modules["homeassistant.components"] = MagicMock()
sys.modules["homeassistant.components.light"] = ha_light

class ColorMode(StrEnum):
    ONOFF = "onoff"
    BRIGHTNESS = "brightness"
    COLOR_TEMP = "color_temp"
    HS = "hs"
    RGB = "rgb"
    WHITE = "white"

ha_light.ColorMode = ColorMode
ha_light.LightEntity = object
ha_light.ATTR_BRIGHTNESS = "brightness"
ha_light.ATTR_COLOR_TEMP_KELVIN = "color_temp_kelvin"
ha_light.ATTR_HS_COLOR = "hs_color"
ha_light.ATTR_RGB_COLOR = "rgb_color"
ha_light.ATTR_WHITE = "white"

sys.modules["homeassistant.helpers.device_registry"] = MagicMock()
sys.modules["homeassistant.helpers.entity_registry"] = MagicMock()
sys.modules["homeassistant.helpers.entity_platform"] = MagicMock()
sys.modules["homeassistant.const"] = MagicMock()
