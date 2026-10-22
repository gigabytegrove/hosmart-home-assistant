"""Pure timing and channel rules for Ho-Smart alarm delivery."""

from __future__ import annotations

from datetime import datetime, timedelta

MAX_LIVE_NOTICE_AGE_SECONDS = 120
CLOUD_RECOVERY_OVERLAP = timedelta(hours=1)
CLOUD_RECOVERY_MAX_LOOKBACK = timedelta(days=7)
CLOUD_INITIAL_LOOKBACK = timedelta(days=30)
CLOCK_SKEW_ALLOWANCE_SECONDS = 5


def cloud_query_start(now: datetime, last_success: datetime | None) -> datetime:
    """Resume from last successful check, with a bounded overlap."""
    if last_success is None:
        return now - CLOUD_INITIAL_LOOKBACK
    return max(min(last_success, now) - CLOUD_RECOVERY_OVERLAP, now - CLOUD_RECOVERY_MAX_LOOKBACK)


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


def cloud_history_window(
    now: datetime, last_reconcile: datetime | None, initialized: bool
) -> tuple[datetime, bool]:
    """Return bounded query start and whether full recovery is required.

    Live polls use a narrow window; full reconciliation runs at least once
    a minute and resumes from the previous successful FULL reconciliation.
    """
    reconcile = (
        not initialized
        or last_reconcile is None
        or (now - last_reconcile).total_seconds() >= 60
    )
    if reconcile:
        return cloud_query_start(now, last_reconcile), True
    return now - timedelta(minutes=3), False
