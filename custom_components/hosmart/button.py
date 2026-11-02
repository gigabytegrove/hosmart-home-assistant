"""Explicit HACS-managed integration installation action."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_RELEASE_CHANNEL, DOMAIN
from .coordinator import HosmartCoordinator
from .entity import HosmartEntity
from .release_install import (
    RELEASE_CHANNEL_MAIN,
    async_install_channel,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: HosmartCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([HosmartInstallSelectedChannel(coordinator)])


class HosmartInstallSelectedChannel(HosmartEntity, ButtonEntity):
    """User-initiated install via HACS, never direct filesystem manipulation."""

    _attr_name = "91 Install selected channel"
    _attr_icon = "mdi:download"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: HosmartCoordinator) -> None:
        super().__init__(coordinator, "install_selected_software_channel")

    async def async_press(self) -> None:
        selected = self.coordinator.entry.options.get(
            CONF_RELEASE_CHANNEL, RELEASE_CHANNEL_MAIN
        )
        if selected not in ("main", "dev"):
            raise HomeAssistantError("Invalid selected software channel")
        await async_install_channel(self.hass, selected)
        # HACS writes the integration files; HA restart must be done manually.
