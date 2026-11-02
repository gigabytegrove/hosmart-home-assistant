"""Remove obsolete flat quiet-hours entities from the receiver device page.

The v0.2.8 legacy schedule controls stay registered and continue working for
existing automations. Detaching device associations is reversible and avoids
the Home Assistant '(Hidden)' controls still appearing in the device's
Configuration area. Unlike deleting entity registry entries, this preserves
entity IDs, state, and user-defined names.
"""

from __future__ import annotations

from typing import Any

LEGACY_CONTROLS: tuple[tuple[str, str], ...] = (
    ("select", "receiver_quiet_action"),
    ("time", "receiver_quiet_start"),
    ("time", "receiver_quiet_end"),
    *(( "select", f"channel_{i}_quiet_mode") for i in range(1, 5)),
    *(( "time", f"channel_{i}_quiet_start") for i in range(1, 5)),
    *(( "time", f"channel_{i}_quiet_end") for i in range(1, 5)),
)


def detach_legacy_schedule_entities(
    registry: Any, *, platform: str, node_id: str, entry_id: str
) -> int:
    """Detach only this config entry's former flat schedule controls.

    Works on new and previously migrated entries. No one-time migration
    marker: it rechecks after every setup to avoid reinstating legacy
    controls through automatic entity/device association.
    """
    detached = 0
    for domain, key in LEGACY_CONTROLS:
        entity_id = registry.async_get_entity_id(
            domain, platform, f"{node_id}_{key}"
        )
        if entity_id is None:
            continue
        entity = registry.async_get(entity_id)
        if (
            entity is None
            or entity.config_entry_id != entry_id
            or entity.device_id is None
        ):
            continue
        registry.async_update_entity(entity_id, device_id=None)
        detached += 1
    return detached
