"""Home Assistant Light platform for Tuya Local Lamp."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    COLOR_TYPE_RGB_HEX_6,
    DOMAIN,
    MODE_COLOUR,
    MODE_WHITE,
    ha_brightness_to_tuya,
    ha_hs_to_tuya_hex,
    ha_kelvin_to_tuya,
    ha_rgb_to_tuya_hex,
    tuya_brightness_to_ha,
    tuya_hex_to_ha_hs,
    tuya_hex_to_ha_rgb,
    tuya_to_ha_kelvin,
)
from .coordinator import TuyaLampCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tuya Local Lamp light platform."""
    coordinator: TuyaLampCoordinator = hass.data[DOMAIN][entry.entry_id]

    known_unique_ids: set[str] = set()

    def _check_and_add_entities() -> None:
        """Inspect coordinator data and add newly discovered light entities."""
        new_entities: list[LightEntity] = []

        # 1. Main light entity
        main_uid = f"{coordinator.device_id}_light"
        if main_uid not in known_unique_ids:
            known_unique_ids.add(main_uid)
            new_entities.append(TuyaLocalLight(coordinator, entry))

        # 2. Auxiliary / Secondary light entity (e.g. Sockel / Base)
        if coordinator.has_aux_light:
            aux_uid = f"{coordinator.device_id}_aux"
            if aux_uid not in known_unique_ids:
                known_unique_ids.add(aux_uid)
                new_entities.append(TuyaLocalAuxLight(coordinator, entry))

        if new_entities:
            async_add_entities(new_entities)

    # Initial registration
    _check_and_add_entities()

    # Listen to subsequent coordinator data updates to dynamically add newly discovered channels
    entry.async_on_unload(coordinator.async_add_listener(_check_and_add_entities))


