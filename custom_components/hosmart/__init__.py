"""Hosmart Home Assistant integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .client import HosmartClient
from .const import CONF_POP, DOMAIN, PLATFORMS
from .coordinator import HosmartCoordinator, async_start_udp_listener
from .debug import HosmartDebugRecorder


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hosmart from a config entry."""
    recorder = HosmartDebugRecorder(hass, entry.entry_id)
    await recorder.async_record(
        "integration_start",
        entry_id=entry.entry_id,
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        poll_interval_seconds=0.25,
    )

    client = HosmartClient(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_POP],
    )
    coordinator = HosmartCoordinator(hass, entry, client, recorder)
    await coordinator.async_config_entry_first_refresh()

    udp_transport = await async_start_udp_listener(hass, coordinator)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "udp_transport": udp_transport,
        "recorder": recorder,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Hosmart config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unloaded:
        return False

    runtime: dict[str, Any] = hass.data[DOMAIN].pop(entry.entry_id)
    transport = runtime.get("udp_transport")
    if transport is not None:
        transport.close()

    coordinator: HosmartCoordinator = runtime["coordinator"]
    recorder: HosmartDebugRecorder = runtime["recorder"]
    await recorder.async_record(
        "integration_stop",
        poll_count=coordinator.poll_count,
        change_count=coordinator.change_count,
        udp_packet_count=coordinator.udp_packet_count,
    )
    await hass.async_add_executor_job(coordinator.client.close)

    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)

    return True
