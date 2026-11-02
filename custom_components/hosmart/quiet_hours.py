"""Per-receiver quiet-hours controller; never interferes with alarm ingestion."""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_QUIET_ACTION,
    CONF_QUIET_ENABLED,
    CONF_QUIET_END,
    CONF_QUIET_START,
    DEFAULT_QUIET_ACTION,
    DEFAULT_QUIET_END,
    DEFAULT_QUIET_START,
    QUIET_ACTION_MUTE,
    QUIET_ACTION_POWER,
)
from .coordinator import HosmartCoordinator
from .night_schedule import is_quiet_now, parse_time

_LOGGER = logging.getLogger(__name__)

_PARAMETERS = {
    QUIET_ACTION_MUTE: ("Volume", 0),
    QUIET_ACTION_POWER: ("Power", False),
}


class HosmartQuietHours:
    """Schedule and restore a single config entry's receiver state.

    Restoration intent is written to HA storage *before* changing hardware.
    A restart midway through the night therefore retains the original setting.
    Only the selected receiver is modified; cloud alarms keep polling.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: HosmartCoordinator,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self._store = Store(hass, 1, f"hosmart_quiet_{entry.entry_id}")
        self._state: dict[str, Any] | None = None
        self._unsubs: list[Any] = []
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._stopped = False
        self._failure_count = 0
        self._retry_after = 0.0

    @property
    def enabled(self) -> bool:
        return bool(self.entry.options.get(CONF_QUIET_ENABLED, False))

    @property
    def action(self) -> str:
        return self.entry.options.get(CONF_QUIET_ACTION, DEFAULT_QUIET_ACTION)

    @property
    def start(self) -> str:
        return self.entry.options.get(CONF_QUIET_START, DEFAULT_QUIET_START)

    @property
    def end(self) -> str:
        return self.entry.options.get(CONF_QUIET_END, DEFAULT_QUIET_END)

    async def async_start(self) -> None:
        """Restore pending intent, arm local-time transitions and reconcile now."""
        stored = await self._store.async_load()
        if isinstance(stored, dict) and stored.get("active") is True:
            if (
                stored.get("action") in _PARAMETERS
                and type(stored.get("original")) in (bool, int, float)
            ):
                self._state = stored
            else:
                _LOGGER.warning("Discarding malformed Ho-Smart quiet-hours state")
        self._unsubs.append(self.coordinator.async_add_listener(self._queue_reconcile))
        for boundary in (self.start, self.end):
            parsed = parse_time(boundary)
            self._unsubs.append(
                async_track_time_change(
                    self.hass,
                    self._on_boundary,
                    hour=parsed.hour,
                    minute=parsed.minute,
                    second=parsed.second,
                )
            )
        await self.async_reconcile()

    async def async_stop(self) -> None:
        """Unregister callbacks without undoing a night-time state during reload."""
        self._stopped = True
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def _on_boundary(self, _now: datetime) -> None:
        # Transitions, especially morning restoration, bypass stale retry delay.
        self._retry_after = 0.0
        self._queue_reconcile()

    def _queue_reconcile(self) -> None:
        if self._stopped:
            return
        if self._task is not None and not self._task.done():
            return
        self._task = self.hass.async_create_task(
            self.async_reconcile(), f"Ho-Smart quiet hours {self.entry.entry_id}"
        )

    async def _save_state(self, state: dict[str, Any] | None) -> None:
        await self._store.async_save(state or {"active": False})
        self._state = state

    def _set_status(self, status: str) -> None:
        if self.coordinator.quiet_status != status:
            self.coordinator.quiet_status = status
            self.coordinator.async_update_listeners()

    async def _write(self, key: str, value: int | float | bool) -> bool:
        # Unsupported firmware must not be hammered with writes every 3-5s.
        if time.monotonic() < self._retry_after:
            return False
        try:
            await self.coordinator.async_set_receiver_parameter(key, value)
            self._failure_count = 0
            self._retry_after = 0.0
            return True
        except Exception as err:
            self._failure_count += 1
            self._retry_after = time.monotonic() + min(
                900, 15 * 2 ** min(self._failure_count - 1, 6)
            )
            _LOGGER.warning(
                "Ho-Smart %s quiet hours could not set %s: %s",
                self.entry.title, key, err,
            )
            self._set_status("error")
            return False

    async def _restore(self, receiver: dict[str, Any]) -> bool:
        """Restore only a value we changed, never blindly overwrite a manual edit."""
        assert self._state is not None
        key, target = _PARAMETERS[self._state["action"]]
        current = receiver.get(key)
        original = self._state["original"]

        if current == target and current != original:
            if not await self._write(key, original):
                return False
        await self._save_state(None)
        return True

    async def async_reconcile(self) -> None:
        """Apply a transition and retry failures when local polling resumes."""
        async with self._lock:
            if self._stopped:
                return
            if not self.coordinator.local_enabled:
                self._set_status("disabled")
                return
            # A cached snapshot must never be used to issue commands if local
            # connectivity has failed since it was captured.
            if not self.coordinator.local_available:
                self._set_status("waiting_receiver" if self.enabled else "disabled")
                return
            receiver = self.coordinator.receiver
            if not receiver:
                self._set_status("waiting_receiver" if self.enabled else "disabled")
                return
            try:
                in_window = self.enabled and is_quiet_now(
                    dt_util.now(), self.start, self.end
                )
            except ValueError as err:
                _LOGGER.error("Invalid Ho-Smart quiet-hours schedule: %s", err)
                return
            requested_action = self.action if in_window else None

            if self._state is not None and (
                requested_action != self._state["action"]
            ):
                if not await self._restore(receiver):
                    return
                receiver = self.coordinator.receiver

            if requested_action is None:
                self._set_status("daytime" if self.enabled else "disabled")
                return
            key, target = _PARAMETERS.get(requested_action, (None, None))
            if key is None:
                _LOGGER.error("Unknown quiet-hours action %s", requested_action)
                self._set_status("error")
                return
            current = receiver.get(key)
            if type(current) not in (bool, int, float):
                _LOGGER.warning(
                    "Ho-Smart %s has no readable %s control; quiet hours not applied",
                    self.entry.title, key,
                )
                self._set_status("unsupported")
                return

            if self._state is None:
                await self._save_state(
                    {"active": True, "action": requested_action, "original": current}
                )

            if current != target:
                if not await self._write(key, target):
                    self._set_status("error")
                    return
            self._set_status("quiet")
