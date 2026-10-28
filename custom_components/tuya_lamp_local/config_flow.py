"""Config flow and Options flow for Tuya Local Lamp integration."""
from __future__ import annotations

import ipaddress
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
    COLOR_TYPES,
    COLOR_TYPE_HSV_HEX_12,
    COLOR_TYPE_RGB_HEX_6,
    CONF_API_DEVICE_ID,
    CONF_API_KEY,
    CONF_API_REGION,
    CONF_API_SECRET,
    CONF_BRIGHTNESS_MAX,
    CONF_BRIGHTNESS_MIN,
    CONF_COLOR_TEMP_MAX,
    CONF_COLOR_TEMP_MIN,
    CONF_COLOR_TEMP_REVERSE,
    CONF_COLOR_TYPE,
    CONF_DEVICE_ID,
    CONF_DISCOVERY_METHOD,
    CONF_DP_BRIGHTNESS,
    CONF_DP_COLOR,
    CONF_DP_COLOR_TEMP,
    CONF_DP_MODE,
    CONF_DP_POWER,
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
    DEFAULT_BRIGHTNESS_MAX,
    DEFAULT_BRIGHTNESS_MIN,
    DEFAULT_COLOR_TEMP_MAX,
    DEFAULT_COLOR_TEMP_MIN,
    DEFAULT_MAX_KELVIN,
    DEFAULT_MIN_KELVIN,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_TUYA_LOCAL_KEY_URL,
    DOMAIN,
    METHOD_CLOUD,
    METHOD_MANUAL,
    METHOD_TUYA_LOCAL_KEY_JSON,
    METHOD_TUYA_LOCAL_KEY_SERVER,
    PROTOCOL_AUTO,
    PROTOCOLS,
    TUYA_REGIONS,
)

_LOGGER = logging.getLogger(__name__)


def _is_private_ip(ip_str: str | None) -> bool:
    """Check if the string is a valid private/local IPv4 or IPv6 address."""
    if not ip_str or not isinstance(ip_str, str):
        return False
    clean_ip = ip_str.strip()
    try:
        ip_obj = ipaddress.ip_address(clean_ip)
        return ip_obj.is_private or ip_obj.is_link_local
    except ValueError:
        return False


def _extract_device_ip(item: dict[str, Any]) -> str:
    """Extract local IP address from Tuya device data, strictly preferring private LAN IPs.

    Tuya cloud and export tools often report the router's public WAN IP in 'ip',
    while the actual internal LAN IP is stored in 'local_ip', 'localIp', 'lan_ip', etc.
    """
    # 1. First priority: explicit local / LAN IP keys
    local_keys = [
        "local_ip",
        "localIp",
        "lan_ip",
        "lanIp",
        "private_ip",
        "privateIp",
        "lan",
    ]
    for key in local_keys:
        val = item.get(key)
        if isinstance(val, str) and _is_private_ip(val):
            return val.strip()

    # 2. Second priority: generic 'ip', 'address', 'host' keys, ONLY IF private IP
    generic_keys = ["ip", "address", "host"]
    for key in generic_keys:
        val = item.get(key)
        if isinstance(val, str) and _is_private_ip(val):
            return val.strip()

    # 3. Third priority: non-empty local key field even if not standard IPv4 (e.g. .local hostname)
    for key in local_keys:
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    # 4. Filter out public WAN IPs from generic keys
    for key in generic_keys:
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            try:
                ip_obj = ipaddress.ip_address(val.strip())
                if not ip_obj.is_private and not ip_obj.is_link_local:
                    _LOGGER.info(
                        "Ignoring public WAN IP %s for device %s; waiting for local LAN IP",
                        val,
                        item.get("id") or item.get("gwId"),
                    )
                    continue
            except ValueError:
                # Hostname or mDNS name (e.g. 'tuya-lamp.local')
                return val.strip()

    return ""


