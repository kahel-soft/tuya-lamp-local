"""DataUpdateCoordinator for managing Tuya local lamp connection and state."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import tinytuya

from .const import (
    COLOR_TYPE_HSV_HEX_12,
    COLOR_TYPE_RGB_HEX_6,
    CONF_AUX_BRIGHTNESS_MAX,
    CONF_AUX_BRIGHTNESS_MIN,
    CONF_BRIGHTNESS_MAX,
    CONF_BRIGHTNESS_MIN,
    CONF_COLOR_TEMP_MAX,
    CONF_COLOR_TEMP_MIN,
    CONF_COLOR_TEMP_REVERSE,
    CONF_COLOR_TYPE,
    CONF_DEVICE_ID,
    CONF_DP_AUX_BRIGHTNESS,
    CONF_DP_AUX_COLOR,
    CONF_DP_AUX_COLOR_TEMP,
    CONF_DP_AUX_MODE,
    CONF_DP_AUX_POWER,
    CONF_DP_BRIGHTNESS,
    CONF_DP_COLOR,
    CONF_DP_COLOR_TEMP,
    CONF_DP_MAIN_POWER,
    CONF_DP_MODE,
    CONF_DP_POWER,
    CONF_HOST,
    CONF_LOCAL_KEY,
    CONF_MAX_KELVIN,
    CONF_MIN_KELVIN,
    CONF_POLL_INTERVAL,
    CONF_PROTOCOL_VERSION,
    DEFAULT_AUX_BRIGHTNESS_MAX,
    DEFAULT_AUX_BRIGHTNESS_MIN,
    DEFAULT_BRIGHTNESS_MAX,
    DEFAULT_BRIGHTNESS_MIN,
    DEFAULT_COLOR_TEMP_MAX,
    DEFAULT_COLOR_TEMP_MIN,
    DEFAULT_MAX_KELVIN,
    DEFAULT_MIN_KELVIN,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    DP_AUX_BRIGHTNESS,
    DP_AUX_COLOR,
    DP_AUX_COLOR_TEMP,
    DP_AUX_MODE,
    DP_AUX_POWER,
    DP_AUX_SCENE,
    DP_LEGACY_BRIGHTNESS,
    DP_LEGACY_COLOR,
    DP_LEGACY_COLOR_TEMP,
    DP_LEGACY_MODE,
    DP_LEGACY_POWER,
    DP_MAIN_POWER,
    DP_MODERN_BRIGHTNESS,
    DP_MODERN_COLOR,
    DP_MODERN_COLOR_TEMP,
    DP_MODERN_MODE,
    DP_MODERN_POWER,
    PROTOCOL_AUTO,
)

_LOGGER = logging.getLogger(__name__)


class TuyaLampCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage Tuya device polling and command execution."""

    def __init__(self, hass: HomeAssistant, config_entry) -> None:
        """Initialize the coordinator."""
        self.entry = config_entry

        # Merge data and options (options take precedence for updates via Web UI)
        opts = config_entry.options or {}
        data = config_entry.data or {}

        self.host: str = opts.get(CONF_HOST, data.get(CONF_HOST, "")).strip()
        self.device_id: str = data.get(CONF_DEVICE_ID, "").strip()
        self.local_key: str = opts.get(CONF_LOCAL_KEY, data.get(CONF_LOCAL_KEY, "")).strip()
        self.protocol_str: str = opts.get(
            CONF_PROTOCOL_VERSION, data.get(CONF_PROTOCOL_VERSION, PROTOCOL_AUTO)
        )
        poll_interval: int = opts.get(CONF_POLL_INTERVAL, data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))

        # User-configured granular DP mappings
        user_power = str(opts.get(CONF_DP_POWER, data.get(CONF_DP_POWER, ""))).strip()
        user_mode = str(opts.get(CONF_DP_MODE, data.get(CONF_DP_MODE, ""))).strip()
        user_bright = str(opts.get(CONF_DP_BRIGHTNESS, data.get(CONF_DP_BRIGHTNESS, ""))).strip()
        user_temp = str(opts.get(CONF_DP_COLOR_TEMP, data.get(CONF_DP_COLOR_TEMP, ""))).strip()
        user_color = str(opts.get(CONF_DP_COLOR, data.get(CONF_DP_COLOR, ""))).strip()

        self.custom_dp_power = user_power if user_power and user_power != "auto" else None
        self.custom_dp_mode = user_mode if user_mode and user_mode != "auto" else None
        self.custom_dp_brightness = user_bright if user_bright and user_bright != "auto" else None
        self.custom_dp_color_temp = user_temp if user_temp and user_temp != "auto" else None
        self.custom_dp_color = user_color if user_color and user_color != "auto" else None

        # User-configured auxiliary / secondary light DP mappings
        user_aux_power = str(opts.get(CONF_DP_AUX_POWER, data.get(CONF_DP_AUX_POWER, ""))).strip()
        user_aux_bright = str(opts.get(CONF_DP_AUX_BRIGHTNESS, data.get(CONF_DP_AUX_BRIGHTNESS, ""))).strip()
        user_aux_color = str(opts.get(CONF_DP_AUX_COLOR, data.get(CONF_DP_AUX_COLOR, ""))).strip()
        user_aux_mode = str(opts.get(CONF_DP_AUX_MODE, data.get(CONF_DP_AUX_MODE, ""))).strip()
        user_aux_temp = str(opts.get(CONF_DP_AUX_COLOR_TEMP, data.get(CONF_DP_AUX_COLOR_TEMP, ""))).strip()

        self.custom_dp_aux_power = user_aux_power if user_aux_power and user_aux_power != "auto" else None
        self.custom_dp_aux_brightness = user_aux_bright if user_aux_bright and user_aux_bright != "auto" else None
        self.custom_dp_aux_color = user_aux_color if user_aux_color and user_aux_color != "auto" else None
        self.custom_dp_aux_mode = user_aux_mode if user_aux_mode and user_aux_mode != "auto" else None
        self.custom_dp_aux_color_temp = user_aux_temp if user_aux_temp and user_aux_temp != "auto" else None

        self.aux_brightness_min: int = int(
            opts.get(CONF_AUX_BRIGHTNESS_MIN, data.get(CONF_AUX_BRIGHTNESS_MIN, DEFAULT_AUX_BRIGHTNESS_MIN))
        )
        self.aux_brightness_max: int = int(
            opts.get(CONF_AUX_BRIGHTNESS_MAX, data.get(CONF_AUX_BRIGHTNESS_MAX, DEFAULT_AUX_BRIGHTNESS_MAX))
        )

        # Value ranges & scaling
        self.brightness_min: int = int(
            opts.get(CONF_BRIGHTNESS_MIN, data.get(CONF_BRIGHTNESS_MIN, DEFAULT_BRIGHTNESS_MIN))
        )
        self.brightness_max: int = int(
            opts.get(CONF_BRIGHTNESS_MAX, data.get(CONF_BRIGHTNESS_MAX, DEFAULT_BRIGHTNESS_MAX))
        )

        self.color_temp_min: int = int(
            opts.get(CONF_COLOR_TEMP_MIN, data.get(CONF_COLOR_TEMP_MIN, DEFAULT_COLOR_TEMP_MIN))
        )
        self.color_temp_max: int = int(
            opts.get(CONF_COLOR_TEMP_MAX, data.get(CONF_COLOR_TEMP_MAX, DEFAULT_COLOR_TEMP_MAX))
        )
        self.color_temp_reverse: bool = bool(
            opts.get(CONF_COLOR_TEMP_REVERSE, data.get(CONF_COLOR_TEMP_REVERSE, False))
        )

        self.min_kelvin: int = int(opts.get(CONF_MIN_KELVIN, data.get(CONF_MIN_KELVIN, DEFAULT_MIN_KELVIN)))
        self.max_kelvin: int = int(opts.get(CONF_MAX_KELVIN, data.get(CONF_MAX_KELVIN, DEFAULT_MAX_KELVIN)))

        self.color_type: str = str(
            opts.get(CONF_COLOR_TYPE, data.get(CONF_COLOR_TYPE, COLOR_TYPE_HSV_HEX_12))
        )

        # Socket lock: Tuya devices only allow 1 concurrent connection
        self._lock = asyncio.Lock()
        self._device: tinytuya.BulbDevice | None = None

        # Datapoint layout mapping (defaults before detection)
        self.dp_power: str = self.custom_dp_power or DP_MODERN_POWER
        self.dp_master_power: str | None = None
        self.dp_mode: str = self.custom_dp_mode or DP_MODERN_MODE
        self.dp_brightness: str = self.custom_dp_brightness or DP_MODERN_BRIGHTNESS
        self.dp_color_temp: str = self.custom_dp_color_temp or DP_MODERN_COLOR_TEMP
        self.dp_color: str = self.custom_dp_color or DP_MODERN_COLOR

        self.has_brightness: bool = False
        self.has_color_temp: bool = False
        self.has_color: bool = False

        # Secondary / Aux light layout mapping
        self.has_aux_light: bool = bool(self.custom_dp_aux_power)
        self.dp_aux_power: str = self.custom_dp_aux_power or DP_AUX_POWER
        self.dp_aux_brightness: str | None = self.custom_dp_aux_brightness or DP_AUX_BRIGHTNESS
        self.dp_aux_color: str | None = self.custom_dp_aux_color or DP_AUX_COLOR
        self.dp_aux_mode: str | None = self.custom_dp_aux_mode or DP_AUX_MODE
        self.dp_aux_color_temp: str | None = self.custom_dp_aux_color_temp or DP_AUX_COLOR_TEMP
        self.has_aux_brightness: bool = False
        self.has_aux_color: bool = False
        self.has_aux_color_temp: bool = False

        self._initialized: bool = False

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.device_id}",
            update_interval=timedelta(seconds=max(5, poll_interval)),
        )

    def _get_device(self) -> tinytuya.BulbDevice:
        """Get or initialize the TinyTuya BulbDevice instance."""
        if self._device is None:
            version_val = 3.3
            if self.protocol_str != PROTOCOL_AUTO:
                try:
                    version_val = float(self.protocol_str)
                except ValueError:
                    version_val = 3.3

            dev = tinytuya.BulbDevice(
                dev_id=self.device_id,
                address=self.host,
                local_key=self.local_key,
                version=version_val,
            )
            dev.set_socketTimeout(4)
            dev.set_dpsUsed({})
            self._device = dev
        return self._device

    def _sync_fetch_status(self) -> dict[str, Any]:
        """Synchronously query device status via TinyTuya (runs in executor)."""
        device = self._get_device()
        data = device.status()

        if not isinstance(data, dict):
            raise UpdateFailed(f"Invalid response from Tuya device: {data}")

        if "Error" in data:
            if self.protocol_str == PROTOCOL_AUTO:
                for candidate_version in [3.4, 3.5, 3.1]:
                    _LOGGER.debug(
                        "Auto-probing protocol %s for device %s",
                        candidate_version,
                        self.device_id,
                    )
                    device.set_version(candidate_version)
                    data = device.status()
                    if isinstance(data, dict) and "dps" in data:
                        _LOGGER.info(
                            "Discovered working protocol %s for device %s",
                            candidate_version,
                            self.device_id,
                        )
                        self.protocol_str = str(candidate_version)
                        break

        if "dps" not in data:
            error_msg = data.get("Error", "No DPS data returned")
            raise UpdateFailed(f"Device communication failed ({self.host}): {error_msg}")

        return data

    def _detect_datapoint_layout(self, dps: dict[str, Any]) -> None:
        """Inspect DPS dictionary to identify lamp capabilities and layout."""
        # 1. Main light switch & Master hardware switch
        if self.custom_dp_power:
            self.dp_power = self.custom_dp_power
            self.dp_master_power = None
        elif DP_MAIN_POWER in dps and DP_AUX_POWER in dps:
            # Dual-source fixture: DP 101 is main light switch, DP 20 is master hardware switch
            self.dp_power = DP_MAIN_POWER
            self.dp_master_power = DP_MODERN_POWER if DP_MODERN_POWER in dps else None
        elif DP_MODERN_POWER in dps:
            self.dp_power = DP_MODERN_POWER
            self.dp_master_power = None
        elif DP_LEGACY_POWER in dps:
            self.dp_power = DP_LEGACY_POWER
            self.dp_master_power = None
        else:
            self.dp_power = DP_MODERN_POWER
            self.dp_master_power = None

        if self.custom_dp_mode:
            self.dp_mode = self.custom_dp_mode
        elif DP_MODERN_MODE in dps:
            self.dp_mode = DP_MODERN_MODE
        elif DP_LEGACY_MODE in dps:
            self.dp_mode = DP_LEGACY_MODE

        if self.custom_dp_brightness:
            self.dp_brightness = self.custom_dp_brightness
        elif DP_MODERN_BRIGHTNESS in dps:
            self.dp_brightness = DP_MODERN_BRIGHTNESS
        elif DP_LEGACY_BRIGHTNESS in dps:
            self.dp_brightness = DP_LEGACY_BRIGHTNESS
            # If user didn't explicitly override brightness max, detect if legacy is 255
            bright_val = dps.get(DP_LEGACY_BRIGHTNESS, 0)
            if bright_val <= 255 and self.brightness_max == DEFAULT_BRIGHTNESS_MAX:
                self.brightness_max = 255

        if self.custom_dp_color_temp:
            self.dp_color_temp = self.custom_dp_color_temp
        elif DP_MODERN_COLOR_TEMP in dps:
            self.dp_color_temp = DP_MODERN_COLOR_TEMP
        elif DP_LEGACY_COLOR_TEMP in dps:
            self.dp_color_temp = DP_LEGACY_COLOR_TEMP
            temp_val = dps.get(DP_LEGACY_COLOR_TEMP, 0)
            if temp_val <= 255 and self.color_temp_max == DEFAULT_COLOR_TEMP_MAX:
                self.color_temp_max = 255

        if self.custom_dp_color:
            self.dp_color = self.custom_dp_color
        elif DP_MODERN_COLOR in dps:
            self.dp_color = DP_MODERN_COLOR
        elif DP_LEGACY_COLOR in dps:
            self.dp_color = DP_LEGACY_COLOR

        self.has_brightness = bool(self.dp_brightness in dps or self.custom_dp_brightness)
        self.has_color_temp = bool(self.dp_color_temp in dps or self.custom_dp_color_temp)
        self.has_color = bool(self.dp_color in dps or self.custom_dp_color)

        # If lamp has color (HSV) but no separate white brightness DP (e.g. floor lamps where brightness is in DP 24),
        # brightness is supported through the HSV color value
        if not self.has_brightness and self.has_color and self.color_type != COLOR_TYPE_RGB_HEX_6:
            self.has_brightness = True

        # 2. Auxiliary / Secondary light detection (e.g. Sockel / Base / Aux light)
        if self.custom_dp_aux_power or DP_AUX_POWER in dps:
            self.has_aux_light = True
            self.dp_aux_power = self.custom_dp_aux_power or DP_AUX_POWER
            self.dp_aux_brightness = self.custom_dp_aux_brightness or (DP_AUX_BRIGHTNESS if DP_AUX_BRIGHTNESS in dps else None)
            self.dp_aux_color = self.custom_dp_aux_color or (DP_AUX_COLOR if DP_AUX_COLOR in dps else None)
            self.dp_aux_mode = self.custom_dp_aux_mode or (DP_AUX_MODE if DP_AUX_MODE in dps else None)
            self.dp_aux_color_temp = self.custom_dp_aux_color_temp or (DP_AUX_COLOR_TEMP if DP_AUX_COLOR_TEMP in dps else None)

            self.has_aux_brightness = bool(self.dp_aux_brightness and (self.dp_aux_brightness in dps or self.custom_dp_aux_brightness))
            self.has_aux_color = bool(self.dp_aux_color and (self.dp_aux_color in dps or self.custom_dp_aux_color))
            self.has_aux_color_temp = bool(self.dp_aux_color_temp and (self.dp_aux_color_temp in dps or self.custom_dp_aux_color_temp))

            if not self.has_aux_brightness and self.has_aux_color:
                self.has_aux_brightness = True

            _LOGGER.info(
                "Tuya lamp (%s): Detected auxiliary light (Sockel/Base) -> Power=%s, Bright=%s (has=%s), Color=%s (has=%s), Mode=%s",
                self.device_id,
                self.dp_aux_power,
                self.dp_aux_brightness,
                self.has_aux_brightness,
                self.dp_aux_color,
                self.has_aux_color,
                self.dp_aux_mode,
            )

        _LOGGER.info(
            "Tuya lamp (%s) configured: Power=%s (master=%s), Bright=%s (min=%s, max=%s, has=%s), Temp=%s (min=%s, max=%s, rev=%s, has=%s), Color=%s (type=%s, has=%s), AuxLight=%s",
            self.device_id,
            self.dp_power,
            self.dp_master_power,
            self.dp_brightness,
            self.brightness_min,
            self.brightness_max,
            self.has_brightness,
            self.dp_color_temp,
            self.color_temp_min,
            self.color_temp_max,
            self.color_temp_reverse,
            self.has_color_temp,
            self.dp_color,
            self.color_type,
            self.has_color,
            self.has_aux_light,
        )
        self._initialized = True

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest state from the bulb."""
        async with self._lock:
            try:
                data = await self.hass.async_add_executor_job(self._sync_fetch_status)
            except Exception as err:
                raise UpdateFailed(f"Error communicating with Tuya lamp ({self.host}): {err}") from err

            dps = data.get("dps", {})
            if dps:
                if not self._initialized or (DP_AUX_POWER in dps and not self.has_aux_light):
                    self._detect_datapoint_layout(dps)

            return data

    def _sync_send_dps(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Synchronously send DP payload to Tuya device."""
        device = self._get_device()
        result = device.set_multiple_values(payload)
        return result

    async def async_send_dps(self, payload: dict[str, Any]) -> None:
        """Send DPS changes to device and update internal state optimistically."""
        async with self._lock:
            try:
                await self.hass.async_add_executor_job(self._sync_send_dps, payload)
            except Exception as err:
                _LOGGER.error("Failed to send command to Tuya lamp (%s): %s", self.host, err)
                raise

            if self.data and "dps" in self.data:
                updated_dps = dict(self.data["dps"])
                updated_dps.update(payload)
                self.data["dps"] = updated_dps
                self.async_set_updated_data(self.data)

    def close(self) -> None:
        """Close socket connection and cleanup resources."""
        if self._device is not None:
            try:
                self._device.close()
            except Exception as err:
                _LOGGER.debug("Error while closing TinyTuya device: %s", err)
            self._device = None
