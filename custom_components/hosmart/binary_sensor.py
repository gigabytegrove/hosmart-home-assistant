"""Binary sensors for Hosmart receivers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HosmartCoordinator
from .entity import HosmartEntity


@dataclass(frozen=True, kw_only=True)
class HosmartBinaryDescription(BinarySensorEntityDescription):
    """Describe a Hosmart binary sensor."""

    value_fn: Callable[[HosmartCoordinator], bool | None]


BINARY_SENSORS = (
    HosmartBinaryDescription(
        key="power",
        name="Power",
        icon="mdi:power",
        value_fn=lambda c: _bool(c.receiver.get("Power")),
    ),
    HosmartBinaryDescription(
        key="internal_charge",
        name="Internal charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda c: _bool(c.receiver.get("InternalCharge")),
    ),
    HosmartBinaryDescription(
        key="zone_all_armed",
        name="All zones armed",
        icon="mdi:shield-check-outline",
        value_fn=lambda c: _bool(c.receiver.get("ZoneAlarmingAll")),
    ),
    HosmartBinaryDescription(
        key="zone_zero_armed",
        name="Zone zero armed",
        icon="mdi:shield-outline",
        value_fn=lambda c: _bool(c.receiver.get("ZoneAlarmingZero")),
    ),
    HosmartBinaryDescription(
        key="zone_1_armed",
        name="Zone 1 armed",
        icon="mdi:shield-outline",
        value_fn=lambda c: _bool(c.receiver.get("ZoneAlarming1")),
    ),
    HosmartBinaryDescription(
        key="zone_2_armed",
        name="Zone 2 armed",
        icon="mdi:shield-outline",
        value_fn=lambda c: _bool(c.receiver.get("ZoneAlarming2")),
    ),
    HosmartBinaryDescription(
        key="zone_3_armed",
        name="Zone 3 armed",
        icon="mdi:shield-outline",
        value_fn=lambda c: _bool(c.receiver.get("ZoneAlarming3")),
    ),
    HosmartBinaryDescription(
        key="zone_4_armed",
        name="Zone 4 armed",
        icon="mdi:shield-outline",
        value_fn=lambda c: _bool(c.receiver.get("ZoneAlarming4")),
    ),
)


def _bool(value) -> bool | None:
    if value is None:
        return None
    return bool(value)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hosmart binary sensors."""
    coordinator: HosmartCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        HosmartBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
    )


class HosmartBinarySensor(HosmartEntity, BinarySensorEntity):
    """A Hosmart binary sensor."""

    entity_description: HosmartBinaryDescription

    def __init__(
        self,
        coordinator: HosmartCoordinator,
        description: HosmartBinaryDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor state."""
        return self.entity_description.value_fn(self.coordinator)
