"""Ho-Smart / eMACROS Home Assistant integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers import entity_registry as er

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
from .quiet_hours import HosmartQuietHours
from .hacs_channel import (
    align_receiver_preferences,
    async_apply_release_channel,
    selected_channel,
)

_LOGGER = logging.getLogger(__name__)


def _mode(entry: ConfigEntry) -> str:
    return entry.options.get(
        CONF_MODE,
        MODE_LOCAL if not entry.data.get(CONF_USER_ID) else MODE_HYBRID,
    )


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply schedule edits in place; reconnect only for actual connection changes."""
    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if runtime is None:
        return
    signature = (
        _mode(entry),
        entry.data.get(CONF_HOST),
        entry.data.get(CONF_PORT),
        entry.data.get(CONF_POP),
        entry.data.get(CONF_USER_ID),
        entry.data.get(CONF_NODE_ID),
    )
    if signature != runtime["connection_signature"]:
        await hass.config_entries.async_reload(entry.entry_id)
        return
    quiet: HosmartQuietHours | None = runtime.get("quiet")
    if quiet is not None:
        await quiet.async_options_updated()
    align_receiver_preferences(hass, entry)
    await _async_sync_channel(hass, entry)
    runtime["coordinator"].async_update_listeners()


async def _async_sync_channel(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reconcile HACS/Marketplace's actual prerelease switch with our choice."""
    channel = selected_channel(entry)
    if channel is None:
        return  # Pre-channel installations retain their previous HACS preference.
    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if runtime is None:
        return
    coordinator: HosmartCoordinator = runtime["coordinator"]
    try:
        status = await async_apply_release_channel(hass, channel)
    except Exception as err:
        _LOGGER.warning("Ho-Smart channel sync failed; retrying: %s", err)
        status = "sync_error"
    if coordinator.release_channel_status != status:
        coordinator.release_channel_status = status
        coordinator.async_update_listeners()
        if status not in ("main_tracking", "dev_tracking"):
            _LOGGER.warning(
                "Ho-Smart %s channel %s pending: %s; will retry",
                entry.title, channel, status,
            )
        else:
            _LOGGER.info("Ho-Smart update channel now tracked by HACS: %s", channel)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ho-Smart / eMACROS from a config entry."""
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
                "Ho-Smart / eMACROS %s requires local host/port/POP but config data is incomplete",
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
        "connection_signature": (
            mode,
            entry.data.get(CONF_HOST),
            entry.data.get(CONF_PORT),
            entry.data.get(CONF_POP),
            entry.data.get(CONF_USER_ID),
            entry.data.get(CONF_NODE_ID),
        ),
    }

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    quiet = HosmartQuietHours(hass, entry, coordinator)
    hass.data[DOMAIN][entry.entry_id]["quiet"] = quiet
    await quiet.async_start()
    _hide_legacy_schedule_entities(hass, entry, coordinator)
    align_receiver_preferences(hass, entry)
    # A HACS Pre-release switch may not exist until Marketplace loads, or
    # until its disabled-by-default registry entry is enabled. Polling is
    # idempotent and keeps this preference effective after HA restarts.
    async def _periodic_channel_sync(_now) -> None:
        await _async_sync_channel(hass, entry)

    def _on_channel_interval(now) -> None:
        hass.async_create_task(
            _periodic_channel_sync(now),
            f"Ho-Smart channel sync {entry.entry_id}",
        )

    unsub = async_track_time_interval(
        hass, _on_channel_interval, timedelta(seconds=60)
    )
    hass.data[DOMAIN][entry.entry_id]["channel_sync_unsub"] = unsub
    await _async_sync_channel(hass, entry)
    return True


def _hide_legacy_schedule_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: HosmartCoordinator,
) -> None:
    """One-time reversible UI migration: hide old flat schedule controls.

    Their registry IDs and automation access remain intact. The edit form
    replaces the old flat list. Do not hide again if the user later chooses
    to make one visible manually.
    """
    key = "_grouped_schedule_ui_migrated"
    if entry.options.get(key):
        return
    registry = er.async_get(hass)
    node_id = coordinator.node_id or entry.entry_id
    ids = [
        ("time", "receiver_quiet_start"),
        ("time", "receiver_quiet_end"),
        ("select", "receiver_quiet_action"),
    ]
    for index in range(1, 5):
        ids.extend(
            (
                ("time", f"channel_{index}_quiet_start"),
                ("time", f"channel_{index}_quiet_end"),
                ("select", f"channel_{index}_quiet_mode"),
            )
        )
    for domain, name in ids:
        entity_id = registry.async_get_entity_id(
            domain, DOMAIN, f"{node_id}_{name}"
        )
        if entity_id is None:
            continue
        item = registry.async_get(entity_id)
        if (
            item is not None
            and item.config_entry_id == entry.entry_id
            and item.hidden_by is None
        ):
            registry.async_update_entity(
                entity_id, hidden_by=er.RegistryEntryHider.INTEGRATION
            )
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, key: True}
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Ho-Smart / eMACROS config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unloaded:
        return False

    runtime: dict[str, Any] = hass.data[DOMAIN].pop(entry.entry_id)
    unsub = runtime.get("channel_sync_unsub")
    if unsub is not None:
        unsub()
    transport = runtime.get("udp_transport")
    if transport is not None:
        transport.close()

    coordinator: HosmartCoordinator = runtime["coordinator"]
    quiet: HosmartQuietHours | None = runtime.get("quiet")
    if quiet is not None:
        await quiet.async_stop()
    coordinator.cancel_alarm_timer()
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
