"""Config flow and Options flow for Tuya Local Lamp integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
import tinytuya
import voluptuous as vol

from .const import (
    CONF_DEVICE_ID,
    CONF_DP_BRIGHT_OVERRIDE,
    CONF_DP_COLOR_OVERRIDE,
    CONF_DP_POWER_OVERRIDE,
    CONF_DP_TEMP_OVERRIDE,
    CONF_HOST,
    CONF_LOCAL_KEY,
    CONF_MAX_KELVIN,
    CONF_MIN_KELVIN,
    CONF_NAME,
    CONF_POLL_INTERVAL,
    CONF_PROTOCOL_VERSION,
    DEFAULT_MAX_KELVIN,
    DEFAULT_MIN_KELVIN,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    PROTOCOL_AUTO,
    PROTOCOLS,
)

_LOGGER = logging.getLogger(__name__)


def _validate_connection(data: dict[str, Any]) -> tuple[bool, str | None, dict[str, Any] | None]:
    """Test device connectivity and credentials in executor."""
    host = data[CONF_HOST].strip()
    device_id = data[CONF_DEVICE_ID].strip()
    local_key = data[CONF_LOCAL_KEY].strip()
    protocol_str = data.get(CONF_PROTOCOL_VERSION, PROTOCOL_AUTO)

    versions_to_try = [3.3, 3.4, 3.5, 3.1] if protocol_str == PROTOCOL_AUTO else [float(protocol_str)]

    last_error = None
    for version in versions_to_try:
        try:
            device = tinytuya.BulbDevice(
                dev_id=device_id,
                address=host,
                local_key=local_key,
                version=version,
            )
            device.set_socketTimeout(3)
            status = device.status()

            if isinstance(status, dict) and "dps" in status:
                return True, str(version), status
            if isinstance(status, dict) and "Error" in status:
                last_error = status["Error"]
        except Exception as err:
            last_error = str(err)

    _LOGGER.warning("Connection validation failed for %s (%s): %s", device_id, host, last_error)
    return False, None, None


class TuyaLampConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tuya Local Lamp."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return TuyaLampOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial user configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID].strip()
            user_input[CONF_HOST] = user_input[CONF_HOST].strip()
            user_input[CONF_DEVICE_ID] = device_id
            user_input[CONF_LOCAL_KEY] = user_input[CONF_LOCAL_KEY].strip()

            await self.async_set_unique_id(device_id)
            self._abort_if_unique_id_configured()

            # Validate connectivity with the device
            success, detected_version, _ = await self.hass.async_add_executor_job(
                _validate_connection, user_input
            )

            if success:
                if detected_version:
                    user_input[CONF_PROTOCOL_VERSION] = detected_version

                custom_name = user_input.get(CONF_NAME, "").strip()
                title = custom_name if custom_name else f"Tuya Lamp ({user_input[CONF_HOST]})"
                return self.async_create_entry(title=title, data=user_input)

            errors["base"] = "cannot_connect"

        schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=""): str,
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_DEVICE_ID): str,
                vol.Required(CONF_LOCAL_KEY): str,
                vol.Optional(CONF_PROTOCOL_VERSION, default=PROTOCOL_AUTO): vol.In(PROTOCOLS),
                vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.All(
                    vol.Coerce(int), vol.Range(min=5, max=120)
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )


class TuyaLampOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for tweaking Tuya lamp settings in the Web UI."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options form."""
        errors: dict[str, str] = {}

        data = self.config_entry.data
        opts = self.config_entry.options

        if user_input is not None:
            # If IP, key or version changed, test connection
            test_data = {
                CONF_HOST: user_input.get(CONF_HOST, opts.get(CONF_HOST, data.get(CONF_HOST))),
                CONF_DEVICE_ID: data.get(CONF_DEVICE_ID),
                CONF_LOCAL_KEY: user_input.get(
                    CONF_LOCAL_KEY, opts.get(CONF_LOCAL_KEY, data.get(CONF_LOCAL_KEY))
                ),
                CONF_PROTOCOL_VERSION: user_input.get(
                    CONF_PROTOCOL_VERSION,
                    opts.get(CONF_PROTOCOL_VERSION, data.get(CONF_PROTOCOL_VERSION)),
                ),
            }

            success, detected_version, _ = await self.hass.async_add_executor_job(
                _validate_connection, test_data
            )

            if success:
                if detected_version:
                    user_input[CONF_PROTOCOL_VERSION] = detected_version
                return self.async_create_entry(title="", data=user_input)

            errors["base"] = "cannot_connect"

        current_host = opts.get(CONF_HOST, data.get(CONF_HOST, ""))
        current_key = opts.get(CONF_LOCAL_KEY, data.get(CONF_LOCAL_KEY, ""))
        current_protocol = opts.get(
            CONF_PROTOCOL_VERSION, data.get(CONF_PROTOCOL_VERSION, PROTOCOL_AUTO)
        )
        current_poll = opts.get(
            CONF_POLL_INTERVAL, data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        )
        current_min_k = opts.get(
            CONF_MIN_KELVIN, data.get(CONF_MIN_KELVIN, DEFAULT_MIN_KELVIN)
        )
        current_max_k = opts.get(
            CONF_MAX_KELVIN, data.get(CONF_MAX_KELVIN, DEFAULT_MAX_KELVIN)
        )

        current_dp_power = opts.get(CONF_DP_POWER_OVERRIDE, "")
        current_dp_bright = opts.get(CONF_DP_BRIGHT_OVERRIDE, "")
        current_dp_temp = opts.get(CONF_DP_TEMP_OVERRIDE, "")
        current_dp_color = opts.get(CONF_DP_COLOR_OVERRIDE, "")

        options_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=current_host): str,
                vol.Required(CONF_LOCAL_KEY, default=current_key): str,
                vol.Optional(CONF_PROTOCOL_VERSION, default=current_protocol): vol.In(PROTOCOLS),
                vol.Optional(CONF_POLL_INTERVAL, default=current_poll): vol.All(
                    vol.Coerce(int), vol.Range(min=5, max=120)
                ),
                vol.Optional(CONF_MIN_KELVIN, default=current_min_k): vol.All(
                    vol.Coerce(int), vol.Range(min=1500, max=4000)
                ),
                vol.Optional(CONF_MAX_KELVIN, default=current_max_k): vol.All(
                    vol.Coerce(int), vol.Range(min=4000, max=9000)
                ),
                vol.Optional(CONF_DP_POWER_OVERRIDE, default=current_dp_power): str,
                vol.Optional(CONF_DP_BRIGHT_OVERRIDE, default=current_dp_bright): str,
                vol.Optional(CONF_DP_TEMP_OVERRIDE, default=current_dp_temp): str,
                vol.Optional(CONF_DP_COLOR_OVERRIDE, default=current_dp_color): str,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            errors=errors,
        )
