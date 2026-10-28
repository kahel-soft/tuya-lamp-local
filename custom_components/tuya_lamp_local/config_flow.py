"""Config flow and Options flow for Tuya Local Lamp integration."""
from __future__ import annotations

import json
import logging
import os
from typing import Any
import urllib.request

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
import tinytuya
import voluptuous as vol

from .const import (
    CONF_API_DEVICE_ID,
    CONF_API_KEY,
    CONF_API_REGION,
    CONF_API_SECRET,
    CONF_DEVICE_ID,
    CONF_DISCOVERY_METHOD,
    CONF_DP_BRIGHT_OVERRIDE,
    CONF_DP_COLOR_OVERRIDE,
    CONF_DP_POWER_OVERRIDE,
    CONF_DP_TEMP_OVERRIDE,
    CONF_FILE_PATH,
    CONF_HOST,
    CONF_JSON_DATA,
    CONF_LOCAL_KEY,
    CONF_MAX_KELVIN,
    CONF_MIN_KELVIN,
    CONF_NAME,
    CONF_POLL_INTERVAL,
    CONF_PROTOCOL_VERSION,
    CONF_SELECTED_DEVICE,
    CONF_SERVER_URL,
    DEFAULT_MAX_KELVIN,
    DEFAULT_MIN_KELVIN,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_TUYA_LOCAL_KEY_URL,
    DOMAIN,
    METHOD_CLOUD,
    METHOD_MANUAL,
    METHOD_TUYA_LOCAL_KEY,
    PROTOCOL_AUTO,
    PROTOCOLS,
    TUYA_REGIONS,
)

_LOGGER = logging.getLogger(__name__)


def _validate_connection(data: dict[str, Any]) -> tuple[bool, str | None, dict[str, Any] | None]:
    """Test device connectivity and credentials in executor."""
    host = data.get(CONF_HOST, "").strip()
    device_id = data.get(CONF_DEVICE_ID, "").strip()
    local_key = data.get(CONF_LOCAL_KEY, "").strip()
    protocol_str = data.get(CONF_PROTOCOL_VERSION, PROTOCOL_AUTO)

    if not host or not device_id or not local_key:
        return False, None, None

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


def _sync_fetch_cloud_devices(
    region: str, api_key: str, api_secret: str, api_device_id: str
) -> list[dict[str, Any]]:
    """Query Tuya Cloud for registered devices and local keys (runs in executor)."""
    cloud = tinytuya.Cloud(
        apiRegion=region,
        apiKey=api_key,
        apiSecret=api_secret,
        apiDeviceID=api_device_id,
    )
    res = cloud.getdevices()
    if isinstance(res, dict) and ("Error" in res or "Err" in res):
        err_msg = res.get("Payload") or res.get("Error") or "Cloud request failed"
        raise Exception(f"Tuya Cloud Error: {err_msg}")
    if not isinstance(res, list):
        raise Exception("Tuya Cloud returned an invalid response format")
    return res


def _sync_scan_lan() -> dict[str, dict[str, Any]]:
    """Scan local network for Tuya devices via UDP broadcast."""
    try:
        lan_res = tinytuya.deviceScan(verbose=False, maxretry=2)
        mapping: dict[str, dict[str, Any]] = {}
        if isinstance(lan_res, dict):
            for ip, dev in lan_res.items():
                dev_id = dev.get("gwId") or dev.get("id")
                if dev_id:
                    mapping[dev_id] = {
                        "ip": ip,
                        "version": str(dev.get("version", "auto")),
                    }
        return mapping
    except Exception as err:
        _LOGGER.debug("Tuya local network scan error: %s", err)
        return {}


def _parse_devices_json(raw_text: str, file_path: str = "") -> list[dict[str, Any]]:
    """Parse JSON string or file containing devices information."""
    content = raw_text.strip()
    if not content and file_path and os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()

    if not content:
        raise ValueError("Keine JSON-Daten angegeben oder Datei nicht gefunden")

    data = json.loads(content)
    raw_list: list[dict[str, Any]] = []

    if isinstance(data, list):
        raw_list = data
    elif isinstance(data, dict):
        if "result" in data and isinstance(data["result"], list):
            raw_list = data["result"]
        elif "devices" in data and isinstance(data["devices"], list):
            raw_list = data["devices"]
        else:
            raw_list = [data]

    normalized: list[dict[str, Any]] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        dev_id = (
            item.get("id")
            or item.get("gwId")
            or item.get("device_id")
            or item.get("deviceId")
            or item.get("devId")
        )
        key = (
            item.get("local_key")
            or item.get("key")
            or item.get("localKey")
            or item.get("localkey")
        )
        if not dev_id or not key:
            continue

        name = (
            item.get("name")
            or item.get("product_name")
            or item.get("productName")
            or f"Tuya Lamp {str(dev_id)[-6:]}"
        )
        ip = item.get("ip") or item.get("address") or item.get("local_ip", "")
        version = str(item.get("version") or item.get("protocol_version") or PROTOCOL_AUTO)
        category = item.get("category", "")

        normalized.append(
            {
                "name": str(name),
                "id": str(dev_id),
                "key": str(key),
                "ip": str(ip),
                "version": version,
                "category": category,
            }
        )
    return normalized


