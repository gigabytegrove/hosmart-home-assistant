"""Synchronize Ho-Smart's update channel with HACS / Marketplace.

Only the owning marketplace's repository Pre-release switch determines
automatic update discovery. The Ho-Smart config option is a preference;
switch.turn_on/off is the documented public API used to enforce it.

The repository's immutable GitHub ID is verified from GitHub's REST API.
Both HACS 2.x and the built-in Marketplace (HA 2026.11+) use that ID as
the Pre-release switch entity's unique_id, even when it is disabled.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.helpers import entity_registry as er

from .const import CONF_RELEASE_CHANNEL

_LOGGER = logging.getLogger(__name__)

REPOSITORY_ID = "1393997438"
STABLE = "main"
DEVELOPMENT = "dev"
VALID_CHANNELS = (STABLE, DEVELOPMENT)
PROVIDERS = ("marketplace", "hacs")


def desired_switch_state(channel: str) -> str:
    """Return HACS prerelease switch state; reject unknown settings."""
    if channel == STABLE:
        return "off"
    if channel == DEVELOPMENT:
        return "on"
    raise ValueError("Release channel must be main or dev")


def locate_prerelease_switch(registry: Any) -> Any | None:
    """Find only our own repository switch in an entity registry."""
    for platform in PROVIDERS:
        entity_id = registry.async_get_entity_id(
            "switch", platform, REPOSITORY_ID
        )
        if entity_id is None:
            continue
        entry = registry.async_get(entity_id)
        if entry is not None and entry.domain == "switch" and entry.platform == platform:
            return entry
    return None


async def async_apply_release_channel(hass: Any, channel: str) -> str:
    """Set HACS/Marketplace release tracking and return a diagnostic status.

    'enabled' means Home Assistant must first materialize a previously
    disabled switch; the next periodic sync will turn it on/off.
    'missing' means HACS/Marketplace has not registered the repository.
    Never change other repositories or write to installed integration files.
    """
    target = desired_switch_state(channel)
    registry = er.async_get(hass)
    entity = locate_prerelease_switch(registry)
    if entity is None:
        return "waiting_for_marketplace"
    if entity.disabled_by is not None:
        registry.async_update_entity(entity.entity_id, disabled_by=None)
        return "enabling_prerelease_control"
    state = hass.states.get(entity.entity_id)
    if state is None or state.state not in ("on", "off"):
        return "waiting_for_prerelease_control"
    if state.state == target:
        return "main_tracking" if channel == STABLE else "dev_tracking"

    if not hass.services.has_service("switch", "turn_on"):
        return "waiting_for_switch_service"
    await hass.services.async_call(
        "switch",
        "turn_on" if target == "on" else "turn_off",
        {"entity_id": entity.entity_id},
        blocking=True,
    )
    # Don't claim the provider applied it until a real state read confirms.
    current = hass.states.get(entity.entity_id)
    if current is None or current.state != target:
        return "waiting_for_prerelease_control"
    return "main_tracking" if channel == STABLE else "dev_tracking"


def align_receiver_preferences(hass: Any, selected_entry: Any) -> None:
    """One integration install = one global update channel, not per receiver."""
    channel = selected_entry.options.get(CONF_RELEASE_CHANNEL)
    if channel is None:
        return
    desired_switch_state(channel)
    for entry in hass.config_entries.async_entries("hosmart"):
        if entry.entry_id == selected_entry.entry_id:
            continue
        if entry.options.get(CONF_RELEASE_CHANNEL) != channel:
            hass.config_entries.async_update_entry(
                entry,
                options={**entry.options, CONF_RELEASE_CHANNEL: channel},
            )


def selected_channel(entry: Any) -> str | None:
    """Legacy entries remain unaffected until the channel is selected."""
    channel = entry.options.get(CONF_RELEASE_CHANNEL)
    return channel if channel in VALID_CHANNELS else None
