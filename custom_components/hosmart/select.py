"""Receiver action and channel scheduling modes as native selectors."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CHANNEL_ALWAYS_ACTIVE,
    CHANNEL_CUSTOM,
    CHANNEL_INHERIT,
    CONF_QUIET_ACTION,
    DEFAULT_QUIET_ACTION,
    DOMAIN,
    QUIET_ACTION_MUTE,
    QUIET_ACTION_POWER,
)
from .coordinator import HosmartCoordinator
from .entity import HosmartEntity
from .settings import async_set_quiet_setting, get_channel_setting


RECEIVER_ACTIONS = {
    "Mute receiver audio": QUIET_ACTION_MUTE,
    "Power off receiver (may disconnect Wi-Fi)": QUIET_ACTION_POWER,
}
CHANNEL_ACTIONS = {
    "Follow receiver-wide hours": CHANNEL_INHERIT,
    "Always armed (protected)": CHANNEL_ALWAYS_ACTIVE,
    "Disarm on custom schedule (stops detection)": CHANNEL_CUSTOM,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Show action and all channel modes on the device's configuration section."""
    coordinator: HosmartCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    if not coordinator.local_enabled:
        return
    async_add_entities(
        [HosmartQuietSelect(coordinator, None)]
        + [HosmartQuietSelect(coordinator, channel) for channel in range(1, 5)]
    )


class HosmartQuietSelect(HosmartEntity, SelectEntity):
    """Change an individual schedule mode without an options wizard."""

    _attr_icon = "mdi:tune-vertical"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: HosmartCoordinator, channel: int | None) -> None:
        key = "receiver_quiet_action" if channel is None else f"channel_{channel}_quiet_mode"
        super().__init__(coordinator, key)
        self._channel = channel
        self._choices = RECEIVER_ACTIONS if channel is None else CHANNEL_ACTIONS
        self._attr_options = list(self._choices)
        self._attr_name = (
            "Receiver quiet-hours action" if channel is None
            else f"Channel {channel} overnight behavior"
        )

    @property
    def current_option(self) -> str | None:
        value = (
            self.coordinator.entry.options.get(CONF_QUIET_ACTION, DEFAULT_QUIET_ACTION)
            if self._channel is None else get_channel_setting(
                self.coordinator.entry, self._channel, "mode"
            )
        )
        return next((label for label, code in self._choices.items() if code == value), None)

    async def async_select_option(self, option: str) -> None:
        await async_set_quiet_setting(
            self.hass,
            self.coordinator.entry,
            key=CONF_QUIET_ACTION if self._channel is None else "mode",
            value=self._choices[option],
            channel=self._channel,
        )
        self.async_write_ha_state()
