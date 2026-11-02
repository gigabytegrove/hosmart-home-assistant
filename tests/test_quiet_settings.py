"""Regression tests for direct schedule entity persistence without Home Assistant.

Module imports are isolated so the tests can run with the standard library in
CI; the Home Assistant integration itself is still checked by Hassfest.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "hosmart"


def load_settings_module():
    """Load the real option validation logic with small HA type stubs."""
    package = types.ModuleType("isolated_hosmart")
    package.__path__ = [str(ROOT)]
    fake_const = types.ModuleType("isolated_hosmart.const")
    for name, value in {
        "CHANNEL_ALWAYS_ACTIVE": "always_active",
        "CHANNEL_CUSTOM": "custom",
        "CHANNEL_INHERIT": "inherit",
        "CHANNEL_MODES": ("inherit", "always_active", "custom"),
        "CONF_CHANNEL_QUIET": "channel_quiet",
        "CONF_MODE": "connection_mode",
        "CONF_QUIET_ACTION": "quiet_action",
        "CONF_QUIET_ENABLED": "quiet_enabled",
        "CONF_QUIET_END": "quiet_end",
        "CONF_QUIET_START": "quiet_start",
        "DEFAULT_QUIET_END": "07:00:00",
        "DEFAULT_QUIET_START": "22:00:00",
        "MODE_CLOUD": "cloud",
        "QUIET_ACTION_MUTE": "mute",
        "QUIET_ACTION_POWER": "power_off",
    }.items():
        setattr(fake_const, name, value)

    ha = types.ModuleType("homeassistant")
    ha.__path__ = []
    ha_config = types.ModuleType("homeassistant.config_entries")
    ha_config.ConfigEntry = type("ConfigEntry", (), {})
    ha_core = types.ModuleType("homeassistant.core")
    ha_core.HomeAssistant = type("HomeAssistant", (), {})
    ha_error = types.ModuleType("homeassistant.exceptions")
    ha_error.HomeAssistantError = type("HomeAssistantError", (Exception,), {})

    modules = {
        "isolated_hosmart": package,
        "isolated_hosmart.const": fake_const,
        "homeassistant": ha,
        "homeassistant.config_entries": ha_config,
        "homeassistant.core": ha_core,
        "homeassistant.exceptions": ha_error,
    }
    with patch.dict(sys.modules, modules):
        schedule_spec = importlib.util.spec_from_file_location(
            "isolated_hosmart.night_schedule", ROOT / "night_schedule.py"
        )
        schedule = importlib.util.module_from_spec(schedule_spec)
        with patch.dict(sys.modules, {"isolated_hosmart.night_schedule": schedule}):
            assert schedule_spec.loader is not None
            schedule_spec.loader.exec_module(schedule)
            settings_spec = importlib.util.spec_from_file_location(
                "isolated_hosmart.settings", ROOT / "settings.py"
            )
            settings = importlib.util.module_from_spec(settings_spec)
            assert settings_spec.loader is not None
            settings_spec.loader.exec_module(settings)
            return settings


S = load_settings_module()


class OptionsTests(unittest.TestCase):
    def setUp(self):
        self.existing = {
            "connection_mode": "hybrid",
            "quiet_enabled": True,
            "quiet_start": "22:00:00",
            "quiet_end": "07:00:00",
            "quiet_action": "mute",
            "channel_quiet": {
                "1": {
                    "mode": "always_active",
                    "start": "22:00:00",
                    "end": "07:00:00",
                },
                "2": {
                    "mode": "custom",
                    "start": "21:00:00",
                    "end": "06:30:00",
                },
                "3": {
                    "mode": "inherit",
                    "start": "22:00:00",
                    "end": "07:00:00",
                },
            },
        }

    def test_change_channel_two_without_touching_one_or_three(self):
        result = S.updated_quiet_options(
            self.existing, key="end", value="08:15:00", channel=2
        )
        self.assertEqual(result["channel_quiet"]["2"]["end"], "08:15:00")
        self.assertEqual(
            result["channel_quiet"]["1"],
            self.existing["channel_quiet"]["1"],
        )
        self.assertEqual(
            result["channel_quiet"]["3"],
            self.existing["channel_quiet"]["3"],
        )
        self.assertEqual(
            self.existing["channel_quiet"]["2"]["end"], "06:30:00"
        )

    def test_receiver_toggle_preserves_all_channels(self):
        result = S.updated_quiet_options(
            self.existing, key="quiet_enabled", value=False
        )
        self.assertFalse(result["quiet_enabled"])
        self.assertEqual(result["channel_quiet"], self.existing["channel_quiet"])

    def test_channel_four_is_independent_and_created_without_wizard(self):
        result = S.updated_quiet_options(
            self.existing, key="mode", value="custom", channel=4
        )
        self.assertEqual(result["channel_quiet"]["4"]["mode"], "custom")
        self.assertEqual(
            result["channel_quiet"]["2"], self.existing["channel_quiet"]["2"]
        )

    def test_rename_channel_action_is_independent(self):
        result = S.updated_quiet_options(
            self.existing, key="action", value="arm", channel=2
        )
        self.assertEqual(result["channel_quiet"]["2"]["action"], "arm")
        self.assertEqual(
            result["channel_quiet"]["1"],
            self.existing["channel_quiet"]["1"],
        )

    def test_disarm_action_cannot_be_replaced_by_invalid_mute(self):
        with self.assertRaises(ValueError):
            S.updated_quiet_options(
                self.existing, key="action", value="mute_all_while_armed",
                channel=2,
            )

    def test_custom_start_cannot_equal_end(self):
        with self.assertRaisesRegex(ValueError, "Channel 2"):
            S.updated_quiet_options(
                self.existing, key="start", value="06:30:00", channel=2
            )

    def test_receiver_start_cannot_equal_end(self):
        with self.assertRaisesRegex(ValueError, "Receiver"):
            S.updated_quiet_options(
                self.existing, key="quiet_start", value="07:00:00"
            )

    def test_reject_nonlocal_timestamps(self):
        with self.assertRaises(ValueError):
            S.updated_quiet_options(
                self.existing, key="quiet_end", value="07:00:00+00:00"
            )

    def test_cannot_enable_when_cloud_only(self):
        options = {
            "connection_mode": "cloud",
            "quiet_enabled": False,
        }
        with self.assertRaisesRegex(ValueError, "Local or Hybrid"):
            S.updated_quiet_options(
                options, key="quiet_enabled", value=True
            )

    def test_reject_invalid_zone_and_mode(self):
        with self.assertRaises(ValueError):
            S.updated_quiet_options(
                self.existing, key="mode", value="unexpected", channel=4
            )
        with self.assertRaises(ValueError):
            S.updated_quiet_options(
                self.existing, key="mode", value="inherit", channel=5
            )


class EntityPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_change_updates_entry_once(self):
        class Entry:
            options = {"connection_mode": "hybrid"}

        entry = Entry()
        writes = []

        class ConfigEntries:
            def async_update_entry(self, obj, *, options):
                writes.append(options)
                obj.options = options

        hass = types.SimpleNamespace(config_entries=ConfigEntries())
        await S.async_set_quiet_setting(
            hass, entry, key="quiet_enabled", value=True
        )
        self.assertEqual(len(writes), 1)
        self.assertTrue(entry.options["quiet_enabled"])

    async def test_unchanged_setting_does_not_write(self):
        class Entry:
            options = {"connection_mode": "hybrid", "quiet_enabled": False}

        writes = []

        class ConfigEntries:
            def async_update_entry(self, obj, *, options):
                writes.append(options)

        await S.async_set_quiet_setting(
            types.SimpleNamespace(config_entries=ConfigEntries()),
            Entry(),
            key="quiet_enabled",
            value=False,
        )
        self.assertEqual(writes, [])


if __name__ == "__main__":
    unittest.main()