def _fetch_from_tuya_local_key_server(server_url: str) -> list[dict[str, Any]]:
    """Fetch devices JSON from running Tuya Local Key add-on/server."""
    server_url = server_url.strip().rstrip("/")
    if not server_url.startswith("http://") and not server_url.startswith("https://"):
        server_url = f"http://{server_url}"

    endpoints = [
        f"{server_url}/api/devices",
        f"{server_url}/devices",
        f"{server_url}/api/v1/devices",
        server_url,
    ]

    last_error = None
    for url in endpoints:
        try:
            req = urllib.request.Request(
                url,
                headers={"Accept": "application/json", "User-Agent": "HomeAssistant-TuyaLamp"},
            )
            with urllib.request.urlopen(req, timeout=4) as response:
                content = response.read().decode("utf-8")
                parsed = _parse_devices_json(content)
                if parsed:
                    return parsed
        except Exception as err:
            last_error = err
            continue

    raise Exception(f"Verbindung zu {server_url} fehlgeschlagen: {last_error}")


class TuyaLampConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tuya Local Lamp."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow state."""
        self._discovered_devices: dict[str, dict[str, Any]] = {}
        self._selected_device: dict[str, Any] | None = None

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
        """Handle the initial mode selection step."""
        if user_input is not None:
            method = user_input.get(CONF_DISCOVERY_METHOD)
            if method == METHOD_TUYA_LOCAL_KEY:
                return await self.async_step_tuya_local_key()
            if method == METHOD_CLOUD:
                return await self.async_step_cloud()
            return await self.async_step_manual()

        methods = {
            METHOD_TUYA_LOCAL_KEY: "Aus 'Tuya Local Key' Add-on (Server-URL oder Raw JSON)",
            METHOD_CLOUD: "Tuya IoT Developer Cloud (API Key & Secret)",
            METHOD_MANUAL: "Manuelle Direkteingabe (IP, ID, Local Key)",
        }

        schema = vol.Schema(
            {
                vol.Required(CONF_DISCOVERY_METHOD, default=METHOD_TUYA_LOCAL_KEY): vol.In(methods),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )

    async def async_step_tuya_local_key(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step to fetch from Tuya Local Key Add-on or paste its Raw JSON."""
        errors: dict[str, str] = {}

        if user_input is not None:
            raw_json = user_input.get(CONF_JSON_DATA, "").strip()
            server_url = user_input.get(CONF_SERVER_URL, "").strip()
            file_path = user_input.get(CONF_FILE_PATH, "").strip()

            parsed_list: list[dict[str, Any]] = []

            # 1. If JSON was pasted directly, parse it first
            if raw_json or (file_path and os.path.exists(file_path)):
                try:
                    parsed_list = _parse_devices_json(raw_json, file_path)
                except Exception as err:
                    _LOGGER.error("JSON parsing error: %s", err)
                    errors["base"] = "invalid_json"

            # 2. Otherwise try fetching from server URL
            elif server_url:
                try:
                    parsed_list = await self.hass.async_add_executor_job(
                        _fetch_from_tuya_local_key_server, server_url
                    )
                except Exception as err:
                    _LOGGER.warning("Could not fetch from server %s: %s", server_url, err)
                    errors["base"] = "cannot_connect_server"
            else:
                errors["base"] = "no_data_provided"

            if parsed_list:
                # Match with LAN scan for current IP addresses
                lan_mapping = await self.hass.async_add_executor_job(_sync_scan_lan)

                self._discovered_devices = {}
                for dev in parsed_list:
                    dev_id = dev["id"]
                    lan_info = lan_mapping.get(dev_id, {})
                    if not dev["ip"] and lan_info.get("ip"):
                        dev["ip"] = lan_info["ip"]
                    if dev["version"] == PROTOCOL_AUTO and lan_info.get("version"):
                        dev["version"] = lan_info["version"]

                    self._discovered_devices[dev_id] = dev

                if not self._discovered_devices:
                    errors["base"] = "no_devices_found"
                else:
                    return await self.async_step_select_device()

        schema = vol.Schema(
            {
                vol.Optional(CONF_JSON_DATA, default=""): str,
                vol.Optional(
                    CONF_SERVER_URL, default=DEFAULT_TUYA_LOCAL_KEY_URL
                ): str,
                vol.Optional(CONF_FILE_PATH, default=""): str,
            }
        )

        return self.async_show_form(
            step_id="tuya_local_key",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step to query official Tuya Cloud API for devices and local keys."""
        errors: dict[str, str] = {}

        if user_input is not None:
            region = user_input[CONF_API_REGION]
            api_key = user_input[CONF_API_KEY].strip()
            api_secret = user_input[CONF_API_SECRET].strip()
            api_dev_id = user_input[CONF_API_DEVICE_ID].strip()

            try:
                # 1. Fetch devices and keys from cloud
                cloud_devices = await self.hass.async_add_executor_job(
                    _sync_fetch_cloud_devices, region, api_key, api_secret, api_dev_id
                )

                # 2. Scan local LAN to match local IPs
                lan_mapping = await self.hass.async_add_executor_job(_sync_scan_lan)

                self._discovered_devices = {}
                for dev in cloud_devices:
                    dev_id = str(dev.get("id") or dev.get("gwId") or "")
                    local_key = str(dev.get("local_key") or dev.get("key") or "")
                    if not dev_id or not local_key:
                        continue

                    name = dev.get("name") or f"Tuya Lamp {dev_id[-6:]}"
                    lan_info = lan_mapping.get(dev_id, {})
                    ip = lan_info.get("ip") or dev.get("ip", "")
                    vers = lan_info.get("version") or dev.get("version", PROTOCOL_AUTO)
                    category = dev.get("category", "")

                    self._discovered_devices[dev_id] = {
                        "name": name,
                        "id": dev_id,
                        "key": local_key,
                        "ip": ip,
                        "version": vers,
                        "category": category,
                    }

                if not self._discovered_devices:
                    errors["base"] = "no_devices_found"
                else:
                    return await self.async_step_select_device()

            except Exception as err:
                _LOGGER.error("Failed to query Tuya Cloud: %s", err)
                errors["base"] = "cloud_fetch_error"

        schema = vol.Schema(
            {
                vol.Required(CONF_API_REGION, default="eu"): vol.In(TUYA_REGIONS),
                vol.Required(CONF_API_KEY): str,
                vol.Required(CONF_API_SECRET): str,
                vol.Required(CONF_API_DEVICE_ID): str,
            }
        )

        return self.async_show_form(
            step_id="cloud",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_select_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step to present a list of discovered devices for the user to choose."""
        current_ids = self._async_current_ids()

        # Filter out devices already configured in Home Assistant
        available_devices = {
            d_id: info
            for d_id, info in self._discovered_devices.items()
            if d_id not in current_ids
        }

        if not available_devices:
            return self.async_abort(reason="all_devices_configured")

        if user_input is not None:
            selected_id = user_input[CONF_SELECTED_DEVICE]
            self._selected_device = available_devices.get(selected_id)
            return await self.async_step_confirm_device()

        choices = {}
        for d_id, info in available_devices.items():
            name = info.get("name", "Tuya Lamp")
            ip = info.get("ip") or "IP suchen"
            cat = f" [{info['category']}]" if info.get("category") else ""
            choices[d_id] = f"{name} ({ip} | ID: {d_id[-6:]}){cat}"

        schema = vol.Schema(
            {
                vol.Required(CONF_SELECTED_DEVICE): vol.In(choices),
            }
        )

        return self.async_show_form(
            step_id="select_device",
            data_schema=schema,
            description_placeholders={"count": str(len(choices))},
        )

    async def async_step_confirm_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm parameters and test connection before saving."""
        errors: dict[str, str] = {}
        dev = self._selected_device or {}

        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID].strip()
            user_input[CONF_HOST] = user_input[CONF_HOST].strip()
            user_input[CONF_DEVICE_ID] = device_id
            user_input[CONF_LOCAL_KEY] = user_input[CONF_LOCAL_KEY].strip()

            await self.async_set_unique_id(device_id)
            self._abort_if_unique_id_configured()

            # Test connection
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
                vol.Optional(CONF_NAME, default=dev.get("name", "")): str,
                vol.Required(CONF_HOST, default=dev.get("ip", "")): str,
                vol.Required(CONF_DEVICE_ID, default=dev.get("id", "")): str,
                vol.Required(CONF_LOCAL_KEY, default=dev.get("key", "")): str,
                vol.Optional(
                    CONF_PROTOCOL_VERSION, default=dev.get("version", PROTOCOL_AUTO)
                ): vol.In(PROTOCOLS),
                vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.All(
                    vol.Coerce(int), vol.Range(min=5, max=120)
                ),
            }
        )

        return self.async_show_form(
            step_id="confirm_device",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle direct manual configuration."""
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
            step_id="manual",
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
