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
