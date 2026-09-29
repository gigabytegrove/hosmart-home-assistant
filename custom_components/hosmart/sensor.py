"""Sensors for Ho-Smart receivers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HosmartCoordinator
from .entity import HosmartEntity


@dataclass(frozen=True, kw_only=True)
class HosmartSensorDescription(SensorEntityDescription):
    """Describe a Ho-Smart sensor."""

    value_fn: Callable[[HosmartCoordinator], Any]
    requires_local: bool = False


def _last_activity_value(coordinator: HosmartCoordinator, key: str):
    if coordinator.last_activity is None:
        return None
    return coordinator.last_activity.get(key)


def _udp_time_value(coordinator: HosmartCoordinator) -> str:
    return (
        coordinator.last_udp_time.isoformat()
        if coordinator.last_udp_time is not None
        else "Never observed"
    )


SENSORS = (
    HosmartSensorDescription(
        key="event",
        name="Event",
        icon="mdi:motion-sensor",
        requires_local=True,
        value_fn=lambda c: c.receiver.get("Event"),
    ),
    HosmartSensorDescription(
        key="channel",
        name="Channel",
        icon="mdi:numeric",
        requires_local=True,
        value_fn=lambda c: c.receiver.get("Channel"),
    ),
    HosmartSensorDescription(
        key="channel_name",
        name="Channel name",
        icon="mdi:label-outline",
        requires_local=True,
        value_fn=lambda c: c.receiver.get("ChannelName"),
    ),
    HosmartSensorDescription(
        key="last_activity_event",
        name="Last activity event",
        icon="mdi:motion-sensor",
        value_fn=lambda c: _last_activity_value(c, "event"),
    ),
    HosmartSensorDescription(
        key="last_activity_channel",
        name="Last activity channel",
        icon="mdi:numeric",
        value_fn=lambda c: _last_activity_value(c, "channel"),
    ),
    HosmartSensorDescription(
        key="last_activity_channel_name",
        name="Last activity channel name",
        icon="mdi:label-outline",
        value_fn=lambda c: _last_activity_value(c, "channel_name"),
    ),
    HosmartSensorDescription(
        key="last_activity_source",
        name="Last activity source",
        icon="mdi:source-branch",
        value_fn=lambda c: c.last_activity_source,
    ),
    HosmartSensorDescription(
        key="last_activity_time",
        name="Last activity time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-check-outline",
        value_fn=lambda c: c.last_activity_time,
    ),
    HosmartSensorDescription(
        key="last_event_change",
        name="Last event change",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-outline",
        value_fn=lambda c: c.last_event_change,
    ),
    HosmartSensorDescription(
        key="last_poll_time",
        name="Last poll time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:update",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        requires_local=True,
        value_fn=lambda c: c.last_poll_time,
    ),
    HosmartSensorDescription(
        key="poll_count",
        name="Poll count",
        icon="mdi:counter",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        requires_local=True,
        value_fn=lambda c: c.poll_count,
    ),
    HosmartSensorDescription(
        key="change_count",
        name="Receiver change count",
        icon="mdi:swap-horizontal",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        requires_local=True,
        value_fn=lambda c: c.change_count,
    ),
    HosmartSensorDescription(
        key="udp_packet_count",
        name="UDP packet count",
        icon="mdi:lan-connect",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        requires_local=True,
        value_fn=lambda c: c.udp_packet_count,
    ),
    HosmartSensorDescription(
        key="last_udp_time",
        name="Last UDP packet time",
        icon="mdi:clock-fast",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        requires_local=True,
        value_fn=_udp_time_value,
    ),
    HosmartSensorDescription(
        key="last_udp_source",
        name="Last UDP packet source",
        icon="mdi:ip-network-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        requires_local=True,
        value_fn=lambda c: c.last_udp_source or "Never observed",
    ),
    HosmartSensorDescription(
        key="cloud_alert_count",
        name="Cloud alert count",
        icon="mdi:counter",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda c: c.cloud_alert_count,
    ),
    HosmartSensorDescription(
        key="last_cloud_check",
        name="Last cloud check",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:cloud-clock",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda c: c.last_cloud_check_time,
    ),
    HosmartSensorDescription(
        key="internal_battery",
        name="Internal battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        requires_local=True,
        value_fn=lambda c: c.receiver.get("InternalBattery"),
    ),
    HosmartSensorDescription(
        key="volume",
        name="Volume",
        icon="mdi:volume-high",
        requires_local=True,
        value_fn=lambda c: c.receiver.get("Volume"),
    ),
    HosmartSensorDescription(
        key="child_device_count",
        name="Child device count",
        icon="mdi:counter",
        requires_local=True,
        value_fn=lambda c: c.receiver.get("ChildDeviceCount"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ho-Smart sensors."""
    coordinator: HosmartCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        HosmartSensor(coordinator, description)
        for description in SENSORS
        if not description.requires_local or coordinator.local_enabled
    )


class HosmartSensor(HosmartEntity, SensorEntity):
    """A Ho-Smart sensor."""

    entity_description: HosmartSensorDescription

    def __init__(
        self,
        coordinator: HosmartCoordinator,
        description: HosmartSensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self):
        """Return the current sensor value."""
        return self.entity_description.value_fn(self.coordinator)
