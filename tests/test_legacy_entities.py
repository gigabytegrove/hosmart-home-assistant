"""Regression tests for cleaning the legacy configuration entity list."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

MODULE = (
    Path(__file__).resolve().parents[1]
    / "custom_components" / "hosmart" / "legacy_entities.py"
)
spec = importlib.util.spec_from_file_location("legacy_entities", MODULE)
legacy = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(legacy)


class Entry:
    def __init__(self, entry_id, device_id):
        self.config_entry_id = entry_id
        self.device_id = device_id


class Registry:
    def __init__(self):
        self.entities = {}
        self.events = []

    def add(self, domain, platform, uid, entity_id, entry_id, device_id):
        self.entities[(domain, platform, uid)] = (
            entity_id, Entry(entry_id, device_id)
        )

    def async_get_entity_id(self, domain, platform, uid):
        found = self.entities.get((domain, platform, uid))
        return found[0] if found else None

    def async_get(self, entity_id):
        for value in self.entities.values():
            if value[0] == entity_id:
                return value[1]
        return None

    def async_update_entity(self, entity_id, *, device_id):
        self.events.append((entity_id, device_id))
        self.async_get(entity_id).device_id = device_id


class LegacyEntityTests(unittest.TestCase):
    def test_legacy_keys_are_only_old_time_and_select_controls(self):
        self.assertEqual(len(legacy.LEGACY_CONTROLS), 15)
        self.assertTrue(all(
            domain in ("select", "time")
            for domain, _ in legacy.LEGACY_CONTROLS
        ))
        self.assertEqual(
            len({key for _, key in legacy.LEGACY_CONTROLS}), 15
        )

    def test_old_device_rows_detached_but_unique_ids_remain(self):
        reg = Registry()
        for idx, (domain, key) in enumerate(legacy.LEGACY_CONTROLS):
            reg.add(
                domain, "hosmart", f"node1_{key}",
                f"{domain}.legacy_{idx}", "entry1", "device1"
            )
        count = legacy.detach_legacy_schedule_entities(
            reg, platform="hosmart", node_id="node1", entry_id="entry1"
        )
        self.assertEqual(count, 15)
        self.assertEqual(len(reg.events), 15)
        for domain, key in legacy.LEGACY_CONTROLS:
            entity_id = reg.async_get_entity_id(
                domain, "hosmart", f"node1_{key}"
            )
            self.assertIsNotNone(entity_id)
            self.assertIsNone(reg.async_get(entity_id).device_id)

        # Repeated starts do not modify anything or erase IDs.
        self.assertEqual(
            legacy.detach_legacy_schedule_entities(
                reg, platform="hosmart", node_id="node1", entry_id="entry1"
            ), 0
        )
        self.assertEqual(len(reg.events), 15)

    def test_does_not_touch_other_receivers_or_unrelated_entities(self):
        reg = Registry()
        reg.add(
            "time", "hosmart", "node1_channel_1_quiet_start",
            "time.other_receiver", "entry-other", "other-device"
        )
        reg.add(
            "time", "hosmart", "node2_channel_1_quiet_start",
            "time.node2", "entry2", "device2"
        )
        reg.add(
            "switch", "hosmart", "node1_quiet_enabled",
            "switch.default_schedule", "entry1", "device1"
        )
        self.assertEqual(
            legacy.detach_legacy_schedule_entities(
                reg, platform="hosmart", node_id="node1", entry_id="entry1"
            ), 0
        )
        self.assertEqual(reg.events, [])
        self.assertEqual(
            reg.async_get("switch.default_schedule").device_id, "device1"
        )


if __name__ == "__main__":
    unittest.main()
