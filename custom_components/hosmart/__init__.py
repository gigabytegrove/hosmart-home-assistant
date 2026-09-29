"""Hosmart Home Assistant integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .client import HosmartClient
from .const import CONF_POP, DOMAIN, PLATFORMS
from .coordinator import HosmartCoordinator, async_start_udp_listener


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hosmart from a config entry."""
    client = HosmartClient(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_POP],
    )
    coordinator = HosmartCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    udp_transport = await async_start_udp_listener(hass, coordinator)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "udp_transport": udp_transport,
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
    await hass.async_add_executor_job(coordinator.client.close)

    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)

    return True
