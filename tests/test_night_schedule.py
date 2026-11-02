"""Behavioral tests for overnight and same-day receiver schedules."""

from datetime import datetime
import importlib.util
from pathlib import Path
import unittest

# Load the pure module without requiring a Home Assistant installation.
_MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components" / "hosmart" / "night_schedule.py"
)
_SPEC = importlib.util.spec_from_file_location("night_schedule", _MODULE_PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(_MODULE)

is_quiet_now = _MODULE.is_quiet_now
parse_time = _MODULE.parse_time


class TestNightSchedule(unittest.TestCase):
    def at(self, h: int, m: int = 0) -> datetime:
        return datetime(2026, 11, 2, h, m)

    def test_over_midnight(self):
        for hour in (22, 23, 0, 2, 6):
            self.assertTrue(is_quiet_now(self.at(hour), "22:00", "07:00"))
        for hour in (7, 8, 12, 21):
            self.assertFalse(is_quiet_now(self.at(hour), "22:00", "07:00"))

    def test_exact_boundaries(self):
        self.assertFalse(is_quiet_now(self.at(21, 59), "22:00", "07:00"))
        self.assertTrue(is_quiet_now(self.at(22), "22:00", "07:00"))
        self.assertTrue(is_quiet_now(self.at(6, 59), "22:00", "07:00"))
        self.assertFalse(is_quiet_now(self.at(7), "22:00", "07:00"))

    def test_daytime(self):
        self.assertFalse(is_quiet_now(self.at(7), "09:00", "17:00"))
        self.assertTrue(is_quiet_now(self.at(12), "09:00", "17:00"))
        self.assertFalse(is_quiet_now(self.at(17), "09:00", "17:00"))

    def test_time_selector_with_seconds(self):
        self.assertTrue(is_quiet_now(self.at(23), "22:00:00", "07:00:00"))

    def test_equal_times_rejected(self):
        with self.assertRaises(ValueError):
            is_quiet_now(self.at(10), "22:00", "22:00")

    def test_timezone_offsets_rejected(self):
        with self.assertRaises(ValueError):
            parse_time("22:00+04:00")


if __name__ == "__main__":
    unittest.main()
