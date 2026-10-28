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
    CONF_DEVICE_ID,
    CONF_DP_BRIGHT_OVERRIDE,
    CONF_DP_COLOR_OVERRIDE,
    CONF_DP_POWER_OVERRIDE,
    CONF_DP_TEMP_OVERRIDE,
    CONF_HOST,
    CONF_LOCAL_KEY,
    CONF_POLL_INTERVAL,
    CONF_PROTOCOL_VERSION,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    DP_LEGACY_BRIGHTNESS,
    DP_LEGACY_COLOR,
    DP_LEGACY_COLOR_TEMP,
    DP_LEGACY_MODE,
    DP_LEGACY_POWER,
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

        # Optional DP overrides from UI
        self._dp_power_override = opts.get(CONF_DP_POWER_OVERRIDE, "").strip()
        self._dp_bright_override = opts.get(CONF_DP_BRIGHT_OVERRIDE, "").strip()
        self._dp_temp_override = opts.get(CONF_DP_TEMP_OVERRIDE, "").strip()
        self._dp_color_override = opts.get(CONF_DP_COLOR_OVERRIDE, "").strip()

        # Socket lock: Tuya devices only allow 1 concurrent connection
        self._lock = asyncio.Lock()
        self._device: tinytuya.BulbDevice | None = None

        # Datapoint layout mapping (resolved dynamically upon initial connection)
        self.dp_power: str = self._dp_power_override or DP_MODERN_POWER
        self.dp_mode: str = DP_MODERN_MODE
        self.dp_brightness: str = self._dp_bright_override or DP_MODERN_BRIGHTNESS
        self.dp_color_temp: str = self._dp_temp_override or DP_MODERN_COLOR_TEMP
        self.dp_color: str = self._dp_color_override or DP_MODERN_COLOR

        self.max_brightness_tuya: int = 1000
        self.max_color_temp_tuya: int = 1000

        self.has_brightness: bool = False
        self.has_color_temp: bool = False
        self.has_color: bool = False
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
            # 4 seconds socket timeout - safe for HA Green without blocking the thread pool
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
            # If auto protocol was requested and 3.3 failed, probe 3.4/3.5
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
        """Inspect DPS dictionary to automatically identify lamp capabilities and layout."""
        if DP_MODERN_POWER in dps:
            # Modern Tuya Light (DP 20-24)
            self.dp_power = self._dp_power_override or DP_MODERN_POWER
            self.dp_mode = DP_MODERN_MODE
            self.dp_brightness = self._dp_bright_override or DP_MODERN_BRIGHTNESS
            self.dp_color_temp = self._dp_temp_override or DP_MODERN_COLOR_TEMP
            self.dp_color = self._dp_color_override or DP_MODERN_COLOR
            self.max_brightness_tuya = 1000
            self.max_color_temp_tuya = 1000
        elif DP_LEGACY_POWER in dps:
            # Legacy Tuya Light (DP 1-5)
            self.dp_power = self._dp_power_override or DP_LEGACY_POWER
            self.dp_mode = DP_LEGACY_MODE
            self.dp_brightness = self._dp_bright_override or DP_LEGACY_BRIGHTNESS
            self.dp_color_temp = self._dp_temp_override or DP_LEGACY_COLOR_TEMP
            self.dp_color = self._dp_color_override or DP_LEGACY_COLOR
            # Legacy devices frequently use 255 for brightness and temp
            bright_val = dps.get(self.dp_brightness, 0)
            self.max_brightness_tuya = 1000 if bright_val > 255 else 255
            self.max_color_temp_tuya = 1000 if bright_val > 255 else 255
        else:
            self.dp_power = self._dp_power_override or DP_MODERN_POWER
            self.dp_brightness = self._dp_bright_override or DP_MODERN_BRIGHTNESS
            self.dp_color_temp = self._dp_temp_override or DP_MODERN_COLOR_TEMP
            self.dp_color = self._dp_color_override or DP_MODERN_COLOR
            _LOGGER.warning("Could not clearly identify standard DP layout in: %s. Using configured/modern mappings", dps)

        self.has_brightness = self.dp_brightness in dps
        self.has_color_temp = self.dp_color_temp in dps
        self.has_color = self.dp_color in dps

        _LOGGER.info(
            "Tuya lamp (%s) layout detected: Power=%s, Bright=%s (has=%s, max=%s), Temp=%s (has=%s), Color=%s (has=%s)",
            self.device_id,
            self.dp_power,
            self.dp_brightness,
            self.has_brightness,
            self.max_brightness_tuya,
            self.dp_color_temp,
            self.has_color_temp,
            self.dp_color,
            self.has_color,
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
            if not self._initialized and dps:
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

            # Optimistic update: apply changes immediately to coordinator data
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
