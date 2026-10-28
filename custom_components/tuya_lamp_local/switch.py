"""Home Assistant Switch platform for Tuya Local Sockets and Switches."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, to_bool
from .coordinator import TuyaLampCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tuya Local Switch/Socket platform."""
    coordinator: TuyaLampCoordinator = hass.data[DOMAIN][entry.entry_id]

    ent_reg = er.async_get(hass)

    # If the device is classified as a light, do not create switch entities
    if not coordinator.is_switch:
        for dp_id in ["1", "2", "3", "4", "20"]:
            old_switch_uid = f"{coordinator.device_id}_switch_{dp_id}"
            old_entity_id = ent_reg.async_get_entity_id("switch", DOMAIN, old_switch_uid)
            if old_entity_id:
                _LOGGER.info(
                    "Device %s is recognized as a light (%s). Removing legacy switch entity %s",
                    coordinator.device_id,
                    coordinator.category or "light",
                    old_entity_id,
                )
                ent_reg.async_remove(old_entity_id)
        return

    known_unique_ids: set[str] = set()

    def _check_and_add_switches() -> None:
        """Inspect coordinator data and add newly discovered switch/socket entities."""
        new_entities: list[SwitchEntity] = []

        # If switch_dps is empty, fallback to single socket on dp_power
        dps_to_setup = coordinator.switch_dps or {coordinator.dp_power: "Steckdose"}
        is_multi = len(dps_to_setup) > 1

        for dp_id, label in dps_to_setup.items():
            uid = f"{coordinator.device_id}_switch_{dp_id}"
            if uid not in known_unique_ids:
                known_unique_ids.add(uid)
                new_entities.append(
                    TuyaLocalSwitch(
                        coordinator,
                        entry,
                        dp_id=dp_id,
                        label=label if is_multi else None,
                    )
                )

        if new_entities:
            async_add_entities(new_entities)

    _check_and_add_switches()
    entry.async_on_unload(coordinator.async_add_listener(_check_and_add_switches))


class TuyaLocalSwitch(CoordinatorEntity[TuyaLampCoordinator], SwitchEntity):
    """Representation of a Tuya Local Socket / Switch."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TuyaLampCoordinator,
        entry: ConfigEntry,
        dp_id: str,
        label: str | None = None,
    ) -> None:
        """Initialize the socket / switch entity."""
        super().__init__(coordinator)
        self.entry = entry
        self.dp_id = dp_id
        self._label = label
        self._attr_unique_id = f"{coordinator.device_id}_switch_{dp_id}"

        if coordinator.is_socket:
            self._attr_device_class = SwitchDeviceClass.OUTLET
            self._attr_icon = "mdi:power-socket-de"
            model_type = "Smart Socket / Plug"
        else:
            self._attr_device_class = SwitchDeviceClass.SWITCH
            self._attr_icon = "mdi:toggle-switch"
            model_type = "Smart Switch"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name=entry.title or f"Tuya {model_type} {coordinator.device_id[-6:]}",
            manufacturer="Tuya",
            model=f"Wi-Fi {model_type} (Protocol {coordinator.protocol_str})",
        )

    @property
    def name(self) -> str | None:
        """Return socket name (e.g. 'Steckdose 1' or None for single socket)."""
        return self._label

    @property
    def is_on(self) -> bool:
        """Return True if the socket/switch is on."""
        dps = self.coordinator.data.get("dps", {}) if self.coordinator.data else {}
        val = dps.get(self.dp_id, dps.get(int(self.dp_id) if str(self.dp_id).isdigit() else None, False))
        return to_bool(val, default=False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the socket/switch on."""
        await self.coordinator.async_send_dps({self.dp_id: True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the socket/switch off."""
        await self.coordinator.async_send_dps({self.dp_id: False})
