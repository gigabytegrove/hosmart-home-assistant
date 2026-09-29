"""Data coordinator and local notification listener for Hosmart."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import timedelta
import json
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .client import HosmartClient, HosmartError
from .const import (
    DEFAULT_SCAN_INTERVAL,
    EVENT_ACTIVITY,
    EVENT_UDP_PACKET,
    UDP_PORT,
)
from .debug import HosmartDebugRecorder

_LOGGER = logging.getLogger(__name__)


def _dict_changes(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Return field-level changes without assuming which fields matter."""
    if previous is None:
        return {}

    changes: dict[str, dict[str, Any]] = {}
    for key in sorted(set(previous) | set(current)):
        old = previous.get(key)
        new = current.get(key)
        if old != new:
            changes[key] = {"previous": old, "current": new}
    return changes


class HosmartCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate local receiver reads and preserve complete field-test data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: HosmartClient,
        recorder: HosmartDebugRecorder,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"Hosmart {entry.entry_id}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.entry = entry
        self.client = client
        self.recorder = recorder

        self.poll_count = 0
        self.change_count = 0
        self.udp_packet_count = 0

        self.last_poll_time = None
        self.last_event_change = None
        self.last_activity_time = None
        self.last_activity: dict[str, Any] | None = None
        self.last_udp_time = None
        self.last_udp_source: str | None = None

        self._baseline_event_tuple: tuple[Any, Any, Any] | None = None
        self._previous_event_tuple: tuple[Any, Any, Any] | None = None
        self._previous_receiver: dict[str, Any] | None = None
        self._previous_params: dict[str, Any] | None = None
        self._previous_config: dict[str, Any] | None = None

    @property
    def receiver(self) -> dict[str, Any]:
        """Return Receiver params."""
        if not self.data:
            return {}
        params = self.data.get("params") or {}
        receiver = params.get("Receiver") or {}
        return receiver if isinstance(receiver, dict) else {}

    async def _async_update_data(self) -> dict[str, Any]:
        self.poll_count += 1
        poll_number = self.poll_count
        started = time.monotonic()
        started_at = dt_util.utcnow()

        try:
            snapshot = await self.hass.async_add_executor_job(
                self.client.read_snapshot
            )
        except HosmartError as err:
            elapsed_ms = round((time.monotonic() - started) * 1000, 3)
            await self.recorder.async_record(
                "poll_error",
                poll=poll_number,
                started_at=started_at,
                duration_ms=elapsed_ms,
                error_type=type(err).__name__,
                error=str(err),
            )
            raise UpdateFailed(str(err)) from err
        except Exception as err:
            elapsed_ms = round((time.monotonic() - started) * 1000, 3)
            await self.recorder.async_record(
                "poll_unexpected_error",
                poll=poll_number,
                started_at=started_at,
                duration_ms=elapsed_ms,
                error_type=type(err).__name__,
                error=str(err),
            )
            raise

        elapsed_ms = round((time.monotonic() - started) * 1000, 3)
        now = dt_util.utcnow()
        self.last_poll_time = now

        params = snapshot.get("params") or {}
        receiver = params.get("Receiver") or {}
        if not isinstance(receiver, dict):
            receiver = {}

        # DEVELOPMENT CAPTURE: write every successful state sample, not just
        # changes. The large static config is journaled on first sight and only
        # again if it actually changes; every poll still records the complete
        # live params object. The recorder recursively redacts POP/credentials.
        config = snapshot.get("config") or {}
        if config != self._previous_config:
            await self.recorder.async_record(
                "config_snapshot",
                poll=poll_number,
                node_id=snapshot.get("node_id"),
                model=snapshot.get("model"),
                fw_version=snapshot.get("fw_version"),
                platform=snapshot.get("platform"),
                config=config,
            )
            self._previous_config = deepcopy(config)

        await self.recorder.async_record(
            "poll_snapshot",
            poll=poll_number,
            started_at=started_at,
            completed_at=now,
            duration_ms=elapsed_ms,
            host=self.client.host,
            port=self.client.port,
            node_id=snapshot.get("node_id"),
            model=snapshot.get("model"),
            fw_version=snapshot.get("fw_version"),
            platform=snapshot.get("platform"),
            params=params,
        )

        if self._previous_params is not None and params != self._previous_params:
            await self.recorder.async_record(
                "params_changed",
                poll=poll_number,
                previous=self._previous_params,
                current=params,
            )

        changes = _dict_changes(self._previous_receiver, receiver)
        if changes:
            self.change_count += 1
            await self.recorder.async_record(
                "receiver_fields_changed",
                poll=poll_number,
                change_number=self.change_count,
                changes=changes,
                full_receiver=receiver,
            )

        current = (
            receiver.get("Event"),
            receiver.get("Channel"),
            receiver.get("ChannelName"),
        )

        if self._previous_event_tuple is None:
            self._previous_event_tuple = current
            self._baseline_event_tuple = current
            await self.recorder.async_record(
                "event_baseline",
                event=current[0],
                channel=current[1],
                channel_name=current[2],
            )
        elif current != self._previous_event_tuple:
            previous = self._previous_event_tuple
            self._previous_event_tuple = current
            self.last_event_change = now

            # Preserve the most recent transition away from the startup/idle
            # tuple so a short event remains visible after the receiver clears.
            if current != self._baseline_event_tuple:
                self.last_activity_time = now
                self.last_activity = {
                    "event": current[0],
                    "channel": current[1],
                    "channel_name": current[2],
                }

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
                "baseline_event": (
                    self._baseline_event_tuple[0]
                    if self._baseline_event_tuple is not None
                    else None
                ),
                "baseline_channel": (
                    self._baseline_event_tuple[1]
                    if self._baseline_event_tuple is not None
                    else None
                ),
                "baseline_channel_name": (
                    self._baseline_event_tuple[2]
                    if self._baseline_event_tuple is not None
                    else None
                ),
            }

            await self.recorder.async_record(
                "event_tuple_changed",
                **event_data,
                poll=poll_number,
            )

            _LOGGER.info(
                "Hosmart activity changed: event=%r channel=%r channel_name=%r",
                current[0],
                current[1],
                current[2],
            )
            self.hass.bus.async_fire(EVENT_ACTIVITY, event_data)

        self._previous_receiver = deepcopy(receiver)
        self._previous_params = deepcopy(params)
        return snapshot


