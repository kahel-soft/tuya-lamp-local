"""Config flow and Options flow for Tuya Local Lamp integration."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import ipaddress
import json
import logging
import os
import re
import socket
from typing import Any
import urllib.parse
import urllib.request

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.storage import Store
import tinytuya
import voluptuous as vol

from .const import (
    CATEGORY_LIGHTS,
    CATEGORY_SOCKETS,
    COLOR_TYPES,
    COLOR_TYPE_HSV_HEX_12,
    COLOR_TYPE_RGB_HEX_6,
    CONF_API_DEVICE_ID,
    CONF_API_KEY,
    CONF_API_REGION,
    CONF_API_SECRET,
    CONF_BRIGHTNESS_MAX,
    CONF_BRIGHTNESS_MIN,
    CONF_CATEGORY,
    CONF_COLOR_TEMP_MAX,
    CONF_COLOR_TEMP_MIN,
    CONF_COLOR_TEMP_REVERSE,
    CONF_COLOR_TYPE,
    CONF_DEVICE_ID,
    CONF_DEVICE_TYPE,
    CONF_DISCOVERY_METHOD,
    CONF_DP_BRIGHTNESS,
    CONF_DP_COLOR,
    CONF_DP_COLOR_TEMP,
    CONF_DP_MODE,
    CONF_DP_POWER,
    CONF_DP_AUX_POWER,
    CONF_DP_AUX_BRIGHTNESS,
    CONF_DP_AUX_COLOR,
    CONF_DP_AUX_COLOR_TEMP,
    CONF_DP_AUX_MODE,
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
    CONF_SELECTED_DEVICES,
    CONF_SERVER_URL,
    DEFAULT_BRIGHTNESS_MAX,
    DEFAULT_BRIGHTNESS_MIN,
    DEFAULT_COLOR_TEMP_MAX,
    DEFAULT_COLOR_TEMP_MIN,
    DEFAULT_MAX_KELVIN,
    DEFAULT_MIN_KELVIN,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_TUYA_LOCAL_KEY_URL,
    DEVICE_TYPE_AUTO,
    DEVICE_TYPES,
    DOMAIN,
    METHOD_CACHED,
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
    clean_ip = ip_str.strip().split(":")[0].strip()
    try:
        ip_obj = ipaddress.ip_address(clean_ip)
        return ip_obj.is_private or ip_obj.is_link_local
    except ValueError:
        return False


def _find_private_ips_in_obj(obj: Any) -> list[str]:
    """Recursively search any dictionary, list, or string for private IPv4 addresses."""
    results: list[str] = []
    if isinstance(obj, dict):
        priority_keys = [
            k for k in obj.keys()
            if any(term in str(k).lower() for term in ["local", "lan", "private"])
        ]
        other_keys = [k for k in obj.keys() if k not in priority_keys]
        for k in priority_keys + other_keys:
            results.extend(_find_private_ips_in_obj(obj[k]))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(_find_private_ips_in_obj(item))
    elif isinstance(obj, str):
        for match in re.findall(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", obj):
            clean = match.strip()
            if _is_private_ip(clean) and clean not in results:
                results.append(clean)
    return results


def _extract_device_ip(item: dict[str, Any]) -> str:
    """Extract local IP address from Tuya device data, strictly preferring private LAN IPs.

    Tuya cloud and export tools often report the router's public WAN IP in 'ip',
    while the actual internal LAN IP is stored in 'local_ip', 'localIp', 'lan_ip', etc.
    """
    # 1. First priority: explicit local / LAN IP keys
    local_keys = [
        "local_ip",
        "localIp",
        "localIP",
        "lan_ip",
        "lanIp",
        "lanIP",
        "private_ip",
        "privateIp",
        "ip_address",
        "ipAddress",
        "device_ip",
        "deviceIp",
        "lan",
    ]
    for key in local_keys:
        val = item.get(key)
        if isinstance(val, str) and _is_private_ip(val):
            return val.strip().split(":")[0].strip()

    # 2. Second priority: generic 'ip', 'address', 'host' keys, ONLY IF private IP
    generic_keys = ["ip", "address", "host"]
    for key in generic_keys:
        val = item.get(key)
        if isinstance(val, str) and _is_private_ip(val):
            return val.strip().split(":")[0].strip()

    # 3. Third priority: recursive search in entire dictionary
    found = _find_private_ips_in_obj(item)
    if found:
        return found[0]

    # 4. Filter out public WAN IPs from generic keys
    for key in local_keys + generic_keys:
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            clean = val.strip().split(":")[0].strip()
            try:
                ip_obj = ipaddress.ip_address(clean)
                if not ip_obj.is_private and not ip_obj.is_link_local:
                    _LOGGER.info(
                        "Ignoring public WAN IP %s for device %s; searching for local LAN IP",
                        val,
                        item.get("id") or item.get("gwId"),
                    )
                    continue
            except ValueError:
                # Hostname or mDNS name (e.g. 'tuya-lamp.local')
                return clean

    return ""


def _get_single_local_subnet() -> str | None:
    """Get the primary local LAN subnet prefix (e.g. '192.168.178')."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        parts = local_ip.split(".")
        if len(parts) == 4 and _is_private_ip(local_ip):
            if not local_ip.startswith("172.") and not local_ip.startswith("127."):
                return ".".join(parts[:3])
    except Exception:
        pass

    # Check Linux/HOAS default route
    if os.path.exists("/proc/net/route"):
        try:
            with open("/proc/net/route", "r") as f:
                for line in f.readlines()[1:]:
                    fields = line.strip().split()
                    if len(fields) >= 3 and fields[1] == "00000000":
                        gw_hex = fields[2]
                        gw_ip = socket.inet_ntoa(bytes.fromhex(gw_hex)[::-1])
                        if _is_private_ip(gw_ip) and not gw_ip.startswith("172."):
                            return ".".join(gw_ip.split(".")[:3])
        except Exception:
            pass

    return "192.168.178"


