"""Diagnostics support for Ho-Smart."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_POP, CONF_USER_ID, DOMAIN
from .debug import redact


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """Return redacted integration diagnostics plus recent capture records."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    coordinator = runtime["coordinator"]
    recorder = runtime["recorder"]

    entry_data = dict(entry.data)
    if CONF_POP in entry_data:
        entry_data[CONF_POP] = "<redacted>"
    if CONF_USER_ID in entry_data:
        entry_data[CONF_USER_ID] = "<redacted>"

    sample_tail = await hass.async_add_executor_job(recorder.tail_sync, 1000)
    event_tail = await hass.async_add_executor_job(recorder.event_tail_sync, 5000)

    return redact(
        {
            "entry": entry_data,
            "options": dict(entry.options),
            "available": coordinator.last_update_success,
            "mode": coordinator.mode,
            "local_enabled": coordinator.local_enabled,
            "local_available": coordinator.local_available,
            "cloud_enabled": coordinator.cloud_enabled,
            "cloud_available": coordinator.cloud_available,
            "node_id": coordinator.node_id,
            "model": (
                coordinator.data.get("model")
                if coordinator.data
                else None
            ),
            "firmware": (
                coordinator.data.get("fw_version")
                if coordinator.data
                else None
            ),
            "current_params": (
                coordinator.data.get("params")
                if coordinator.data
                else None
            ),
            "poll_count": coordinator.poll_count,
            "change_count": coordinator.change_count,
            "udp_packet_count": coordinator.udp_packet_count,
            "cloud_alert_count": coordinator.cloud_alert_count,
            "cloud_error_count": coordinator.cloud_error_count,
            "last_poll_time": coordinator.last_poll_time,
            "last_event_change": coordinator.last_event_change,
            "last_activity_time": coordinator.last_activity_time,
            "last_activity": coordinator.last_activity,
            "last_activity_source": coordinator.last_activity_source,
            "last_udp_time": coordinator.last_udp_time,
            "last_udp_source": coordinator.last_udp_source,
            "last_cloud_check_time": coordinator.last_cloud_check_time,
            "last_cloud_error": coordinator.last_cloud_error,
            "sample_log_path": str(recorder.path),
            "event_journal_path": str(recorder.event_path),
            "recent_sample_records": sample_tail,
            "event_journal": event_tail,
        }
    )
