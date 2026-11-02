"""Direct receiver controls; no configuration wizard required."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_QUIET_ENABLED, DOMAIN
from .coordinator import HosmartCoordinator
from .entity import HosmartEntity
from .settings import async_set_quiet_setting


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Show master enable and all four zone controls on the receiver's device."""
    coordinator: HosmartCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    if not coordinator.local_enabled:
        return
    async_add_entities(
        [HosmartQuietEnabled(coordinator)]
        + [HosmartZoneArmed(coordinator, index) for index in range(1, 5)]
    )


class HosmartQuietEnabled(HosmartEntity, SwitchEntity):
    """Opt in or out of receiver-wide night quiet hours."""

    _attr_name = "00 Main: Quiet hours"
    _attr_icon = "mdi:weather-night"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: HosmartCoordinator) -> None:
        super().__init__(coordinator, "quiet_enabled")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.entry.options.get(CONF_QUIET_ENABLED, False))

    async def async_turn_on(self, **kwargs) -> None:
        await self._set_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set_enabled(False)

    async def _set_enabled(self, enabled: bool) -> None:
        await async_set_quiet_setting(
            self.hass, self.coordinator.entry, key=CONF_QUIET_ENABLED, value=enabled
        )
        self.async_write_ha_state()


class HosmartZoneArmed(HosmartEntity, SwitchEntity):
    """Direct local zone armed state.

    Turning off a zone DISARMS it; this can also prevent alarm reporting.
    The scheduled controller may overwrite manual arming during quiet hours.
    """

    _attr_icon = "mdi:shield-check"

    def __init__(self, coordinator: HosmartCoordinator, index: int) -> None:
        super().__init__(coordinator, f"zone_{index}_armed_control")
        self.index = index
        names = coordinator.entry.data.get("channel_names") or {}
        named = names.get(str(index)) if isinstance(names, dict) else None
        self._attr_name = (
            f"Channel {index} ({str(named)[:48]}) armed" if named
            else f"Channel {index} armed"
        )

    @property
    def available(self) -> bool:
        return bool(
            super().available
            and self.coordinator.local_enabled
            and self.coordinator.local_available
            and self._read() is not None
        )

    def _read(self) -> bool | None:
        value = self.coordinator.receiver.get(f"ZoneAlarming{self.index}")
        if type(value) in (bool, int) and value in (0, 1):
            return bool(value)
        return None

    @property
    def is_on(self) -> bool | None:
        return self._read()

    async def async_turn_on(self, **kwargs) -> None:
        await self._set_arm(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set_arm(False)

    async def _set_arm(self, value: bool) -> None:
        try:
            await self.coordinator.async_set_receiver_parameter(
                f"ZoneAlarming{self.index}", value
            )
        except Exception as err:
            raise HomeAssistantError(
                f"Receiver did not confirm Channel {self.index} "
                f"{'arm' if value else 'disarm'} command: {err}"
            ) from err
        self.async_write_ha_state()
