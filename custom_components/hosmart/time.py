"""Always-visible receiver and per-channel time pickers."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_QUIET_END,
    CONF_QUIET_START,
    DEFAULT_QUIET_END,
    DEFAULT_QUIET_START,
    DOMAIN,
)
from .coordinator import HosmartCoordinator
from .entity import HosmartEntity
from .settings import as_time, async_set_quiet_setting, get_channel_setting


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Expose both endpoints for receiver and all four channels at once."""
    coordinator: HosmartCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    if not coordinator.local_enabled:
        return
    entities = [
        HosmartQuietTime(coordinator, None, "start"),
        HosmartQuietTime(coordinator, None, "end"),
    ]
    for channel in range(1, 5):
        entities.append(HosmartQuietTime(coordinator, channel, "start"))
        entities.append(HosmartQuietTime(coordinator, channel, "end"))
    async_add_entities(entities)


class HosmartQuietTime(HosmartEntity, TimeEntity):
    """Persist a local time-of-day without restarting Home Assistant integration."""

    _attr_icon = "mdi:clock-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: HosmartCoordinator, channel: int | None, boundary: str
    ) -> None:
        prefix = "receiver" if channel is None else f"channel_{channel}"
        super().__init__(coordinator, f"{prefix}_quiet_{boundary}")
        self._channel = channel
        self._boundary = boundary
        display = "Receiver" if channel is None else f"Channel {channel}"
        self._attr_name = f"{display} quiet {'starts' if boundary == 'start' else 'ends'}"

    @property
    def native_value(self) -> time:
        if self._channel is None:
            key = CONF_QUIET_START if self._boundary == "start" else CONF_QUIET_END
            fallback = (
                DEFAULT_QUIET_START if self._boundary == "start" else DEFAULT_QUIET_END
            )
            return as_time(self.coordinator.entry.options.get(key, fallback))
        return as_time(
            get_channel_setting(self.coordinator.entry, self._channel, self._boundary)
        )

    async def async_set_value(self, value: time) -> None:
        key = (
            (CONF_QUIET_START if self._boundary == "start" else CONF_QUIET_END)
            if self._channel is None else self._boundary
        )
        await async_set_quiet_setting(
            self.hass,
            self.coordinator.entry,
            key=key,
            value=value.isoformat(timespec="seconds"),
            channel=self._channel,
        )
        self.async_write_ha_state()
