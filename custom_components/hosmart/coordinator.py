"""Data coordinator and local notification listener for Ho-Smart."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .client import HosmartClient, HosmartError
from .cloud import (
    HosmartCloudError,
    history_record_key,
    parse_activity,
    query_history,
)
from .const import (
    CLOUD_SCAN_INTERVAL,
    CONF_CHANNEL_NAMES,
    CONF_MODE,
    CONF_NODE_ID,
    CONF_USER_ID,
    DEFAULT_SCAN_INTERVAL,
    EVENT_ACTIVITY,
    EVENT_ALERT,
    EVENT_UDP_PACKET,
    MODE_CLOUD,
    MODE_HYBRID,
    MODE_LOCAL,
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
    """Coordinate local receiver state and Ho-Smart cloud alarm history."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: HosmartClient | None,
        recorder: HosmartDebugRecorder,
    ) -> None:
        self.mode = entry.options.get(
            CONF_MODE,
            MODE_LOCAL if not entry.data.get(CONF_USER_ID) else MODE_HYBRID,
        )
        self.local_enabled = self.mode in (MODE_LOCAL, MODE_HYBRID)
        self.cloud_enabled = self.mode in (MODE_CLOUD, MODE_HYBRID) and bool(
            entry.data.get(CONF_USER_ID)
        )

        super().__init__(
            hass,
            _LOGGER,
            name=f"Ho-Smart {entry.entry_id}",
            update_interval=timedelta(
                seconds=(
                    CLOUD_SCAN_INTERVAL if self.cloud_enabled else DEFAULT_SCAN_INTERVAL
                )
            ),
        )

        self.entry = entry
        self.client = client
        self.recorder = recorder

        self.local_available = not self.local_enabled
        self.cloud_available = not self.cloud_enabled

        self.poll_count = 0
        self.change_count = 0
        self.udp_packet_count = 0
        self.cloud_alert_count = 0
        self.cloud_error_count = 0

        self.last_poll_time: datetime | None = None
        self.last_event_change: datetime | None = None
        self.last_activity_time: datetime | None = None
        self.last_activity: dict[str, Any] | None = None
        self.last_activity_source: str | None = None
        self.last_udp_time: datetime | None = None
        self.last_udp_source: str | None = None
        self.last_cloud_check_time: datetime | None = None
        self.last_cloud_error: str | None = None

        self._baseline_event_tuple: tuple[Any, Any, Any] | None = None
        self._previous_event_tuple: tuple[Any, Any, Any] | None = None
        self._previous_receiver: dict[str, Any] | None = None
        self._previous_params: dict[str, Any] | None = None
        self._previous_config: dict[str, Any] | None = None

        self._local_snapshot: dict[str, Any] | None = None
        self._next_local_poll = 0.0

        self._cloud_initialized = False
        self._seen_cloud_keys: set[str] = set()

    @property
    def receiver(self) -> dict[str, Any]:
        """Return Receiver params."""
        snapshot = self._local_snapshot or self.data or {}
        params = snapshot.get("params") or {}
        receiver = params.get("Receiver") or {}
        return receiver if isinstance(receiver, dict) else {}

    @property
    def node_id(self) -> str | None:
        """Return the configured/observed node id."""
        if self._local_snapshot and self._local_snapshot.get("node_id"):
            return str(self._local_snapshot["node_id"])
        node_id = self.entry.data.get(CONF_NODE_ID) or self.entry.unique_id
        return str(node_id) if node_id else None

    def request_local_refresh(self) -> None:
        """Force the next coordinator cycle to include a local read."""
        self._next_local_poll = 0.0
        self.hass.async_create_task(self.async_request_refresh())

    def _channel_number_for_name(self, channel_name: Any) -> Any:
        """Map a cloud channel name back to the receiver's numbered channel."""
        if channel_name in (None, ""):
            return None

        name = str(channel_name).casefold()

        for index in range(1, 5):
            local_name = self.receiver.get(f"Channel{index}Name")
            if local_name is not None and str(local_name).casefold() == name:
                return index

        configured = self.entry.data.get(CONF_CHANNEL_NAMES) or {}
        if isinstance(configured, dict):
            for index, configured_name in configured.items():
                if str(configured_name).casefold() == name:
                    try:
                        return int(index)
                    except (TypeError, ValueError):
                        return index

        return None

    async def _async_set_activity(
        self,
        *,
        event: Any,
        channel: Any,
        channel_name: Any,
        activity_time: datetime,
        source: str,
        message: str | None = None,
        historical: bool = False,
        record_key: str | None = None,
    ) -> None:
        """Update persistent activity state and optionally fire HA events."""
        if channel in (None, "", 0, "0") and channel_name:
            mapped = self._channel_number_for_name(channel_name)
            if mapped is not None:
                channel = mapped

        self.last_activity_time = activity_time
        self.last_event_change = activity_time
        self.last_activity_source = source
        self.last_activity = {
            "event": event,
            "channel": channel,
            "channel_name": channel_name,
            "source": source,
            "message": message,
        }

        activity_data = {
            "entry_id": self.entry.entry_id,
            "node_id": self.node_id,
            "name": self.receiver.get("Name") or self.entry.title,
            "event": event,
            "channel": channel,
            "channel_name": channel_name,
            "activity_time": activity_time.isoformat(),
            "source": source,
            "message": message,
            "record_key": record_key,
        }

        await self.recorder.async_record(
            "activity",
            historical=historical,
            **activity_data,
        )

        if historical:
            return

        self.hass.bus.async_fire(EVENT_ACTIVITY, activity_data)

        if str(event or "").casefold() == "alarm":
            self.hass.bus.async_fire(EVENT_ALERT, activity_data)

    async def _async_process_local_snapshot(
        self,
        snapshot: dict[str, Any],
        *,
        poll_number: int,
        started_at: datetime,
        elapsed_ms: float,
    ) -> None:
        """Capture and process one live local state read."""
        now = dt_util.utcnow()
        self.last_poll_time = now
        self.local_available = True
        self._local_snapshot = snapshot

        params = snapshot.get("params") or {}
        receiver = params.get("Receiver") or {}
        if not isinstance(receiver, dict):
            receiver = {}

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
            host=self.client.host if self.client else None,
            port=self.client.port if self.client else None,
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

            event_data = {
                "entry_id": self.entry.entry_id,
                "host": self.client.host if self.client else None,
                "node_id": snapshot.get("node_id"),
                "name": receiver.get("Name"),
                "event": current[0],
                "channel": current[1],
                "channel_name": current[2],
                "previous_event": previous[0],
                "previous_channel": previous[1],
                "previous_channel_name": previous[2],
            }

            await self.recorder.async_record(
                "event_tuple_changed",
                **event_data,
                poll=poll_number,
            )

            if current != self._baseline_event_tuple:
                await self._async_set_activity(
                    event=current[0],
                    channel=current[1],
                    channel_name=current[2],
                    activity_time=now,
                    source="local",
                )

        self._previous_receiver = deepcopy(receiver)
        self._previous_params = deepcopy(params)

    async def _async_local_update(self) -> None:
        """Perform one local Security1 state read."""
        if not self.local_enabled or self.client is None:
            return

        now_mono = time.monotonic()
        if self._local_snapshot is not None and now_mono < self._next_local_poll:
            return

        self._next_local_poll = now_mono + DEFAULT_SCAN_INTERVAL
        self.poll_count += 1
        poll_number = self.poll_count
        started = time.monotonic()
        started_at = dt_util.utcnow()

        try:
            snapshot = await self.hass.async_add_executor_job(self.client.read_snapshot)
        except Exception as err:
            elapsed_ms = round((time.monotonic() - started) * 1000, 3)
            self.local_available = False
            await self.recorder.async_record(
                "poll_error",
                poll=poll_number,
                started_at=started_at,
                duration_ms=elapsed_ms,
                error_type=type(err).__name__,
                error=str(err),
            )
            if self._local_snapshot is None and not self.cloud_enabled:
                if isinstance(err, HosmartError):
                    raise UpdateFailed(str(err)) from err
                raise UpdateFailed(f"Local receiver read failed: {err}") from err
            return

        elapsed_ms = round((time.monotonic() - started) * 1000, 3)
        await self._async_process_local_snapshot(
            snapshot,
            poll_number=poll_number,
            started_at=started_at,
            elapsed_ms=elapsed_ms,
        )

    async def _async_cloud_update(self) -> None:
        """Load historical baseline once, then watch recent Ho-Smart alarms."""
        if not self.cloud_enabled:
            return

        user_id = self.entry.data.get(CONF_USER_ID)
        node_id = self.node_id
        if not user_id or not node_id:
            return

        now = datetime.now(timezone.utc)
        self.last_cloud_check_time = now

        if not self._cloud_initialized:
            start = now - timedelta(days=30)
        else:
            start = now - timedelta(minutes=3)

        try:
            records = await self.hass.async_add_executor_job(
                query_history,
                str(user_id),
                int(start.timestamp() * 1000),
                int((now + timedelta(seconds=5)).timestamp() * 1000),
            )
        except HosmartCloudError as err:
            self.cloud_available = False
            self.cloud_error_count += 1
            self.last_cloud_error = str(err)
            await self.recorder.async_record(
                "cloud_history_error",
                error_type=type(err).__name__,
                error=str(err),
                initialized=self._cloud_initialized,
            )
            if not self.local_enabled and not self._cloud_initialized:
                raise UpdateFailed(str(err)) from err
            return

        self.cloud_available = True
        self.last_cloud_error = None

        target_records = [
            record
            for record in records
            if str(record.get("node_id") or record.get("nodeId") or "") == str(node_id)
        ]
        target_records.sort(key=lambda record: int(record.get("msgtime") or 0))

        if not self._cloud_initialized:
            for record in target_records:
                self._seen_cloud_keys.add(history_record_key(record))

            latest_activity = None
            latest_record = None
            for record in target_records:
                activity = parse_activity(record)
                if activity is not None:
                    latest_activity = activity
                    latest_record = record

            if latest_activity is not None:
                msgtime_ms = latest_activity.get("msgtime_ms")
                activity_time = (
                    datetime.fromtimestamp(msgtime_ms / 1000, timezone.utc)
                    if msgtime_ms is not None
                    else now
                )
                await self._async_set_activity(
                    event=latest_activity.get("event"),
                    channel=latest_activity.get("channel"),
                    channel_name=latest_activity.get("channel_name"),
                    activity_time=activity_time,
                    source="cloud",
                    message=latest_activity.get("message"),
                    historical=True,
                    record_key=latest_activity.get("record_key"),
                )
                await self.recorder.async_record(
                    "cloud_history_baseline",
                    record=latest_record,
                )

            self._cloud_initialized = True
            await self.recorder.async_record(
                "cloud_history_initialized",
                records=len(target_records),
                latest_activity_time=self.last_activity_time,
            )
            return

        for record in target_records:
            key = history_record_key(record)
            if key in self._seen_cloud_keys:
                continue
            self._seen_cloud_keys.add(key)

            activity = parse_activity(record)
            if activity is None:
                await self.recorder.async_record(
                    "cloud_history_unparsed_record",
                    record=record,
                )
                continue

            msgtime_ms = activity.get("msgtime_ms")
            activity_time = (
                datetime.fromtimestamp(msgtime_ms / 1000, timezone.utc)
                if msgtime_ms is not None
                else now
            )

            self.cloud_alert_count += 1
            await self.recorder.async_record(
                "cloud_history_alert",
                alert_number=self.cloud_alert_count,
                record=record,
                parsed=activity,
            )
            await self._async_set_activity(
                event=activity.get("event"),
                channel=activity.get("channel"),
                channel_name=activity.get("channel_name"),
                activity_time=activity_time,
                source="cloud",
                message=activity.get("message"),
                historical=False,
                record_key=key,
            )

    async def _async_update_data(self) -> dict[str, Any]:
        """Refresh whichever transports are enabled for this config entry."""
        await self._async_local_update()
        await self._async_cloud_update()

        if self._local_snapshot is not None:
            return self._local_snapshot

        return {
            "node_id": self.node_id,
            "model": None,
            "fw_version": None,
            "platform": None,
            "config": {},
            "params": {},
        }


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

        expected_node_id = self.coordinator.node_id

        node_id = None
        if isinstance(payload, dict):
            node_id = payload.get("nodeId") or payload.get("node_id")

        host_matches = bool(
            self.coordinator.client
            and addr[0] == self.coordinator.client.host
        )
        node_matches = bool(
            node_id and expected_node_id and str(node_id) == str(expected_node_id)
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

        self.coordinator.hass.async_create_task(
            self.coordinator.recorder.async_record(
                "udp_50001_datagram",
                **record,
            )
        )
        self.coordinator.hass.bus.async_fire(EVENT_UDP_PACKET, record)

        if matched:
            self.coordinator.request_local_refresh()


async def async_start_udp_listener(
    hass: HomeAssistant,
    coordinator: HosmartCoordinator,
):
    """Start the optional local-notification listener."""
    if not coordinator.local_enabled:
        return None

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
            "Could not bind Ho-Smart UDP/%s listener (%s); polling remains active",
            UDP_PORT,
            err,
        )
        return None

    await coordinator.recorder.async_record(
        "udp_listener_started",
        bind="0.0.0.0",
        port=UDP_PORT,
    )
    _LOGGER.info("Ho-Smart local notification listener active on UDP/%s", UDP_PORT)
    return transport
