"""Diagnostics support for Hosmart."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_POP, DOMAIN
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

    tail = await hass.async_add_executor_job(recorder.tail_sync, 2000)

    return redact(
        {
            "entry": entry_data,
            "available": coordinator.last_update_success,
            "node_id": (
                coordinator.data.get("node_id")
                if coordinator.data
                else None
            ),
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
            "last_poll_time": coordinator.last_poll_time,
            "last_event_change": coordinator.last_event_change,
            "last_activity_time": coordinator.last_activity_time,
            "last_activity": coordinator.last_activity,
            "last_udp_time": coordinator.last_udp_time,
            "last_udp_source": coordinator.last_udp_source,
            "debug_log_path": str(recorder.path),
            "debug_log_tail": tail,
        }
    )