async def _async_scan_subnet_tuya_ports(prefix: str, timeout: float = 0.25) -> list[str]:
    """Scan local /24 subnet for devices with open TCP port 6668 (Tuya port)."""
    async def _check_ip(ip: str) -> str | None:
        try:
            conn = asyncio.open_connection(ip, 6668)
            _, writer = await asyncio.wait_for(conn, timeout=timeout)
            writer.close()
            await writer.wait_closed()
            return ip
        except Exception:
            return None

    tasks = [_check_ip(f"{prefix}.{i}") for i in range(1, 255)]
    results = await asyncio.gather(*tasks)
    return [ip for ip in results if ip]


async def _async_resolve_devices_ips(
    hass,
    devices: list[dict[str, Any]],
    lan_mapping: dict[str, dict[str, Any]],
    user_override_host: str = "",
) -> None:
    """Resolve local LAN IPs for parsed devices quickly and safely."""
    # 1. User override if provided
    if user_override_host and _is_private_ip(user_override_host):
        for dev in devices:
            if not dev.get("ip"):
                dev["ip"] = user_override_host

    # 2. Map from UDP broadcast scan
    for dev in devices:
        dev_id = dev["id"]
        if dev_id in lan_mapping:
            lan_ip = lan_mapping[dev_id].get("ip")
            if lan_ip and _is_private_ip(lan_ip):
                dev["ip"] = lan_ip

    # 3. Check if any device still needs an IP
    needing_ip = [d for d in devices if not d.get("ip") or not _is_private_ip(d.get("ip"))]
    if not needing_ip:
        return

    # 4. Scan subnet ONCE on port 6668 (takes ~0.25s)
    prefix = _get_single_local_subnet()
    if not prefix:
        return

    candidates = await _async_scan_subnet_tuya_ports(prefix=prefix, timeout=0.25)
    if not candidates:
        return

    # If only 1 device needs an IP and only 1 candidate was found:
    if len(needing_ip) == 1 and len(candidates) == 1:
        needing_ip[0]["ip"] = candidates[0]
        return

    # Multiple candidates: probe quickly in executor with 0.3s timeout
    def _run_matches() -> dict[str, str]:
        results: dict[str, str] = {}
        for dev in needing_ip:
            dev_id = dev["id"]
            key = dev["key"]
            for cand_ip in candidates:
                try:
                    d = tinytuya.BulbDevice(dev_id=dev_id, address=cand_ip, local_key=key, version=3.3)
                    d.set_socketTimeout(0.3)
                    st = d.status()
                    if isinstance(st, dict) and "dps" in st:
                        results[dev_id] = cand_ip
                        break
                except Exception:
                    continue
        return results

    matches = await hass.async_add_executor_job(_run_matches)
    for dev in needing_ip:
        if dev["id"] in matches:
            dev["ip"] = matches[dev["id"]]
        elif len(candidates) == 1:
            dev["ip"] = candidates[0]


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

        category = str(item.get("category", "")).lower().strip()
        default_name = (
            f"Tuya Steckdose {str(dev_id)[-6:]}"
            if category in CATEGORY_SOCKETS
            else f"Tuya Lamp {str(dev_id)[-6:]}"
        )
        name = (
            item.get("name")
            or item.get("product_name")
            or item.get("productName")
            or default_name
        )
        ip = _extract_device_ip(item)
        version = str(item.get("version") or item.get("protocol_version") or PROTOCOL_AUTO)

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

    # Fast socket pre-check (1.0s timeout) to prevent 30s+ browser freeze on closed ports
    parsed_url = urllib.parse.urlparse(server_url)
    host = parsed_url.hostname or "localhost"
    port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=1.0):
            pass
    except Exception as err:
        raise Exception(f"Port {port} auf {host} nicht erreichbar ({err}). Läuft das Add-on und ist der Port freigegeben?")

    # Port is open! Check standard endpoints
    endpoints = [
        f"{server_url}/api/devices",
        f"{server_url}/devices",
        server_url,
    ]
    last_error = None
    for url in endpoints:
        try:
            req = urllib.request.Request(
                url,
                headers={"Accept": "application/json", "User-Agent": "HomeAssistant-TuyaLamp"},
            )
            with urllib.request.urlopen(req, timeout=1.5) as response:
                content = response.read().decode("utf-8")
                parsed = _parse_devices_json(content)
                if parsed:
                    return parsed
        except Exception as err:
            last_error = err
            continue

    raise Exception(f"Konnte keine Gerätedaten von {server_url} abrufen: {last_error}")


