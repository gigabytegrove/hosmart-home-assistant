"""Never disarm a muted-only channel, even with mixed schedules."""

from datetime import datetime
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "hosmart"
package = types.ModuleType("isolated_quiet")
package.__path__ = [str(ROOT)]
with patch.dict(sys.modules, {"isolated_quiet": package}):
    spec = importlib.util.spec_from_file_location(
        "isolated_quiet.night_schedule", ROOT / "night_schedule.py"
    )
    night = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(night)
    with patch.dict(sys.modules, {"isolated_quiet.night_schedule": night}):
        ps = importlib.util.spec_from_file_location(
            "isolated_quiet.schedule_actions", ROOT / "schedule_actions.py"
        )
        actions = importlib.util.module_from_spec(ps)
        assert ps.loader
        ps.loader.exec_module(actions)

def plan(hour, action="disarm", channels=None, enabled=True):
    return actions.build_schedule_plan(
        datetime(2026,11,2,hour),
        enabled=enabled,
        start="22:00:00",
        end="07:00:00",
        default_action=action,
        channels=channels or {},
    )

class ScheduleActionsTests(unittest.TestCase):
    def test_default_disarms_every_channel_overnight(self):
        writes, status = plan(23)
        self.assertEqual(writes,{f"ZoneAlarming{i}":False for i in range(1,5)})
        self.assertEqual(set(status.values()),{"scheduled_disarm"})
        self.assertEqual(plan(7)[0],{})

    def test_protected_driveway_never_disarmed(self):
        writes, states = plan(23,channels={"1":{"mode":"always_active"}})
        self.assertEqual(writes,{f"ZoneAlarming{i}":False for i in (2,3,4)})
        self.assertEqual(states[1],"protected")

    def test_mute_tone_never_disarms_or_silences_shared_volume(self):
        changes,states=plan(
            23,"disarm",
            {"1":{"mode":"custom","start":"22:00","end":"07:00",
                  "action":"mute_tone"}}
        )
        self.assertNotIn("ZoneAlarming1",changes)
        self.assertNotIn("Volume",changes)
        self.assertEqual(states[1],"unsupported_tone_mute")

    def test_global_mute_never_silences_protected_channel(self):
        writes,states=plan(23,"mute",{"1":{"mode":"always_active"}})
        self.assertEqual(writes,{})
        self.assertEqual(states[1],"protected")
        self.assertEqual(states[2],"unsupported_global_mute")

    def test_legacy_global_mute_all_if_all_inherit(self):
        writes,states=plan(23,"mute")
        self.assertEqual(writes,{"Volume":0})
        self.assertEqual(states[3],"muted_all")

    def test_custom_arm_vs_disarm(self):
        writes,_=plan(23,channels={"2":{"mode":"custom","action":"arm",
                                      "start":"22:00","end":"07:00"}})
        self.assertTrue(writes["ZoneAlarming2"])
        self.assertFalse(writes["ZoneAlarming1"])

    def test_disabled_master_can_still_use_independent_zone_schedule(self):
        writes,states=plan(23,enabled=False,channels={
            "3":{"mode":"custom","action":"disarm",
                 "start":"20:00","end":"05:00"}
        })
        self.assertEqual(writes,{"ZoneAlarming3":False})
        self.assertEqual(states[2],"active")

    def test_invalid_action_fails_without_writes(self):
        with self.assertRaises(ValueError):
            plan(23,"unknown")
        with self.assertRaises(ValueError):
            plan(23,channels={"3":{"mode":"custom","action":"invalid",
                                    "start":"22:00","end":"07:00"}})

if __name__ == "__main__":
    unittest.main()
