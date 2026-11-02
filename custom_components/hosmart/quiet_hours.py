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
from .night_schedule import parse_time, plan_channel_quiet

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
            fields = stored.get("properties")
            if not isinstance(fields, dict) and stored.get("active"):
                # v0.2.6 had at most one managed property.
                action = stored.get("action")
                key = "Volume" if action == QUIET_ACTION_MUTE else (
                    "Power" if action == QUIET_ACTION_POWER else ""
                )
                fields = {key: stored.get("original")} if key else {}
            if isinstance(fields, dict):
                self._managed = {
                    key: {"original": value}
                    for key, value in fields.items()
                    if _valid_original(key, value)
                }
                if len(self._managed) != len(fields):
                    _LOGGER.warning(
                        "Ho-Smart %s discarded invalid saved quiet-hours data",
                        self.entry.title,
                    )

        self._unsubs.append(self.coordinator.async_add_listener(self._queue))
        boundaries = {self.start, self.end}
        for rule in self.channels.values():
            if isinstance(rule, dict) and rule.get("mode") == CHANNEL_CUSTOM:
                boundaries.update(
                    (rule.get("start", DEFAULT_QUIET_START),
                     rule.get("end", DEFAULT_QUIET_END))
                )
        try:
            for boundary in boundaries:
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
        except (ValueError, TypeError):
            _LOGGER.error("Ho-Smart %s has an invalid quiet-hours time", self.entry.title)
            self._set_status("error")
            return
        await self.async_reconcile()

    async def async_stop(self) -> None:
        """Stop scheduling without clearing saved morning restoration intent."""
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
            {"active": bool(self._managed), "properties": {
                key: item["original"] for key, item in self._managed.items()
            }}
        )

    def _set_status(self, status: str, zones: tuple[int, ...] = ()) -> None:
        """Expose failed writes as errors instead of a false quiet success."""
        changed = self.coordinator.quiet_status != status
        states: dict[int, str] = {}
        for index in range(1, 5):
            rule = self.channels.get(str(index), {})
            protected = isinstance(rule, dict) and rule.get("mode") == "always_active"
            if index in zones:
                states[index] = (
                    status if status in ("error", "unsupported", "waiting_receiver")
                    else "quiet"
                )
            elif protected:
                states[index] = "protected"
            else:
                states[index] = "active"
        if self.coordinator.channel_quiet_status != states:
            self.coordinator.channel_quiet_status = states
            changed = True
        self.coordinator.quiet_status = status
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
        """Restore obsolete settings first, then apply the current quiet plan."""
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
                self._set_status("waiting_receiver" if (configured or self._managed)
                                 else "disabled")
                return
            try:
                global_action, zones = plan_channel_quiet(
                    dt_util.now(),
                    receiver_enabled=self.enabled,
                    receiver_start=self.start,
                    receiver_end=self.end,
                    receiver_action=self.action,
                    channels=self.channels,
                )
            except (TypeError, ValueError) as err:
                _LOGGER.error("Invalid Ho-Smart quiet-hours configuration: %s", err)
                self._set_status("error")
                return

            desired: dict[str, int | bool] = {}
            if global_action == QUIET_ACTION_MUTE:
                desired["Volume"] = 0
            elif global_action == QUIET_ACTION_POWER:
                desired["Power"] = False
            else:
                for index in zones:
                    desired[f"ZoneAlarming{index}"] = False

            effective_zones = (1, 2, 3, 4) if global_action else zones

            # Restore prior values that the latest plan no longer targets,
            # including any saved v0.2.6 global Volume/Power state. Protected
            # channels take priority: failing to restore global audio is an
            # error rather than claiming a protected driveway is still audible.
            for key in list(self._managed):
                if key in desired:
                    continue
                original = self._managed[key]["original"]
                current = self.coordinator.receiver.get(key)
                if current is None:
                    self._set_status("unsupported", effective_zones)
                    return
                if current == _target_for(key) and current != original:
                    if not await self._write(
                        key, _normalized_original(key, original)
                    ):
                        self._set_status("error", effective_zones)
                        return
                del self._managed[key]
                await self._save_managed()

            # When a receiver-wide mute/power operation is desired, ensure
            # all channel rules evaluated quiet before modifying the master.
            for key, target in desired.items():
                current = self.coordinator.receiver.get(key)
                if not _valid_original(key, current):
                    _LOGGER.warning(
                        "Ho-Smart %s does not expose usable %s for scheduling",
                        self.entry.title, key,
                    )
                    self._set_status("unsupported", effective_zones)
                    return
                if current == target:
                    continue
                if key not in self._managed:
                    self._managed[key] = {"original": current}
                    await self._save_managed()
                if not await self._write(key, target):
                    self._set_status("error", effective_zones)
                    return

            if desired:
                self._set_status(
                    "quiet" if len(effective_zones) == 4 else "partially_quiet",
                    effective_zones,
                )
            else:
                protected = any(
                    isinstance(rule, dict) and rule.get("mode") == "always_active"
                    for rule in self.channels.values()
                )
                self._set_status(
                    "protected" if self.enabled and protected else (
                        "daytime" if configured else "disabled"
                    )
                )
