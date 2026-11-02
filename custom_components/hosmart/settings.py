"""Persistent receiver/channel schedule settings edited by Home Assistant entities.

Existing v0.2.7 config-entry options are preserved. All writes are validated
and applied in place; changing a time never triggers a receiver reconnect.
"""

from __future__ import annotations

from datetime import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CHANNEL_ALWAYS_ACTIVE,
    CHANNEL_CUSTOM,
    CHANNEL_INHERIT,
    CHANNEL_MODES,
    CONF_CHANNEL_QUIET,
    CONF_MODE,
    CONF_QUIET_ACTION,
    CONF_QUIET_ENABLED,
    CONF_QUIET_END,
    CONF_QUIET_START,
    DEFAULT_QUIET_END,
    DEFAULT_QUIET_START,
    MODE_CLOUD,
    QUIET_ACTION_MUTE,
    QUIET_ACTION_POWER,
)
from .night_schedule import parse_time

RECEIVER_ACTIONS = (QUIET_ACTION_MUTE, QUIET_ACTION_POWER)
RECEIVER_TIMES = (CONF_QUIET_START, CONF_QUIET_END)


def get_channel_setting(entry: ConfigEntry, channel: int, field: str) -> str:
    """Read channel setting from the existing persisted options format."""
    rules = entry.options.get(CONF_CHANNEL_QUIET, {})
    if not isinstance(rules, dict):
        rules = {}
    item = rules.get(str(channel), {})
    if not isinstance(item, dict):
        item = {}
    if field == "mode":
        return str(item.get(field, CHANNEL_INHERIT))
    return str(
        item.get(
            field,
            DEFAULT_QUIET_START if field == "start" else DEFAULT_QUIET_END,
        )
    )


def updated_quiet_options(
    old: dict[str, Any],
    *,
    key: str,
    value: Any,
    channel: int | None = None,
) -> dict[str, Any]:
    """Build a validated copy; reject destructive or inconsistent settings."""
    options = dict(old)
    if channel is None:
        if key == CONF_QUIET_ENABLED:
            if type(value) is not bool:
                raise ValueError("Quiet-hours enabled must be a boolean")
        elif key == CONF_QUIET_ACTION:
            if value not in RECEIVER_ACTIONS:
                raise ValueError("Unsupported receiver quiet-hours action")
        elif key in RECEIVER_TIMES:
            if not isinstance(value, str):
                raise ValueError("Quiet-hours time must be ISO local time")
            parse_time(value)
        else:
            raise ValueError("Unknown receiver quiet-hours setting")
        options[key] = value
    else:
        if channel not in (1, 2, 3, 4) or key not in ("mode", "start", "end"):
            raise ValueError("Unknown channel quiet-hours setting")
        if key == "mode":
            if value not in CHANNEL_MODES:
                raise ValueError("Unsupported channel quiet-hours mode")
        else:
            if not isinstance(value, str):
                raise ValueError("Channel quiet-hours time must be ISO local time")
            parse_time(value)
        raw = options.get(CONF_CHANNEL_QUIET, {})
        rules = {
            name: dict(rule)
            for name, rule in raw.items()
            if isinstance(name, str) and isinstance(rule, dict)
        } if isinstance(raw, dict) else {}
        item = dict(rules.get(str(channel), {}))
        item[key] = value
        rules[str(channel)] = item
        options[CONF_CHANNEL_QUIET] = rules

    start = options.get(CONF_QUIET_START, DEFAULT_QUIET_START)
    end = options.get(CONF_QUIET_END, DEFAULT_QUIET_END)
    if parse_time(start) == parse_time(end):
        raise ValueError("Receiver quiet-hours start and end must differ")
    rules = options.get(CONF_CHANNEL_QUIET, {})
    has_custom = False
    if isinstance(rules, dict):
        for i in range(1, 5):
            rule = rules.get(str(i), {})
            if not isinstance(rule, dict):
                raise ValueError(f"Invalid Channel {i} settings")
            mode = rule.get("mode", CHANNEL_INHERIT)
            if mode not in CHANNEL_MODES:
                raise ValueError(f"Invalid Channel {i} mode")
            if mode == CHANNEL_CUSTOM:
                has_custom = True
                if parse_time(rule.get("start", DEFAULT_QUIET_START)) == parse_time(
                    rule.get("end", DEFAULT_QUIET_END)
                ):
                    raise ValueError(f"Channel {i} quiet-hours start and end must differ")

    if options.get(CONF_MODE) == MODE_CLOUD and (
        options.get(CONF_QUIET_ENABLED, False) or has_custom
    ):
        raise ValueError("Quiet hours need Local or Hybrid connection mode")
    return options


async def async_set_quiet_setting(
    hass: HomeAssistant,
    entry: ConfigEntry,
    *,
    key: str,
    value: str | bool,
    channel: int | None = None,
) -> None:
    """Persist one property; normal update listener re-arms scheduling in place."""
    try:
        options = updated_quiet_options(
            dict(entry.options), key=key, value=value, channel=channel
        )
    except (TypeError, ValueError) as err:
        raise HomeAssistantError(str(err)) from err
    if options != dict(entry.options):
        hass.config_entries.async_update_entry(entry, options=options)


def as_time(value: str) -> time:
    """Normalize Home Assistant persisted wall-clock times."""
    return parse_time(value)