def _validate_connection(data: dict[str, Any]) -> tuple[bool, str | None, dict[str, Any] | None]:
    """Test device connectivity and credentials in executor."""
    host = data.get(CONF_HOST, "").strip()
    device_id = data.get(CONF_DEVICE_ID, "").strip()
    local_key = data.get(CONF_LOCAL_KEY, "").strip()
    protocol_str = data.get(CONF_PROTOCOL_VERSION, PROTOCOL_AUTO)

    if not host or not device_id or not local_key:
        return False, None, None

    if host and not _is_private_ip(host):
        try:
            ip_obj = ipaddress.ip_address(host)
            if not ip_obj.is_private and not ip_obj.is_link_local:
                _LOGGER.warning(
                    "Attempting connection to public WAN IP %s for device %s. "
                    "Tuya local TCP connections (port 6668) typically require the device's local private LAN IP (e.g. 192.168.x.x)",
                    host,
                    device_id,
                )
        except ValueError:
            pass

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
        ip = _extract_device_ip(item)
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

    # Build candidates: user URL plus common Home Assistant Docker add-on hostnames
    candidates = [server_url]
    if "localhost" in server_url or "127.0.0.1" in server_url:
        candidates.extend(
            [
                server_url.replace("localhost", "127.0.0.1"),
                server_url.replace("localhost", "tuya-local-key").replace("127.0.0.1", "tuya-local-key"),
                server_url.replace("localhost", "local-tuya-local-key").replace("127.0.0.1", "local-tuya-local-key"),
                server_url.replace("localhost", "homeassistant").replace("127.0.0.1", "homeassistant"),
            ]
        )

    last_error = None
    for base in candidates:
        endpoints = [
            f"{base}/api/devices",
            f"{base}/devices",
            f"{base}/api/v1/devices",
            base,
        ]
        for url in endpoints:
            try:
                req = urllib.request.Request(
                    url,
                    headers={"Accept": "application/json", "User-Agent": "HomeAssistant-TuyaLamp"},
                )
                with urllib.request.urlopen(req, timeout=3) as response:
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
        return TuyaLampOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial mode selection step."""
        if user_input is not None:
            method = user_input.get(CONF_DISCOVERY_METHOD)
            if method == METHOD_TUYA_LOCAL_KEY_SERVER:
                return await self.async_step_tuya_local_key_server()
            if method == METHOD_TUYA_LOCAL_KEY_JSON:
                return await self.async_step_tuya_local_key_json()
            if method == METHOD_CLOUD:
                return await self.async_step_cloud()
            return await self.async_step_manual()

        methods = {
            METHOD_TUYA_LOCAL_KEY_SERVER: "Tuya Local Key Add-on (Automatisch über Server-URL)",
            METHOD_TUYA_LOCAL_KEY_JSON: "Raw JSON einfügen (aus Tuya Local Key kopiert)",
            METHOD_CLOUD: "Tuya IoT Developer Cloud (API Key & Secret)",
            METHOD_MANUAL: "Manuelle Direkteingabe (IP, ID, Local Key)",
        }

        schema = vol.Schema(
            {
                vol.Required(CONF_DISCOVERY_METHOD, default=METHOD_TUYA_LOCAL_KEY_SERVER): vol.In(methods),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )

    async def async_step_tuya_local_key_server(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step to fetch devices automatically from Tuya Local Key Add-on URL."""
        errors: dict[str, str] = {}

        if user_input is not None:
            server_url = user_input.get(CONF_SERVER_URL, "").strip()
            try:
                parsed_list = await self.hass.async_add_executor_job(
                    _fetch_from_tuya_local_key_server, server_url
                )

                lan_mapping = await self.hass.async_add_executor_job(_sync_scan_lan)
                self._discovered_devices = {}
                for dev in parsed_list:
                    dev_id = dev["id"]
                    lan_info = lan_mapping.get(dev_id, {})
                    lan_ip = lan_info.get("ip")
                    if lan_ip and _is_private_ip(lan_ip):
                        dev["ip"] = lan_ip
                    elif not _is_private_ip(dev.get("ip")) and lan_ip:
                        dev["ip"] = lan_ip

                    if dev["version"] == PROTOCOL_AUTO and lan_info.get("version"):
                        dev["version"] = lan_info["version"]

                    self._discovered_devices[dev_id] = dev

                if not self._discovered_devices:
                    errors["base"] = "no_devices_found"
                else:
                    return await self.async_step_select_device()

            except Exception as err:
                _LOGGER.warning("Could not connect to Tuya Local Key server %s: %s", server_url, err)
                errors["base"] = "cannot_connect_server"

        schema = vol.Schema(
            {
                vol.Required(CONF_SERVER_URL, default=DEFAULT_TUYA_LOCAL_KEY_URL): str,
            }
        )

        return self.async_show_form(
            step_id="tuya_local_key_server",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_tuya_local_key_json(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step to paste Raw JSON from Tuya Local Key Add-on."""
        errors: dict[str, str] = {}

        if user_input is not None:
            raw_json = user_input.get(CONF_JSON_DATA, "").strip()
            if not raw_json:
                errors["base"] = "no_data_provided"
            else:
                try:
                    parsed_list = _parse_devices_json(raw_json)
                    lan_mapping = await self.hass.async_add_executor_job(_sync_scan_lan)

                    self._discovered_devices = {}
                    for dev in parsed_list:
                        dev_id = dev["id"]
                        lan_info = lan_mapping.get(dev_id, {})
                        lan_ip = lan_info.get("ip")
                        if lan_ip and _is_private_ip(lan_ip):
                            dev["ip"] = lan_ip
                        elif not _is_private_ip(dev.get("ip")) and lan_ip:
                            dev["ip"] = lan_ip

                        if dev["version"] == PROTOCOL_AUTO and lan_info.get("version"):
                            dev["version"] = lan_info["version"]

                        self._discovered_devices[dev_id] = dev

                    if not self._discovered_devices:
                        errors["base"] = "no_devices_found"
                    else:
                        return await self.async_step_select_device()

                except Exception as err:
                    _LOGGER.error("Failed to parse JSON device data: %s", err)
                    errors["base"] = "invalid_json"

        schema = vol.Schema(
            {
                vol.Required(CONF_JSON_DATA): str,
            }
        )

        return self.async_show_form(
            step_id="tuya_local_key_json",
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
                    lan_ip = lan_info.get("ip")
                    extracted_ip = _extract_device_ip(dev)

                    if lan_ip and _is_private_ip(lan_ip):
                        ip = lan_ip
                    elif extracted_ip:
                        ip = extracted_ip
                    else:
                        ip = ""

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

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Display options navigation menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["network", "datapoints"],
        )

    async def async_step_network(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage network and connection parameters."""
        errors: dict[str, str] = {}
        data = self.config_entry.data
        opts = self.config_entry.options

        if user_input is not None:
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
                new_opts = dict(self.config_entry.options)
                new_opts.update(user_input)
                return self.async_create_entry(title="", data=new_opts)

            errors["base"] = "cannot_connect"

        current_host = opts.get(CONF_HOST, data.get(CONF_HOST, ""))
        current_key = opts.get(CONF_LOCAL_KEY, data.get(CONF_LOCAL_KEY, ""))
        current_protocol = opts.get(
            CONF_PROTOCOL_VERSION, data.get(CONF_PROTOCOL_VERSION, PROTOCOL_AUTO)
        )
        current_poll = opts.get(
            CONF_POLL_INTERVAL, data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        )

        network_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=current_host): str,
                vol.Required(CONF_LOCAL_KEY, default=current_key): str,
                vol.Optional(CONF_PROTOCOL_VERSION, default=current_protocol): vol.In(PROTOCOLS),
                vol.Optional(CONF_POLL_INTERVAL, default=current_poll): vol.All(
                    vol.Coerce(int), vol.Range(min=5, max=120)
                ),
            }
        )

        return self.async_show_form(
            step_id="network",
            data_schema=network_schema,
            errors=errors,
        )

    async def async_step_datapoints(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage granular Datapoint (DP) mapping and value ranges."""
        data = self.config_entry.data
        opts = self.config_entry.options

        if user_input is not None:
            new_opts = dict(self.config_entry.options)
            new_opts.update(user_input)
            return self.async_create_entry(title="", data=new_opts)

        # Inspect current live DPs from the coordinator if available
        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        live_dps = coordinator.data.get("dps", {}) if coordinator and coordinator.data else {}

        if live_dps:
            formatted_dps = " | ".join(
                f"DP {k}: {v}"
                for k, v in sorted(
                    live_dps.items(),
                    key=lambda x: int(x[0]) if x[0].isdigit() else str(x[0]),
                )
            )
        else:
            formatted_dps = "Keine Live-Daten verfügbar (Lampe eingeschaltet?)"

        current_power = opts.get(CONF_DP_POWER, data.get(CONF_DP_POWER, "20"))
        current_mode = opts.get(CONF_DP_MODE, data.get(CONF_DP_MODE, "21"))

        current_bright = opts.get(CONF_DP_BRIGHTNESS, data.get(CONF_DP_BRIGHTNESS, "22"))
        current_bright_min = opts.get(CONF_BRIGHTNESS_MIN, data.get(CONF_BRIGHTNESS_MIN, DEFAULT_BRIGHTNESS_MIN))
        current_bright_max = opts.get(CONF_BRIGHTNESS_MAX, data.get(CONF_BRIGHTNESS_MAX, DEFAULT_BRIGHTNESS_MAX))

        current_temp = opts.get(CONF_DP_COLOR_TEMP, data.get(CONF_DP_COLOR_TEMP, "23"))
        current_temp_min = opts.get(CONF_COLOR_TEMP_MIN, data.get(CONF_COLOR_TEMP_MIN, DEFAULT_COLOR_TEMP_MIN))
        current_temp_max = opts.get(CONF_COLOR_TEMP_MAX, data.get(CONF_COLOR_TEMP_MAX, DEFAULT_COLOR_TEMP_MAX))
        current_temp_rev = opts.get(CONF_COLOR_TEMP_REVERSE, data.get(CONF_COLOR_TEMP_REVERSE, False))

        current_min_k = opts.get(CONF_MIN_KELVIN, data.get(CONF_MIN_KELVIN, DEFAULT_MIN_KELVIN))
        current_max_k = opts.get(CONF_MAX_KELVIN, data.get(CONF_MAX_KELVIN, DEFAULT_MAX_KELVIN))

        current_color = opts.get(CONF_DP_COLOR, data.get(CONF_DP_COLOR, "24"))
        current_color_type = opts.get(CONF_COLOR_TYPE, data.get(CONF_COLOR_TYPE, COLOR_TYPE_HSV_HEX_12))

        dp_schema = vol.Schema(
            {
                vol.Required(CONF_DP_POWER, default=current_power): str,
                vol.Optional(CONF_DP_BRIGHTNESS, default=current_bright): str,
                vol.Optional(CONF_BRIGHTNESS_MIN, default=current_bright_min): vol.Coerce(int),
                vol.Optional(CONF_BRIGHTNESS_MAX, default=current_bright_max): vol.Coerce(int),
                vol.Optional(CONF_DP_COLOR_TEMP, default=current_temp): str,
                vol.Optional(CONF_COLOR_TEMP_MIN, default=current_temp_min): vol.Coerce(int),
                vol.Optional(CONF_COLOR_TEMP_MAX, default=current_temp_max): vol.Coerce(int),
                vol.Optional(CONF_COLOR_TEMP_REVERSE, default=current_temp_rev): bool,
                vol.Optional(CONF_MIN_KELVIN, default=current_min_k): vol.Coerce(int),
                vol.Optional(CONF_MAX_KELVIN, default=current_max_k): vol.Coerce(int),
                vol.Optional(CONF_DP_COLOR, default=current_color): str,
                vol.Optional(CONF_COLOR_TYPE, default=current_color_type): vol.In(COLOR_TYPES),
                vol.Optional(CONF_DP_MODE, default=current_mode): str,
            }
        )

        return self.async_show_form(
            step_id="datapoints",
            data_schema=dp_schema,
            description_placeholders={"detected_dps": formatted_dps},
        )
