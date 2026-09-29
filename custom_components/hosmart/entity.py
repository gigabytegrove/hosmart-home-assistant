"""Base entity for Ho-Smart."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HosmartCoordinator


class HosmartEntity(CoordinatorEntity[HosmartCoordinator]):
    """Base Ho-Smart entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HosmartCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        node_id = coordinator.node_id or coordinator.entry.entry_id
        self._attr_unique_id = f"{node_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return receiver device information."""
        data = self.coordinator.data or {}
        receiver = self.coordinator.receiver
        node_id = self.coordinator.node_id or self.coordinator.entry.entry_id
        return DeviceInfo(
            identifiers={(DOMAIN, str(node_id))},
            name=receiver.get("Name") or self.coordinator.entry.title or "Ho-Smart Receiver",
            manufacturer="Ho-Smart",
            model=data.get("model"),
            sw_version=data.get("fw_version"),
        )
