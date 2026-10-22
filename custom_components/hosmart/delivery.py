"""Pure timing and channel rules for Ho-Smart alarm delivery."""

from __future__ import annotations

from datetime import datetime, timedelta

MAX_LIVE_NOTICE_AGE_SECONDS = 120
CLOUD_RECOVERY_OVERLAP = timedelta(minutes=3)
CLOUD_RECOVERY_MAX_LOOKBACK = timedelta(days=7)
CLOUD_INITIAL_LOOKBACK = timedelta(days=30)
CLOCK_SKEW_ALLOWANCE_SECONDS = 5


def cloud_query_start(now: datetime, last_success: datetime | None) -> datetime:
    """Resume from last successful check, with a bounded overlap."""
    if last_success is None:
        return now - CLOUD_INITIAL_LOOKBACK
    return max(last_success - CLOUD_RECOVERY_OVERLAP, now - CLOUD_RECOVERY_MAX_LOOKBACK)


def is_live_notice(activity_time: datetime, observed_at: datetime) -> bool:
    """Only near-real-time notices may produce live motion events."""
    age = (observed_at - activity_time).total_seconds()
    return -CLOCK_SKEW_ALLOWANCE_SECONDS <= age <= MAX_LIVE_NOTICE_AGE_SECONDS


def is_driveway_channel(channel: object, channel_name: object, driveway_name: object = "Driveway") -> bool:
    """Only channel one belongs to the driveway motion entity."""
    if channel not in (None, "", 0, "0"):
        try:
            return int(channel) == 1
        except (ValueError, TypeError):
            return False
    return bool(
        channel_name and driveway_name
        and str(channel_name).strip().casefold() == str(driveway_name).strip().casefold()
    )
