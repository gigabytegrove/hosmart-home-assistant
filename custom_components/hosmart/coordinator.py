"""Data coordinator and local notification listener for Hosmart."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import json
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .client import HosmartClient, HosmartError
from .const import DEFAULT_SCAN_INTERVAL, EVENT_ACTIVITY, UDP_PORT

_LOGGER = logging.getLogger(__name__)


class HosmartCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate local receiver reads."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: HosmartClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"Hosmart {entry.entry_id}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.entry = entry
        self.client = client
        self.last_event_change = None
        self._previous_event_tuple: tuple[Any, Any, Any] | None = None

    @property
    def receiver(self) -> dict[str, Any]:
        """Return Receiver params."""
        if not self.data:
            return {}
        params = self.data.get("params") or {}
        receiver = params.get("Receiver") or {}
        return receiver if isinstance(receiver, dict) else {}

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            snapshot = await self.hass.async_add_executor_job(
                self.client.read_snapshot
            )
        except HosmartError as err:
            raise UpdateFailed(str(err)) from err

        params = snapshot.get("params") or {}
        receiver = params.get("Receiver") or {}
        if not isinstance(receiver, dict):
            receiver = {}

        current = (
            receiver.get("Event"),
            receiver.get("Channel"),
            receiver.get("ChannelName"),
        )

        if self._previous_event_tuple is None:
            self._previous_event_tuple = current
        elif current != self._previous_event_tuple:
            previous = self._previous_event_tuple
            self._previous_event_tuple = current
            self.last_event_change = dt_util.utcnow()

            event_data = {
                "entry_id": self.entry.entry_id,
                "host": self.client.host,
                "node_id": snapshot.get("node_id"),
                "name": receiver.get("Name"),
                "event": current[0],
                "channel": current[1],
                "channel_name": current[2],
                "previous_event": previous[0],
                "previous_channel": previous[1],
                "previous_channel_name": previous[2],
            }
            _LOGGER.info(
                "Hosmart activity changed: event=%r channel=%r channel_name=%r",
                current[0],
                current[1],
                current[2],
            )
            self.hass.bus.async_fire(EVENT_ACTIVITY, event_data)

        return snapshot


class HosmartUDPProtocol(asyncio.DatagramProtocol):
    """Listen for Hosmart's local refresh hints on UDP/50001."""

    def __init__(self, coordinator: HosmartCoordinator) -> None:
        self.coordinator = coordinator

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        host_matches = addr[0] == self.coordinator.client.host
        node_matches = False

        try:
            payload = json.loads(data.decode("utf-8"))
            if isinstance(payload, dict):
                node_id = payload.get("nodeId") or payload.get("node_id")
                expected = (
                    self.coordinator.data.get("node_id")
                    if self.coordinator.data
                    else None
                )
                node_matches = bool(node_id and expected and node_id == expected)
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = None

        if not host_matches and not node_matches:
            return

        _LOGGER.debug("Hosmart UDP refresh hint from %s: %r", addr, payload)
        self.coordinator.hass.async_create_task(
            self.coordinator.async_request_refresh()
        )


async def async_start_udp_listener(
    hass: HomeAssistant,
    coordinator: HosmartCoordinator,
):
    """Start UDP notification listener if the port is available."""
    loop = hass.loop
    try:
        transport, _ = await loop.create_datagram_endpoint(
            lambda: HosmartUDPProtocol(coordinator),
            local_addr=("0.0.0.0", UDP_PORT),
            allow_broadcast=True,
        )
    except OSError as err:
        _LOGGER.warning(
            "Could not bind Hosmart UDP/%s listener (%s); polling remains active",
            UDP_PORT,
            err,
        )
        return None

    _LOGGER.info("Hosmart local notification listener active on UDP/%s", UDP_PORT)
    return transport
