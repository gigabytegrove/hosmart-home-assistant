"""Regression coverage for HACS/Marketplace stable/dev synchronization.

Only our verified GitHub repository's unique ID is allowed to be toggled.
All tests use lightweight fake HA registries and service calls.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "hosmart"

pkg = types.ModuleType("isolated_release_channel")
pkg.__path__ = [str(ROOT)]
const = types.ModuleType("isolated_release_channel.const")
const.CONF_RELEASE_CHANNEL = "release_channel"
registry_module = types.ModuleType("homeassistant.helpers.entity_registry")
ha = types.ModuleType("homeassistant")
ha.__path__ = []
helpers = types.ModuleType("homeassistant.helpers")
helpers.__path__ = []
helpers.entity_registry = registry_module
with patch.dict(sys.modules, {
    "isolated_release_channel": pkg,
    "isolated_release_channel.const": const,
    "homeassistant": ha,
    "homeassistant.helpers": helpers,
    "homeassistant.helpers.entity_registry": registry_module,
}):
    spec = importlib.util.spec_from_file_location(
        "isolated_release_channel.hacs_channel", ROOT / "hacs_channel.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)


class Entry:
    def __init__(self, entity_id, platform, disabled_by=None):
        self.entity_id = entity_id
        self.domain = "switch"
        self.platform = platform
        self.disabled_by = disabled_by


class Registry:
    def __init__(self, entries):
        self.entries = entries
        self.updated = []

    def async_get_entity_id(self, domain, platform, unique_id):
        entry = self.entries.get((domain, platform, unique_id))
        return entry.entity_id if entry else None

    def async_get(self, entity_id):
        return next(
            (entry for entry in self.entries.values()
             if entry.entity_id == entity_id), None
        )

    def async_update_entity(self, entity_id, *, disabled_by):
        self.updated.append((entity_id, disabled_by))
        self.async_get(entity_id).disabled_by = disabled_by


class FakeState:
    def __init__(self, state):
        self.state = state


class States:
    def __init__(self, states=None):
        self.states = states or {}

    def get(self, entity_id):
        return self.states.get(entity_id)


class Services:
    def __init__(self, states):
        self.states = states
        self.calls = []

    def has_service(self, domain, service):
        return domain == "switch" and service == "turn_on"

    async def async_call(self, domain, service, data, *, blocking):
        self.calls.append((domain, service, data, blocking))
        self.states.states[data["entity_id"]] = FakeState(
            "on" if service == "turn_on" else "off"
        )


class FakeHass:
    def __init__(self, registry, states=None):
        self.registry = registry
        self.states = States(states)
        self.services = Services(self.states)


registry_module.async_get = lambda hass: hass.registry

OWN_ID = module.REPOSITORY_ID


class ReleaseChannelTests(unittest.IsolatedAsyncioTestCase):
    async def test_main_and_dev_map_to_actual_prerelease_switch(self):
        self.assertEqual(module.desired_switch_state("main"), "off")
        self.assertEqual(module.desired_switch_state("dev"), "on")
        with self.assertRaises(ValueError):
            module.desired_switch_state("nightly")

    async def test_exact_marketplace_id_chosen_not_other_project(self):
        other = Entry("switch.other_pre_release", "marketplace")
        ours = Entry("switch.hosmart_pre_release", "marketplace")
        registry = Registry({
            ("switch", "marketplace", "999999"): other,
            ("switch", "marketplace", OWN_ID): ours,
        })
        hass = FakeHass(registry, {
            ours.entity_id: FakeState("off"),
            other.entity_id: FakeState("off"),
        })
        self.assertEqual(
            await module.async_apply_release_channel(hass, "dev"),
            "dev_tracking",
        )
        self.assertEqual(hass.services.calls, [
            ("switch", "turn_on", {"entity_id": ours.entity_id}, True)
        ])
        self.assertEqual(hass.states.get(other.entity_id).state, "off")

    async def test_classic_hacs_provider_supported(self):
        ours = Entry("switch.hosmart_pre_release", "hacs")
        reg = Registry({("switch", "hacs", OWN_ID): ours})
        hass = FakeHass(reg, {ours.entity_id: FakeState("on")})
        status = await module.async_apply_release_channel(hass, "main")
        self.assertEqual(status, "main_tracking")
        self.assertEqual(hass.services.calls[0][1], "turn_off")

    async def test_disabled_switch_enabled_then_retry_is_safe(self):
        ours = Entry("switch.pre_release", "marketplace", "integration")
        reg = Registry({("switch", "marketplace", OWN_ID): ours})
        hass = FakeHass(reg)
        status = await module.async_apply_release_channel(hass, "dev")
        self.assertEqual(status, "enabling_prerelease_control")
        self.assertEqual(reg.updated, [(ours.entity_id, None)])
        self.assertEqual(hass.services.calls, [])
        self.assertEqual(
            await module.async_apply_release_channel(hass, "dev"),
            "waiting_for_prerelease_control",
        )
        hass.states.states[ours.entity_id] = FakeState("off")
        self.assertEqual(
            await module.async_apply_release_channel(hass, "dev"),
            "dev_tracking",
        )

    async def test_missing_switch_never_claims_success(self):
        hass = FakeHass(Registry({}))
        self.assertEqual(
            await module.async_apply_release_channel(hass, "dev"),
            "waiting_for_marketplace",
        )
        self.assertEqual(hass.services.calls, [])

    async def test_already_selected_channel_is_idempotent(self):
        ours = Entry("switch.own", "marketplace")
        reg = Registry({("switch", "marketplace", OWN_ID): ours})
        hass = FakeHass(reg, {ours.entity_id: FakeState("on")})
        self.assertEqual(
            await module.async_apply_release_channel(hass, "dev"),
            "dev_tracking",
        )
        self.assertEqual(hass.services.calls, [])

    async def test_multi_receiver_selection_is_consistent(self):
        class Receiver:
            def __init__(self, name, channel=None):
                self.entry_id = name
                self.options = ({"release_channel": channel} if channel else {})

        a = Receiver("a", "main")
        b = Receiver("b", "dev")
        writes = []

        class Entries:
            def async_entries(self, domain):
                self.domain = domain
                return [a, b]

            def async_update_entry(self, entry, *, options):
                entry.options = options
                writes.append((entry.entry_id, options["release_channel"]))

        hass = types.SimpleNamespace(config_entries=Entries())
        module.align_receiver_preferences(hass, b)
        self.assertEqual(hass.config_entries.domain, "hosmart")
        self.assertEqual(a.options["release_channel"], "dev")
        self.assertEqual(writes, [("a", "dev")])

    async def test_legacy_unselected_channel_does_not_override_hacs(self):
        entry = types.SimpleNamespace(options={})
        self.assertIsNone(module.selected_channel(entry))


if __name__ == "__main__":
    unittest.main()