class HosmartUDPProtocol(asyncio.DatagramProtocol):
    """Capture every UDP/50001 datagram and refresh on receiver matches."""

    def __init__(self, coordinator: HosmartCoordinator) -> None:
        self.coordinator = coordinator

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.coordinator.udp_packet_count += 1
        self.coordinator.last_udp_time = dt_util.utcnow()
        self.coordinator.last_udp_source = f"{addr[0]}:{addr[1]}"

        payload: Any = None
        text: str | None = None
        try:
            text = data.decode("utf-8")
            payload = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass

        expected_node_id = (
            self.coordinator.data.get("node_id")
            if self.coordinator.data
            else None
        )

        node_id = None
        if isinstance(payload, dict):
            node_id = payload.get("nodeId") or payload.get("node_id")

        host_matches = addr[0] == self.coordinator.client.host
        node_matches = bool(
            node_id and expected_node_id and node_id == expected_node_id
        )
        matched = host_matches or node_matches

        record = {
            "packet_number": self.coordinator.udp_packet_count,
            "source_ip": addr[0],
            "source_port": addr[1],
            "length": len(data),
            "raw_hex": data.hex(),
            "raw_text": text,
            "json": payload,
            "expected_node_id": expected_node_id,
            "host_matches": host_matches,
            "node_matches": node_matches,
            "matched_receiver": matched,
        }

        # Capture BEFORE filtering so an unexpected packet format/source is
        # still available after a one-off field test.
        self.coordinator.hass.async_create_task(
            self.coordinator.recorder.async_record(
                "udp_50001_datagram",
                **record,
            )
        )

        self.coordinator.hass.bus.async_fire(EVENT_UDP_PACKET, record)

        if not matched:
            return

        self.coordinator.hass.async_create_task(
            self.coordinator.async_request_refresh()
        )


async def async_start_udp_listener(
    hass: HomeAssistant,
    coordinator: HosmartCoordinator,
):
    """Start UDP notification listener if the port is available."""
    loop = asyncio.get_running_loop()
    try:
        transport, _ = await loop.create_datagram_endpoint(
            lambda: HosmartUDPProtocol(coordinator),
            local_addr=("0.0.0.0", UDP_PORT),
            allow_broadcast=True,
        )
    except OSError as err:
        await coordinator.recorder.async_record(
            "udp_listener_error",
            port=UDP_PORT,
            error_type=type(err).__name__,
            error=str(err),
        )
        _LOGGER.warning(
            "Could not bind Hosmart UDP/%s listener (%s); polling remains active",
            UDP_PORT,
            err,
        )
        return None

    await coordinator.recorder.async_record(
        "udp_listener_started",
        bind="0.0.0.0",
        port=UDP_PORT,
    )
    _LOGGER.info("Hosmart local notification listener active on UDP/%s", UDP_PORT)
    return transport
