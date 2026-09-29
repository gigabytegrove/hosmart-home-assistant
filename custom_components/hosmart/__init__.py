"""Ho-Smart Home Assistant integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .client import HosmartClient
from .const import (
    CONF_MODE,
    CONF_NODE_ID,
    CONF_POP,
    CONF_USER_ID,
    DOMAIN,
    MODE_CLOUD,
    MODE_HYBRID,
    MODE_LOCAL,
    PLATFORMS,
)
from .coordinator import HosmartCoordinator, async_start_udp_listener
from .debug import HosmartDebugRecorder

_LOGGER = logging.getLogger(__name__)


def _mode(entry: ConfigEntry) -> str:
    return entry.options.get(
        CONF_MODE,
        MODE_LOCAL if not entry.data.get(CONF_USER_ID) else MODE_HYBRID,
    )


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when the Local / Cloud / Hybrid option changes."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ho-Smart from a config entry."""
    mode = _mode(entry)
    local_enabled = mode in (MODE_LOCAL, MODE_HYBRID)

    recorder = HosmartDebugRecorder(hass, entry.entry_id)
    await recorder.async_record(
        "integration_start",
        entry_id=entry.entry_id,
        mode=mode,
        host=entry.data.get(CONF_HOST),
        port=entry.data.get(CONF_PORT),
    )

    client: HosmartClient | None = None
    if local_enabled:
        pop = entry.data.get(CONF_POP)
        host = entry.data.get(CONF_HOST)
        port = entry.data.get(CONF_PORT)

        if not pop or not host or not port:
            _LOGGER.error(
                "Ho-Smart %s requires local host/port/POP but config data is incomplete",
                mode,
            )
            return False

        client = HosmartClient(
            str(host),
            int(port),
            str(pop),
        )

    coordinator = HosmartCoordinator(hass, entry, client, recorder)
    await coordinator.async_config_entry_first_refresh()

    # Entries created before v0.2.0 stored the node id only as unique_id.
    # Backfill it into entry data after a successful local refresh so later
    # cloud-mode configuration has a stable explicit node identifier.
    if not entry.data.get(CONF_NODE_ID) and coordinator.node_id:
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_NODE_ID: coordinator.node_id,
            },
        )

    udp_transport = await async_start_udp_listener(hass, coordinator)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "udp_transport": udp_transport,
        "recorder": recorder,
    }

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Ho-Smart config entry."""
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
        mode=coordinator.mode,
        poll_count=coordinator.poll_count,
        change_count=coordinator.change_count,
        udp_packet_count=coordinator.udp_packet_count,
        cloud_alert_count=coordinator.cloud_alert_count,
    )

    if coordinator.client is not None:
        await hass.async_add_executor_job(coordinator.client.close)

    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)

    return True
