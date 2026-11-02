"""Pure, timezone-local scheduling rules for receiver quiet hours."""

from __future__ import annotations

from datetime import datetime, time


def parse_time(value: str) -> time:
    """Parse a Home Assistant time selector value; reject offsets and invalid times."""
    parsed = time.fromisoformat(value)
    if parsed.tzinfo is not None:
        raise ValueError("Quiet-hours times must be local wall-clock times")
    return parsed.replace(microsecond=0)


def is_quiet_now(now: datetime, start: str, end: str) -> bool:
    """Whether local wall-clock now belongs to [start, end).

    Equal start/end times are invalid rather than silently disabling a schedule
    or imposing a 24-hour shutdown.
    """
    begin = parse_time(start)
    finish = parse_time(end)
    if begin == finish:
        raise ValueError("Quiet-hours start and end must differ")

    current = now.timetz().replace(tzinfo=None)
    if begin < finish:
        return begin <= current < finish
    return current >= begin or current < finish


def plan_channel_quiet(
    now: datetime,
    *,
    receiver_enabled: bool,
    receiver_start: str,
    receiver_end: str,
    receiver_action: str,
    channels: dict[str, dict[str, str]],
) -> tuple[str | None, tuple[int, ...]]:
    """Return the receiver-wide action and zone numbers to disarm.

    Precedence: an individual channel can inherit receiver quiet hours,
    remain active, or use a completely independent schedule. A receiver-wide
    volume/power action is only safe when *all four* channels are quiet and
    receiver-wide quiet hours are enabled. This prevents a protected channel
    (such as a driveway) from being silenced by the master setting.

    Zone disarming is NOT audio-only muting: it may also suppress alarms and
    device-to-cloud notices. The caller must explain this distinction.
    """
    if receiver_action not in ("mute", "power_off"):
        raise ValueError("Unknown receiver-wide quiet action")
    default_quiet = receiver_enabled and is_quiet_now(
        now, receiver_start, receiver_end
    )
    quiet: list[int] = []
    for index in range(1, 5):
        rule = channels.get(str(index), {})
        if not isinstance(rule, dict):
            raise ValueError(f"Invalid channel {index} settings")
        mode = rule.get("mode", "inherit")
        if mode == "inherit":
            active = default_quiet
        elif mode == "always_active":
            active = False
        elif mode == "custom":
            active = is_quiet_now(
                now,
                rule.get("start", "22:00:00"),
                rule.get("end", "07:00:00"),
            )
        else:
            raise ValueError(f"Invalid channel {index} mode: {mode}")
        if active:
            quiet.append(index)

    if receiver_enabled and len(quiet) == 4:
        return receiver_action, ()
    return None, tuple(quiet)