STORAGE_KEY = f"{DOMAIN}_device_cache"
STORAGE_VERSION = 1


async def _async_get_cached_devices(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    """Retrieve cached Tuya devices from hass.data or persistent storage."""
    hass.data.setdefault(DOMAIN, {})
    if "cached_devices" in hass.data[DOMAIN]:
        return dict(hass.data[DOMAIN]["cached_devices"])

    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    stored = await store.async_load()
    if isinstance(stored, dict):
        hass.data[DOMAIN]["cached_devices"] = stored
        return dict(stored)

    hass.data[DOMAIN]["cached_devices"] = {}
    return {}


async def _async_save_cached_devices(hass: HomeAssistant, devices: dict[str, dict[str, Any]]) -> None:
    """Save discovered Tuya devices into memory and persistent storage."""
    hass.data.setdefault(DOMAIN, {})
    cached = hass.data[DOMAIN].setdefault("cached_devices", {})
    cached.update(devices)
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    await store.async_save(cached)


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
        cached_devices = await _async_get_cached_devices(self.hass)
        current_ids = self._async_current_ids()

        unconfigured_cached = {
            d_id: info
            for d_id, info in cached_devices.items()
            if d_id not in current_ids
        }

        if user_input is not None:
            method = user_input.get(CONF_DISCOVERY_METHOD)
            if method == METHOD_CACHED:
                self._discovered_devices = unconfigured_cached
                return await self.async_step_select_device()
            if method == METHOD_TUYA_LOCAL_KEY_SERVER:
                return await self.async_step_tuya_local_key_server()
            if method == METHOD_TUYA_LOCAL_KEY_JSON:
                return await self.async_step_tuya_local_key_json()
            if method == METHOD_CLOUD:
                return await self.async_step_cloud()
            return await self.async_step_manual()

        methods = {}
        if unconfigured_cached:
            methods[METHOD_CACHED] = f"Gefundene Geräte hinzufügen ({len(unconfigured_cached)} verfügbar)"
        methods[METHOD_TUYA_LOCAL_KEY_SERVER] = "Tuya Local Key Add-on (Automatisch über Server-URL)"
        methods[METHOD_TUYA_LOCAL_KEY_JSON] = "Raw JSON einfügen (aus Tuya Local Key kopiert)"
        methods[METHOD_CLOUD] = "Tuya IoT Developer Cloud (API Key & Secret)"
        methods[METHOD_MANUAL] = "Manuelle Direkteingabe (IP, ID, Local Key)"

        default_method = METHOD_CACHED if unconfigured_cached else METHOD_TUYA_LOCAL_KEY_SERVER

        schema = vol.Schema(
            {
                vol.Required(CONF_DISCOVERY_METHOD, default=default_method): vol.In(methods),
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
                await _async_resolve_devices_ips(self.hass, parsed_list, lan_mapping)

                self._discovered_devices = {}
                for dev in parsed_list:
                    dev_id = dev["id"]
                    lan_info = lan_mapping.get(dev_id, {})
                    if dev["version"] == PROTOCOL_AUTO and lan_info.get("version"):
                        dev["version"] = lan_info["version"]
                    self._discovered_devices[dev_id] = dev

                if not self._discovered_devices:
                    errors["base"] = "no_devices_found"
                else:
                    await _async_save_cached_devices(self.hass, self._discovered_devices)
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
            user_host = user_input.get(CONF_HOST, "").strip()

            if not raw_json:
                errors["base"] = "no_data_provided"
            else:
                try:
                    parsed_list = _parse_devices_json(raw_json)
                    lan_mapping = await self.hass.async_add_executor_job(_sync_scan_lan)
                    await _async_resolve_devices_ips(
                        self.hass, parsed_list, lan_mapping, user_override_host=user_host
                    )

                    self._discovered_devices = {}
                    for dev in parsed_list:
                        dev_id = dev["id"]
                        lan_info = lan_mapping.get(dev_id, {})
                        if dev["version"] == PROTOCOL_AUTO and lan_info.get("version"):
                            dev["version"] = lan_info["version"]
                        self._discovered_devices[dev_id] = dev

                    if not self._discovered_devices:
                        errors["base"] = "no_devices_found"
                    else:
                        await _async_save_cached_devices(self.hass, self._discovered_devices)
                        return await self.async_step_select_device()

                except Exception as err:
                    _LOGGER.error("Failed to parse JSON device data: %s", err)
                    errors["base"] = "invalid_json"

        schema = vol.Schema(
            {
                vol.Required(CONF_JSON_DATA): str,
                vol.Optional(CONF_HOST, default=""): str,
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

                parsed_list: list[dict[str, Any]] = []
                for dev in cloud_devices:
                    dev_id = str(dev.get("id") or dev.get("gwId") or "")
                    local_key = str(dev.get("local_key") or dev.get("key") or "")
                    if not dev_id or not local_key:
                        continue
                    category = str(dev.get("category", "")).lower().strip()
                    default_name = (
                        f"Tuya Steckdose {dev_id[-6:]}"
                        if category in CATEGORY_SOCKETS
                        else f"Tuya Lamp {dev_id[-6:]}"
                    )
                    name = dev.get("name") or default_name
                    ip = _extract_device_ip(dev)
                    vers = dev.get("version", PROTOCOL_AUTO)
                    parsed_list.append(
                        {
                            "name": name,
                            "id": dev_id,
                            "key": local_key,
                            "ip": ip,
                            "version": vers,
                            "category": category,
                        }
                    )

                await _async_resolve_devices_ips(self.hass, parsed_list, lan_mapping)

                self._discovered_devices = {}
                for dev in parsed_list:
                    dev_id = dev["id"]
                    lan_info = lan_mapping.get(dev_id, {})
                    if dev["version"] == PROTOCOL_AUTO and lan_info.get("version"):
                        dev["version"] = lan_info["version"]
                    self._discovered_devices[dev_id] = dev

                if not self._discovered_devices:
                    errors["base"] = "no_devices_found"
                else:
                    await _async_save_cached_devices(self.hass, self._discovered_devices)
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
        """Step to present a list of discovered devices for the user to choose (with multi-select)."""
        current_ids = self._async_current_ids()

        # Filter out devices already configured in Home Assistant
        available_devices = {
            d_id: info
            for d_id, info in self._discovered_devices.items()
            if d_id not in current_ids
        }

        if not available_devices:
            return self.async_abort(reason="all_devices_configured")

        errors: dict[str, str] = {}

        if user_input is not None:
            selected_raw = user_input.get(CONF_SELECTED_DEVICES) or user_input.get(CONF_SELECTED_DEVICE)
            if isinstance(selected_raw, str):
                selected_ids = [selected_raw]
            elif isinstance(selected_raw, list):
                selected_ids = selected_raw
            else:
                selected_ids = []

            if not selected_ids:
                errors["base"] = "no_device_selected"
            elif len(selected_ids) == 1:
                # Single device selected: allow confirmation & testing
                self._selected_device = available_devices.get(selected_ids[0])
                return await self.async_step_confirm_device()
            else:
                # Multiple devices selected: create all at once!
                return await self._async_create_multiple_devices(selected_ids, available_devices)

        choices = {}
        for d_id, info in available_devices.items():
            name = info.get("name", "Tuya Device")
            ip = info.get("ip") or "IP suchen"
            cat = str(info.get("category", "")).lower().strip()
            if cat in CATEGORY_SOCKETS:
                type_badge = " [🔌 Steckdose]"
            elif cat in CATEGORY_LIGHTS:
                type_badge = " [💡 Lampe]"
            elif any(w in name.lower() for w in ["steckdose", "socket", "plug", "outlet", "stecker"]):
                type_badge = " [🔌 Steckdose]"
            elif any(w in name.lower() for w in ["lampe", "lamp", "light", "leuchte", "birne", "bulb"]):
                type_badge = " [💡 Lampe]"
            elif cat:
                type_badge = f" [{cat}]"
            else:
                type_badge = ""
            choices[d_id] = f"{name} ({ip} | ID: {d_id[-6:]}){type_badge}"

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SELECTED_DEVICES,
                    default=list(choices.keys())
                ): cv.multi_select(choices),
            }
        )

        return self.async_show_form(
            step_id="select_device",
            data_schema=schema,
            errors=errors,
            description_placeholders={"count": str(len(choices))},
        )

    async def _async_create_multiple_devices(
        self, selected_ids: list[str], available_devices: dict[str, dict[str, Any]]
    ) -> FlowResult:
        """Create multiple config entries at once for all selected devices."""
        first_id = selected_ids[0]
        first_dev = available_devices[first_id]

        # Trigger background creation flows for all subsequent devices
        for d_id in selected_ids[1:]:
            dev = available_devices.get(d_id)
            if not dev:
                continue
            custom_name = dev.get("name", "").strip()
            dev_host = dev.get("ip", "").strip()
            dev_data = {
                CONF_NAME: custom_name,
                CONF_HOST: dev_host,
                CONF_DEVICE_ID: d_id,
                CONF_LOCAL_KEY: dev.get("key", "").strip(),
                CONF_PROTOCOL_VERSION: dev.get("version", PROTOCOL_AUTO),
                CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
                CONF_CATEGORY: dev.get("category", ""),
            }
            self.hass.async_create_task(
                self.hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_IMPORT},
                    data=dev_data,
                )
            )

        # Create entry for the first device in this flow
        first_name = first_dev.get("name", "").strip()
        first_host = first_dev.get("ip", "").strip()
        first_cat = first_dev.get("category", "")
        await self.async_set_unique_id(first_id)
        self._abort_if_unique_id_configured()

        first_data = {
            CONF_NAME: first_name,
            CONF_HOST: first_host,
            CONF_DEVICE_ID: first_id,
            CONF_LOCAL_KEY: first_dev.get("key", "").strip(),
            CONF_PROTOCOL_VERSION: first_dev.get("version", PROTOCOL_AUTO),
            CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
            CONF_CATEGORY: first_cat,
        }
        fallback_prefix = "Tuya Steckdose" if first_cat in CATEGORY_SOCKETS else "Tuya Lamp"
        title = first_name if first_name else f"{fallback_prefix} ({first_host})"
        return self.async_create_entry(title=title, data=first_data)

    async def async_step_import(self, import_data: dict[str, Any]) -> FlowResult:
        """Handle programmatic creation of multiple selected devices."""
        device_id = import_data[CONF_DEVICE_ID]
        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured()

        custom_name = import_data.get(CONF_NAME, "").strip()
        dev_host = import_data.get(CONF_HOST, "").strip()
        cat = import_data.get(CONF_CATEGORY, "")
        fallback_prefix = "Tuya Steckdose" if cat in CATEGORY_SOCKETS else "Tuya Lamp"
        title = custom_name if custom_name else f"{fallback_prefix} ({dev_host})"
        return self.async_create_entry(title=title, data=import_data)

    async def async_step_confirm_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm parameters and test connection before saving."""
        errors: dict[str, str] = {}
        dev = self._selected_device or {}

        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID].strip()
            host = user_input[CONF_HOST].strip()
            user_input[CONF_HOST] = host
            user_input[CONF_DEVICE_ID] = device_id
            user_input[CONF_LOCAL_KEY] = user_input[CONF_LOCAL_KEY].strip()
            user_input[CONF_CATEGORY] = dev.get("category", "")

            if not host:
                errors[CONF_HOST] = "host_required"
            else:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured(updates=user_input)

                # Test connection
                success, detected_version, _ = await self.hass.async_add_executor_job(
                    _validate_connection, user_input
                )

                if success:
                    if detected_version:
                        user_input[CONF_PROTOCOL_VERSION] = detected_version

                    custom_name = user_input.get(CONF_NAME, "").strip()
                    cat = dev.get("category", "")
                    fallback_prefix = "Tuya Steckdose" if cat in CATEGORY_SOCKETS else "Tuya Lamp"
                    title = custom_name if custom_name else f"{fallback_prefix} ({user_input[CONF_HOST]})"
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
            self._abort_if_unique_id_configured(updates=user_input)

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
            menu_options=["network", "datapoints", "rescan"],
        )

    async def async_step_rescan(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Rescan device live data and detect all light sources / DPs."""
        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if not coordinator:
            return self.async_abort(reason="cannot_connect")

        if user_input is not None:
            new_opts = dict(self.config_entry.options)
            if not coordinator.is_switch and coordinator.has_aux_light:
                new_opts[CONF_DP_AUX_POWER] = coordinator.dp_aux_power
                if coordinator.dp_aux_brightness:
                    new_opts[CONF_DP_AUX_BRIGHTNESS] = coordinator.dp_aux_brightness
                if coordinator.dp_aux_color:
                    new_opts[CONF_DP_AUX_COLOR] = coordinator.dp_aux_color
                if coordinator.dp_aux_color_temp:
                    new_opts[CONF_DP_AUX_COLOR_TEMP] = coordinator.dp_aux_color_temp
                if coordinator.dp_aux_mode:
                    new_opts[CONF_DP_AUX_MODE] = coordinator.dp_aux_mode
                if coordinator.dp_master_power:
                    new_opts[CONF_DP_POWER] = coordinator.dp_power
            return self.async_create_entry(title="", data=new_opts)

        try:
            status_data = await self.hass.async_add_executor_job(coordinator._sync_fetch_status)
            dps = status_data.get("dps", {})
            coordinator._detect_datapoint_layout(dps)
            coordinator.async_set_updated_data(status_data)
        except Exception as err:
            _LOGGER.error("Rescan failed for device %s: %s", coordinator.device_id, err)
            return self.async_abort(reason="cannot_connect")

        if coordinator.is_switch:
            dev_type_str = "Steckdose / Smart Plug" if coordinator.is_socket else "Schalter / Switch"
            sources = [f"{label} (DP {dp})" for dp, label in coordinator.switch_dps.items()]
        else:
            dev_type_str = "Lampe / Lighting"
            sources = ["Hauptlicht (Main Light)"]
            if coordinator.has_aux_light:
                sources.append("Sockel / Base (Zusatzlicht - DP 102/103/105)")

        dps_summary = " | ".join(
            f"DP {k}: {v}"
            for k, v in sorted(
                dps.items(),
                key=lambda x: int(x[0]) if str(x[0]).isdigit() else str(x[0]),
            )
        )

        return self.async_show_form(
            step_id="rescan",
            data_schema=vol.Schema({}),
            description_placeholders={
                "device_type": dev_type_str,
                "light_sources": ", ".join(sources),
                "dps_summary": dps_summary,
            },
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

        current_power = opts.get(
            CONF_DP_POWER,
            data.get(CONF_DP_POWER, coordinator.dp_power if coordinator else "20"),
        )
        current_mode = opts.get(
            CONF_DP_MODE,
            data.get(CONF_DP_MODE, coordinator.dp_mode if coordinator else "21"),
        )

        current_bright = opts.get(
            CONF_DP_BRIGHTNESS,
            data.get(CONF_DP_BRIGHTNESS, coordinator.dp_brightness if coordinator else "22"),
        )
        current_bright_min = opts.get(CONF_BRIGHTNESS_MIN, data.get(CONF_BRIGHTNESS_MIN, DEFAULT_BRIGHTNESS_MIN))
        current_bright_max = opts.get(CONF_BRIGHTNESS_MAX, data.get(CONF_BRIGHTNESS_MAX, DEFAULT_BRIGHTNESS_MAX))

        current_temp = opts.get(
            CONF_DP_COLOR_TEMP,
            data.get(CONF_DP_COLOR_TEMP, coordinator.dp_color_temp if coordinator else "23"),
        )
        current_temp_min = opts.get(CONF_COLOR_TEMP_MIN, data.get(CONF_COLOR_TEMP_MIN, DEFAULT_COLOR_TEMP_MIN))
        current_temp_max = opts.get(CONF_COLOR_TEMP_MAX, data.get(CONF_COLOR_TEMP_MAX, DEFAULT_COLOR_TEMP_MAX))
        current_temp_rev = opts.get(CONF_COLOR_TEMP_REVERSE, data.get(CONF_COLOR_TEMP_REVERSE, False))

        current_min_k = opts.get(CONF_MIN_KELVIN, data.get(CONF_MIN_KELVIN, DEFAULT_MIN_KELVIN))
        current_max_k = opts.get(CONF_MAX_KELVIN, data.get(CONF_MAX_KELVIN, DEFAULT_MAX_KELVIN))

        current_color = opts.get(
            CONF_DP_COLOR,
            data.get(CONF_DP_COLOR, coordinator.dp_color if coordinator else "24"),
        )
        current_color_type = opts.get(CONF_COLOR_TYPE, data.get(CONF_COLOR_TYPE, COLOR_TYPE_HSV_HEX_12))

        current_aux_power = opts.get(
            CONF_DP_AUX_POWER,
            data.get(
                CONF_DP_AUX_POWER,
                coordinator.dp_aux_power if coordinator and coordinator.has_aux_light else ("102" if "102" in live_dps else ""),
            ),
        )
        current_aux_bright = opts.get(
            CONF_DP_AUX_BRIGHTNESS,
            data.get(
                CONF_DP_AUX_BRIGHTNESS,
                coordinator.dp_aux_brightness if coordinator and coordinator.has_aux_light else ("103" if "103" in live_dps else ""),
            ),
        )
        current_aux_color = opts.get(
            CONF_DP_AUX_COLOR,
            data.get(
                CONF_DP_AUX_COLOR,
                coordinator.dp_aux_color if coordinator and coordinator.has_aux_light else ("105" if "105" in live_dps else ""),
            ),
        )
        current_aux_temp = opts.get(
            CONF_DP_AUX_COLOR_TEMP,
            data.get(
                CONF_DP_AUX_COLOR_TEMP,
                coordinator.dp_aux_color_temp if coordinator and coordinator.has_aux_light else ("104" if "104" in live_dps else ""),
            ),
        )
        current_aux_mode = opts.get(
            CONF_DP_AUX_MODE,
            data.get(
                CONF_DP_AUX_MODE,
                coordinator.dp_aux_mode if coordinator and coordinator.has_aux_light else ("106" if "106" in live_dps else ""),
            ),
        )

        current_dev_type = opts.get(CONF_DEVICE_TYPE, data.get(CONF_DEVICE_TYPE, DEVICE_TYPE_AUTO))

        dp_schema = vol.Schema(
            {
                vol.Optional(CONF_DEVICE_TYPE, default=current_dev_type): vol.In(DEVICE_TYPES),
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
                vol.Optional(CONF_DP_AUX_POWER, default=current_aux_power): str,
                vol.Optional(CONF_DP_AUX_BRIGHTNESS, default=current_aux_bright): str,
                vol.Optional(CONF_DP_AUX_COLOR, default=current_aux_color): str,
                vol.Optional(CONF_DP_AUX_COLOR_TEMP, default=current_aux_temp): str,
                vol.Optional(CONF_DP_AUX_MODE, default=current_aux_mode): str,
            }
        )

        return self.async_show_form(
            step_id="datapoints",
            data_schema=dp_schema,
            description_placeholders={"detected_dps": formatted_dps},
        )