class TuyaLocalLight(CoordinatorEntity[TuyaLampCoordinator], LightEntity):
    """Representation of the main Tuya Local Lamp."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:lightbulb-multiple"

    def __init__(self, coordinator: TuyaLampCoordinator, entry: ConfigEntry) -> None:
        """Initialize the main light."""
        super().__init__(coordinator)
        self.entry = entry
        self._attr_unique_id = f"{coordinator.device_id}_light"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name=entry.title or f"Tuya Lamp {coordinator.device_id[-6:]}",
            manufacturer="Tuya",
            model=f"Wi-Fi Smart Lamp (Protocol {coordinator.protocol_str})",
        )

    @property
    def name(self) -> str | None:
        """Return entity name. If device has multiple light sources, label as 'Hauptlicht'."""
        if self.coordinator.has_aux_light:
            return "Hauptlicht"
        return None

    @property
    def min_color_temp_kelvin(self) -> int:
        """Return minimum supported color temperature in Kelvin."""
        return self.coordinator.min_kelvin

    @property
    def max_color_temp_kelvin(self) -> int:
        """Return maximum supported color temperature in Kelvin."""
        return self.coordinator.max_kelvin

    @property
    def _dps(self) -> dict[str, Any]:
        """Convenience property for current DPS map."""
        if self.coordinator.data and "dps" in self.coordinator.data:
            return self.coordinator.data["dps"]
        return {}

    @property
    def is_on(self) -> bool:
        """Return True if the main light is on."""
        power_on = bool(self._dps.get(self.coordinator.dp_power, False))
        if self.coordinator.dp_master_power:
            master_on = bool(self._dps.get(self.coordinator.dp_master_power, True))
            return power_on and master_on
        return power_on

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Flag supported color modes based on detected/configured DPs."""
        modes: set[ColorMode] = set()

        if self.coordinator.has_color:
            if self.coordinator.color_type == COLOR_TYPE_RGB_HEX_6:
                modes.add(ColorMode.RGB)
            else:
                modes.add(ColorMode.HS)

        if self.coordinator.has_color_temp:
            modes.add(ColorMode.COLOR_TEMP)

        if not modes:
            if self.coordinator.has_brightness:
                modes.add(ColorMode.BRIGHTNESS)
            else:
                modes.add(ColorMode.ONOFF)

        return modes

    @property
    def color_mode(self) -> ColorMode | None:
        """Return current operational color mode."""
        current_tuya_mode = self._dps.get(self.coordinator.dp_mode, MODE_WHITE)

        if current_tuya_mode == MODE_COLOUR and self.coordinator.has_color:
            if self.coordinator.color_type == COLOR_TYPE_RGB_HEX_6:
                return ColorMode.RGB
            return ColorMode.HS

        if self.coordinator.has_color_temp:
            return ColorMode.COLOR_TEMP
        if self.coordinator.has_brightness:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def brightness(self) -> int | None:
        """Return the current brightness (1-255)."""
        if not self.coordinator.has_brightness:
            return None

        current_tuya_mode = self._dps.get(self.coordinator.dp_mode, MODE_WHITE)

        # In color mode with HSV hex, brightness is encoded in the V component.
        # Also use HSV value if no separate white brightness DP is available.
        if (current_tuya_mode == MODE_COLOUR or not self._dps.get(self.coordinator.dp_brightness)) and self.coordinator.has_color and self.coordinator.color_type != COLOR_TYPE_RGB_HEX_6:
            hex_data = str(self._dps.get(self.coordinator.dp_color, ""))
            parsed = tuya_hex_to_ha_hs(hex_data)
            if parsed is not None:
                _, bright_ha = parsed
                return bright_ha

        val = self._dps.get(self.coordinator.dp_brightness)
        if val is None:
            return None
        return tuya_brightness_to_ha(
            int(val),
            min_tuya=self.coordinator.brightness_min,
            max_tuya=self.coordinator.brightness_max,
        )

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the current color temperature in Kelvin."""
        if not self.coordinator.has_color_temp:
            return None

        val = self._dps.get(self.coordinator.dp_color_temp)
        if val is None:
            return None
        return tuya_to_ha_kelvin(
            int(val),
            min_kelvin=self.coordinator.min_kelvin,
            max_kelvin=self.coordinator.max_kelvin,
            min_tuya=self.coordinator.color_temp_min,
            max_tuya=self.coordinator.color_temp_max,
            reverse=self.coordinator.color_temp_reverse,
        )

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the current HS color tuple."""
        if not self.coordinator.has_color or self.coordinator.color_type == COLOR_TYPE_RGB_HEX_6:
            return None

        hex_data = str(self._dps.get(self.coordinator.dp_color, ""))
        parsed = tuya_hex_to_ha_hs(hex_data)
        if parsed is not None:
            hs, _ = parsed
            return hs
        return None

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the current RGB color tuple."""
        if not self.coordinator.has_color or self.coordinator.color_type != COLOR_TYPE_RGB_HEX_6:
            return None

        hex_data = str(self._dps.get(self.coordinator.dp_color, ""))
        return tuya_hex_to_ha_rgb(hex_data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the main lamp on with requested parameters."""
        payload: dict[str, Any] = {
            self.coordinator.dp_power: True
        }
        if self.coordinator.dp_master_power:
            payload[self.coordinator.dp_master_power] = True

        # Handle Color (RGB)
        if ATTR_RGB_COLOR in kwargs and self.coordinator.has_color:
            rgb = kwargs[ATTR_RGB_COLOR]
            hex_str = ha_rgb_to_tuya_hex(rgb)
            payload[self.coordinator.dp_color] = hex_str
            if self.coordinator.dp_mode:
                payload[self.coordinator.dp_mode] = MODE_COLOUR

        # Handle Color (HS)
        elif ATTR_HS_COLOR in kwargs and self.coordinator.has_color:
            hs = kwargs[ATTR_HS_COLOR]
            bright = kwargs.get(ATTR_BRIGHTNESS, self.brightness or 255)
            hex_str = ha_hs_to_tuya_hex(hs, brightness_ha=bright)
            payload[self.coordinator.dp_color] = hex_str
            if self.coordinator.dp_mode:
                payload[self.coordinator.dp_mode] = MODE_COLOUR

        # Handle Color Temperature (Kelvin)
        elif ATTR_COLOR_TEMP_KELVIN in kwargs and self.coordinator.has_color_temp:
            kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
            tuya_temp = ha_kelvin_to_tuya(
                kelvin,
                min_kelvin=self.coordinator.min_kelvin,
                max_kelvin=self.coordinator.max_kelvin,
                min_tuya=self.coordinator.color_temp_min,
                max_tuya=self.coordinator.color_temp_max,
                reverse=self.coordinator.color_temp_reverse,
            )
            payload[self.coordinator.dp_color_temp] = tuya_temp
            if self.coordinator.dp_mode:
                payload[self.coordinator.dp_mode] = MODE_WHITE

            if ATTR_BRIGHTNESS in kwargs and self.coordinator.has_brightness:
                bright = kwargs[ATTR_BRIGHTNESS]
                payload[self.coordinator.dp_brightness] = ha_brightness_to_tuya(
                    bright,
                    min_tuya=self.coordinator.brightness_min,
                    max_tuya=self.coordinator.brightness_max,
                )

        # Handle Brightness only
        elif ATTR_BRIGHTNESS in kwargs:
            bright = kwargs[ATTR_BRIGHTNESS]
            current_tuya_mode = self._dps.get(self.coordinator.dp_mode, MODE_WHITE)

            if current_tuya_mode == MODE_COLOUR and self.coordinator.has_color and self.hs_color and self.coordinator.color_type != COLOR_TYPE_RGB_HEX_6:
                hex_str = ha_hs_to_tuya_hex(self.hs_color, brightness_ha=bright)
                payload[self.coordinator.dp_color] = hex_str
            elif self.coordinator.has_brightness:
                payload[self.coordinator.dp_brightness] = ha_brightness_to_tuya(
                    bright,
                    min_tuya=self.coordinator.brightness_min,
                    max_tuya=self.coordinator.brightness_max,
                )
                if self.coordinator.dp_mode:
                    payload[self.coordinator.dp_mode] = MODE_WHITE

        await self.coordinator.async_send_dps(payload)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the main lamp off."""
        await self.coordinator.async_send_dps({self.coordinator.dp_power: False})


class TuyaLocalAuxLight(CoordinatorEntity[TuyaLampCoordinator], LightEntity):
    """Representation of an auxiliary Tuya Local Lamp light (Sockel / Base / Secondary light)."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:floor-lamp"

    def __init__(self, coordinator: TuyaLampCoordinator, entry: ConfigEntry) -> None:
        """Initialize the auxiliary light."""
        super().__init__(coordinator)
        self.entry = entry
        self._attr_unique_id = f"{coordinator.device_id}_aux"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name=entry.title or f"Tuya Lamp {coordinator.device_id[-6:]}",
            manufacturer="Tuya",
            model=f"Wi-Fi Smart Lamp (Protocol {coordinator.protocol_str})",
        )

    @property
    def name(self) -> str | None:
        """Return entity name for the auxiliary light."""
        return "Sockel"

    @property
    def _dps(self) -> dict[str, Any]:
        """Convenience property for current DPS map."""
        if self.coordinator.data and "dps" in self.coordinator.data:
            return self.coordinator.data["dps"]
        return {}

    @property
    def is_on(self) -> bool:
        """Return True if the auxiliary light is on."""
        aux_on = bool(self._dps.get(self.coordinator.dp_aux_power, False))
        if self.coordinator.dp_master_power:
            master_on = bool(self._dps.get(self.coordinator.dp_master_power, True))
            return aux_on and master_on
        return aux_on

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Flag supported color modes based on detected aux DPs."""
        modes: set[ColorMode] = set()

        if self.coordinator.has_aux_color:
            modes.add(ColorMode.HS)

        if self.coordinator.has_aux_color_temp:
            modes.add(ColorMode.COLOR_TEMP)

        if not modes:
            if self.coordinator.has_aux_brightness:
                modes.add(ColorMode.BRIGHTNESS)
            else:
                modes.add(ColorMode.ONOFF)

        return modes

    @property
    def color_mode(self) -> ColorMode | None:
        """Return current operational color mode."""
        current_mode = self._dps.get(self.coordinator.dp_aux_mode, MODE_WHITE)
        if current_mode == MODE_COLOUR and self.coordinator.has_aux_color:
            return ColorMode.HS
        if self.coordinator.has_aux_color_temp:
            return ColorMode.COLOR_TEMP
        if self.coordinator.has_aux_brightness:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def brightness(self) -> int | None:
        """Return current brightness of the auxiliary light (1-255)."""
        if not self.coordinator.has_aux_brightness:
            return None

        current_mode = self._dps.get(self.coordinator.dp_aux_mode, MODE_WHITE)

        if (current_mode == MODE_COLOUR or not self._dps.get(self.coordinator.dp_aux_brightness)) and self.coordinator.has_aux_color:
            hex_data = str(self._dps.get(self.coordinator.dp_aux_color, ""))
            parsed = tuya_hex_to_ha_hs(hex_data)
            if parsed is not None:
                _, bright_ha = parsed
                return bright_ha

        val = self._dps.get(self.coordinator.dp_aux_brightness)
        if val is not None:
            return tuya_brightness_to_ha(
                int(val),
                min_tuya=self.coordinator.aux_brightness_min,
                max_tuya=self.coordinator.aux_brightness_max,
            )
        return None

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return current HS color of the auxiliary light."""
        if not self.coordinator.has_aux_color:
            return None

        hex_data = str(self._dps.get(self.coordinator.dp_aux_color, ""))
        parsed = tuya_hex_to_ha_hs(hex_data)
        if parsed is not None:
            hs, _ = parsed
            return hs
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the auxiliary light on with requested parameters."""
        payload: dict[str, Any] = {
            self.coordinator.dp_aux_power: True
        }
        if self.coordinator.dp_master_power:
            payload[self.coordinator.dp_master_power] = True

        # Handle Color (HS)
        if ATTR_HS_COLOR in kwargs and self.coordinator.has_aux_color:
            hs = kwargs[ATTR_HS_COLOR]
            bright = kwargs.get(ATTR_BRIGHTNESS, self.brightness or 255)
            hex_str = ha_hs_to_tuya_hex(hs, brightness_ha=bright)
            if self.coordinator.dp_aux_color:
                payload[self.coordinator.dp_aux_color] = hex_str
            if self.coordinator.dp_aux_mode:
                payload[self.coordinator.dp_aux_mode] = MODE_COLOUR

        # Handle Brightness only
        elif ATTR_BRIGHTNESS in kwargs:
            bright = kwargs[ATTR_BRIGHTNESS]
            current_mode = self._dps.get(self.coordinator.dp_aux_mode, MODE_WHITE)
            if current_mode == MODE_COLOUR and self.coordinator.has_aux_color and self.hs_color:
                hex_str = ha_hs_to_tuya_hex(self.hs_color, brightness_ha=bright)
                if self.coordinator.dp_aux_color:
                    payload[self.coordinator.dp_aux_color] = hex_str
            elif self.coordinator.dp_aux_brightness:
                payload[self.coordinator.dp_aux_brightness] = ha_brightness_to_tuya(
                    bright,
                    min_tuya=self.coordinator.aux_brightness_min,
                    max_tuya=self.coordinator.aux_brightness_max,
                )
                if self.coordinator.dp_aux_mode:
                    payload[self.coordinator.dp_aux_mode] = MODE_WHITE

        await self.coordinator.async_send_dps(payload)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the auxiliary light off."""
        await self.coordinator.async_send_dps({self.coordinator.dp_aux_power: False})
