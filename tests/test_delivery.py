"""Regression tests for cloud outages and delayed driveway motion."""

import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

source = Path(__file__).resolve().parents[1] / "custom_components" / "hosmart" / "delivery.py"
spec = importlib.util.spec_from_file_location("delivery_under_test", source)
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)


class TestDelivery(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 22, 10, tzinfo=timezone.utc)

    def test_initial_baseline(self):
        self.assertEqual(delivery.cloud_query_start(self.now, None), self.now - timedelta(days=30))

    def test_four_hour_cloud_outage(self):
        last = self.now - timedelta(hours=4)
        self.assertEqual(delivery.cloud_query_start(self.now, last), last - timedelta(hours=1))

    def test_delayed_vendor_upload_is_rechecked(self):
        last = self.now - timedelta(minutes=10)
        self.assertEqual(
            delivery.cloud_query_start(self.now, last),
            last - timedelta(hours=1),
        )

    def test_future_checkpoint_is_clamped(self):
        self.assertEqual(
            delivery.cloud_query_start(self.now, self.now + timedelta(hours=1)),
            self.now - timedelta(hours=1),
        )

    def test_seven_day_recovery_limit(self):
        self.assertEqual(delivery.cloud_query_start(self.now, self.now - timedelta(days=10)), self.now - timedelta(days=7))

    def test_live_notice_age(self):
        self.assertTrue(delivery.is_live_notice(self.now - timedelta(seconds=120), self.now))
        self.assertFalse(delivery.is_live_notice(self.now - timedelta(seconds=121), self.now))

    def test_recovered_old_notice_is_not_live(self):
        self.assertFalse(delivery.is_live_notice(self.now - timedelta(minutes=4), self.now))

    def test_clock_skew(self):
        self.assertTrue(delivery.is_live_notice(self.now + timedelta(seconds=5), self.now))
        self.assertFalse(delivery.is_live_notice(self.now + timedelta(seconds=6), self.now))

    def test_driveway_is_channel_one(self):
        self.assertTrue(delivery.is_driveway_channel("1", "Driveway"))
        self.assertFalse(delivery.is_driveway_channel(2, "Driveway"))
        self.assertTrue(delivery.is_driveway_channel(None, "Main Drive", "Main Drive"))
        self.assertFalse(delivery.is_driveway_channel(None, "Garage"))


class TestCloudPagination(unittest.TestCase):
    @staticmethod
    def _cloud_module():
        path = source.parent / "cloud.py"
        spec = importlib.util.spec_from_file_location("hosmart_cloud_under_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_repeated_page_cursor_is_error(self):
        from unittest.mock import patch
        module = self._cloud_module()
        with patch.object(module, "_request_json", return_value={"data": [], "lastKey": "repeat"}):
            with self.assertRaises(module.HosmartCloudError):
                module.query_history("test", 1, 2, max_pages=3)

    def test_limit_cannot_silently_drop_records(self):
        from unittest.mock import patch
        module = self._cloud_module()
        with patch.object(module, "_request_json", return_value={"data": [], "lastKey": "more"}):
            with self.assertRaises(module.HosmartCloudError):
                module.query_history("test", 1, 2, max_pages=1)

    def test_normal_paginated_response(self):
        from unittest.mock import patch
        module = self._cloud_module()
        values = iter([
            {"data": [{"node_id": "a"}], "lastKey": "page-2"},
            {"data": [], "lastKey": None},
        ])
        with patch.object(module, "_request_json", side_effect=lambda *a, **k: next(values)):
            self.assertEqual(module.query_history("test", 1, 2), [{"node_id": "a"}])


if __name__ == "__main__":
    unittest.main()
