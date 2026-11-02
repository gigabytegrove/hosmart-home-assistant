"""Declarative receiver and channel quiet-hours commands.

Tone-only muting MUST NOT fall back to disarming, powering off or changing
shared receiver volume. Unsupported tone mute is explicitly reported instead.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .night_schedule import is_quiet_now

ACTION_ARM = "arm"
ACTION_DISARM = "disarm"
ACTION_MUTE_TONE = "mute_tone"
ACTION_MUTE_ALL = "mute"
ACTION_POWER_OFF = "power_off"
CHANNEL_ACTIONS = (ACTION_ARM, ACTION_DISARM, ACTION_MUTE_TONE)
DEFAULT_ACTIONS = CHANNEL_ACTIONS + (ACTION_MUTE_ALL, ACTION_POWER_OFF)


def build_schedule_plan(
    now: datetime,
    *,
    enabled: bool,
    start: str,
    end: str,
    default_action: str,
    channels: dict[str, dict[str, Any]],
) -> tuple[dict[str, int | bool], dict[int, str]]:
    """Plan safe writes and per-channel statuses for the current wall clock.

    Inherited schedule action is the selected Default action. 'arm' / 'disarm'
    affect zone arming, while mute_tone requires an independently supported,
    vendor-confirmed tone-mute API (none is known on verified HS006W).
    Legacy global mute and power-off only act if *all* channels are scheduled
    for that same global action, so a protected channel cannot be silenced.
    """
    if default_action not in DEFAULT_ACTIONS:
        raise ValueError("Invalid Default action")
    global_active = enabled and is_quiet_now(now, start, end)
    effective: dict[int, str] = {}
    statuses: dict[int, str] = {}
    desired: dict[str, int | bool] = {}

    for index in range(1, 5):
        rule = channels.get(str(index), {})
        if not isinstance(rule, dict):
            raise ValueError(f"Invalid Ch. {index} settings")
        mode = rule.get("mode", "inherit")
        if mode == "always_active":
            statuses[index] = "protected"
            continue
        if mode == "inherit":
            active = global_active
            action = default_action
        elif mode == "custom":
            active = is_quiet_now(
                now, rule.get("start", "22:00:00"),
                rule.get("end", "07:00:00")
            )
            action = rule.get("action", ACTION_DISARM)
        else:
            raise ValueError(f"Unknown Ch. {index} mode")
        if not active:
            statuses[index] = "active"
            continue
        if action not in DEFAULT_ACTIONS:
            raise ValueError(f"Invalid Ch. {index} action")
        effective[index] = action
        if action == ACTION_ARM:
            desired[f"ZoneAlarming{index}"] = True
            statuses[index] = "scheduled_arm"
        elif action == ACTION_DISARM:
            desired[f"ZoneAlarming{index}"] = False
            statuses[index] = "scheduled_disarm"
        elif action == ACTION_MUTE_TONE:
            # No verified independent tone-mute write exists for the HS006W.
            # Crucially, do not silently replace muting with zone disarming.
            statuses[index] = "unsupported_tone_mute"
        else:
            statuses[index] = "unsupported_global_mute"

    for global_action, field, value in (
        (ACTION_MUTE_ALL, "Volume", 0),
        (ACTION_POWER_OFF, "Power", False),
    ):
        if len(effective) == 4 and all(
            action == global_action for action in effective.values()
        ):
            desired[field] = value
            for index in range(1, 5):
                statuses[index] = "muted_all" if field == "Volume" else "powered_off"
            break

    return desired, statuses
