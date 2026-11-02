"""Isolated regression tests for per-channel overnight precedence."""

from datetime import datetime
import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components" / "hosmart" / "night_schedule.py"
)
spec = importlib.util.spec_from_file_location("night_schedule", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
spec.loader.exec_module(module)

plan = module.plan_channel_quiet


class ChannelQuietPlanTests(unittest.TestCase):
    def at(self, hour: int, minute: int = 0) -> datetime:
        return datetime(2026, 11, 2, hour, minute)

    def calculate(self, hour, channels=None, receiver=True, action="mute"):
        return plan(
            self.at(hour),
            receiver_enabled=receiver,
            receiver_start="22:00:00",
            receiver_end="07:00:00",
            receiver_action=action,
            channels=channels or {},
        )

    def test_legacy_global_receiver_behavior_preserved(self):
        self.assertEqual(self.calculate(23), ("mute", ()))
        self.assertEqual(self.calculate(8), (None, ()))

    def test_keep_driveway_channel_one_active(self):
        rules = {"1": {"mode": "always_active"}}
        self.assertEqual(self.calculate(23, rules), (None, (2, 3, 4)))
        self.assertEqual(self.calculate(8, rules), (None, ()))

    def test_protected_channel_prevents_global_power_off(self):
        rules = {"1": {"mode": "always_active"}}
        self.assertEqual(
            self.calculate(23, rules, action="power_off"),
            (None, (2, 3, 4)),
        )

    def test_individual_schedule_with_master_disabled(self):
        rules = {
            "2": {"mode": "custom", "start": "21:30", "end": "06:30"}
        }
        self.assertEqual(self.calculate(22, rules, receiver=False), (None, (2,)))
        self.assertEqual(self.calculate(7, rules, receiver=False), (None, ()))

    def test_independent_schedule_overrides_master(self):
        rules = {
            "2": {"mode": "custom", "start": "23:30", "end": "04:30"},
        }
        self.assertEqual(self.calculate(22, rules), (None, (1, 3, 4)))
        self.assertEqual(self.calculate(0, rules), ("mute", ()))
        self.assertEqual(self.calculate(5, rules), (None, (1, 3, 4)))

    def test_every_channel_can_be_protected(self):
        rules = {
            str(i): {"mode": "always_active"} for i in range(1, 5)
        }
        self.assertEqual(self.calculate(23, rules), (None, ()))

    def test_invalid_mode_refused(self):
        with self.assertRaises(ValueError):
            self.calculate(23, {"1": {"mode": "disable_all"}})

    def test_invalid_equal_channel_times(self):
        with self.assertRaises(ValueError):
            self.calculate(
                23,
                {"2": {"mode": "custom", "start": "22:00", "end": "22:00"}},
            )


if __name__ == "__main__":
    unittest.main()
