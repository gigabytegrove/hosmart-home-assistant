"""Per-receiver and per-zone quiet-hours scheduling with restart-safe restore.

ZoneAlarming controls arm/disarm sensor channels; they are not per-channel
volume controls and may also suppress receiver/cloud alarm events.
"""

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
    CHANNEL_CUSTOM,
    CONF_CHANNEL_QUIET,
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
from .night_schedule import parse_time
from .schedule_actions import build_schedule_plan

_LOGGER = logging.getLogger(__name__)


def _target_for(key: str) -> int | bool:
    if key == "Volume":
        return 0
    if key == "Power" or key in (f"ZoneAlarming{i}" for i in range(1, 5)):
        return False
    raise ValueError(f"Unrecognized quiet-hours property: {key}")


def _valid_original(key: str, value: Any) -> bool:
    if key == "Volume":
        return type(value) in (int, float) and 0 <= value <= 100
    if key == "Power" or key in (f"ZoneAlarming{i}" for i in range(1, 5)):
        return type(value) in (bool, int) and value in (0, 1)
    return False


def _normalized_original(key: str, value: Any) -> int | float | bool:
    return bool(value) if key != "Volume" else value


class HosmartQuietHours:
    """Reconcile receiver and four channel schedules to verified local state.

    A single v1 Store key is retained so v0.2.6 restore intent is migrated
    instead of lost when the feature expands to multiple properties.
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
        self._managed: dict[str, Any] = {}
        self._unsubs: list[Any] = []
        self._time_unsubs: list[Any] = []
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._stopped = False
        self._failures: dict[str, int] = {}
        self._retry_after: dict[str, float] = {}

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

    @property
    def channels(self) -> dict[str, dict[str, str]]:
        rules = self.entry.options.get(CONF_CHANNEL_QUIET, {})
        return rules if isinstance(rules, dict) else {}

    async def async_start(self) -> None:
        """Load previous state, register all local-time boundaries, reconcile."""
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            values = stored.get("properties")
            if not isinstance(values, dict) and stored.get("active"):
                # Migrate v0.2.6 single-property restoration intent.
                action = stored.get("action")
                key = "Volume" if action == QUIET_ACTION_MUTE else (
                    "Power" if action == QUIET_ACTION_POWER else ""
                )
                values = {key: stored.get("original")} if key else {}
            if isinstance(values, dict):
                for key, item in values.items():
                    value = item.get("original") if isinstance(item, dict) else item
                    target = (
                        item.get("target", _target_for(key))
                        if isinstance(item, dict) else _target_for(key)
                    ) if key in ("Power", "Volume", *(
                        f"ZoneAlarming{i}" for i in range(1, 5)
                    )) else None
                    if _valid_original(key, value) and (
                        type(target) in (bool, int, float)
                    ):
                        self._managed[key] = {
                            "original": value,
                            "target": target,
                        }
                    else:
                        _LOGGER.warning(
                            "Discarded invalid saved quiet-hours property %s", key
                        )

        self._unsubs.append(self.coordinator.async_add_listener(self._queue))
        self._register_boundaries()
        await self.async_reconcile()

    def _register_boundaries(self) -> None:
        """Register every receiver and per-channel time without a reload."""
        boundaries = {self.start, self.end}
        for rule in self.channels.values():
            if isinstance(rule, dict) and rule.get("mode") == CHANNEL_CUSTOM:
                boundaries.update(
                    (
                        rule.get("start", DEFAULT_QUIET_START),
                        rule.get("end", DEFAULT_QUIET_END),
                    )
                )
        try:
            for boundary in boundaries:
                parsed = parse_time(boundary)
                self._time_unsubs.append(
                    async_track_time_change(
                        self.hass,
                        self._on_boundary,
                        hour=parsed.hour,
                        minute=parsed.minute,
                        second=parsed.second,
                    )
                )
        except (ValueError, TypeError):
            _LOGGER.exception(
                "Ho-Smart %s has an invalid quiet-hours boundary", self.entry.title
            )
            self._set_status("error")

    async def async_options_updated(self) -> None:
        """Rearm all time triggers and apply edits without reconnecting."""
        if self._stopped:
            return
        for unsub in self._time_unsubs:
            unsub()
        self._time_unsubs.clear()
        self._register_boundaries()
        self._retry_after.clear()
        await self.async_reconcile()

    async def async_stop(self) -> None:
        """Stop scheduling without clearing saved morning restoration intent."""
        self._stopped = True
        for unsub in self._time_unsubs:
            unsub()
        self._time_unsubs.clear()
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
        self._retry_after.clear()
        self._queue()

    def _queue(self) -> None:
        if self._stopped:
            return
        if self._task is not None and not self._task.done():
            return
        self._task = self.hass.async_create_task(
            self.async_reconcile(),
            f"Ho-Smart channel quiet hours {self.entry.entry_id}",
        )

    async def _save_managed(self) -> None:
        # Store before any command that may disconnect the receiver.
        await self._store.async_save(
            {
                "active": bool(self._managed),
                "properties": {
                    key: {"original": value["original"], "target": value["target"]}
                    for key, value in self._managed.items()
                },
            }
        )

    def _set_status(
        self, status: str, channels: dict[int, str] | None = None
    ) -> None:
        """Expose whether the desired operation actually succeeded."""
        states = channels or {i: "active" for i in range(1, 5)}
        changed = (
            self.coordinator.quiet_status != status
            or self.coordinator.channel_quiet_status != states
        )
        self.coordinator.quiet_status = status
        self.coordinator.channel_quiet_status = states
        if changed:
            self.coordinator.async_update_listeners()

    async def _write(self, key: str, value: int | float | bool) -> bool:
        if time.monotonic() < self._retry_after.get(key, 0):
            return False
        try:
            await self.coordinator.async_set_receiver_parameter(key, value)
            self._failures.pop(key, None)
            self._retry_after.pop(key, None)
            return True
        except Exception as err:
            failures = self._failures.get(key, 0) + 1
            self._failures[key] = failures
            self._retry_after[key] = time.monotonic() + min(
                900, 15 * 2 ** min(failures - 1, 6)
            )
            _LOGGER.warning(
                "Ho-Smart %s quiet-hours write %s failed: %s",
                self.entry.title, key, err,
            )
            return False

    async def async_reconcile(self) -> None:
        """Restore unwanted changes, then perform only supported zone actions."""
        async with self._lock:
            if self._stopped:
                return

            configured = self.enabled or any(
                isinstance(rule, dict) and rule.get("mode") == CHANNEL_CUSTOM
                for rule in self.channels.values()
            )
            if not self.coordinator.local_enabled:
                self._set_status("unsupported" if configured else "disabled")
                return
            if not self.coordinator.local_available or not self.coordinator.receiver:
                self._set_status(
                    "waiting_receiver" if (configured or self._managed) else "disabled"
                )
                return

            try:
                desired, statuses = build_schedule_plan(
                    dt_util.now(),
                    enabled=self.enabled,
                    start=self.start,
                    end=self.end,
                    default_action=self.action,
                    channels=self.channels,
                )
            except (TypeError, ValueError) as err:
                _LOGGER.error("Invalid Ho-Smart schedule: %s", err)
                self._set_status("error")
                return

            unsupported = any(
                state in ("unsupported_tone_mute", "unsupported_global_mute")
                for state in statuses.values()
            )

            # Original state (not the currently scheduled value) must survive
            # action changes, reloads, and interrupted nights.
            for key in list(self._managed):
                if key in desired:
                    continue
                item = self._managed[key]
                current = self.coordinator.receiver.get(key)
                if not _valid_original(key, current):
                    self._set_status("unsupported", statuses)
                    return
                if current == item["target"] and current != item["original"]:
                    if not await self._write(
                        key, _normalized_original(key, item["original"])
                    ):
                        self._set_status("error", statuses)
                        return
                del self._managed[key]
                await self._save_managed()

            for key, target in desired.items():
                current = self.coordinator.receiver.get(key)
                if not _valid_original(key, current):
                    _LOGGER.warning(
                        "Ho-Smart %s cannot schedule unavailable property %s",
                        self.entry.title, key,
                    )
                    self._set_status("unsupported", statuses)
                    return
                if current == target:
                    if key in self._managed and self._managed[key]["target"] != target:
                        self._managed[key]["target"] = target
                        await self._save_managed()
                    continue

                if key not in self._managed:
                    self._managed[key] = {
                        "original": current, "target": target
                    }
                    await self._save_managed()
                elif self._managed[key]["target"] != target:
                    self._managed[key]["target"] = target
                    await self._save_managed()

                if not await self._write(key, target):
                    self._set_status("error", statuses)
                    return

            if unsupported:
                self._set_status("unsupported", statuses)
            elif desired:
                self._set_status("scheduled", statuses)
            else:
                self._set_status(
                    "daytime" if configured else "disabled", statuses
                )
