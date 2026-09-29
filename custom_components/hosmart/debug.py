"""Persistent structured debug capture for Hosmart development builds."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from functools import partial
import json
from pathlib import Path
import threading
from typing import Any

from homeassistant.core import HomeAssistant

_SENSITIVE_KEYS = {
    "pop",
    "password",
    "access_token",
    "accesstoken",
    "refresh_token",
    "refreshtoken",
}

_MAX_BYTES = 50 * 1024 * 1024
_BACKUPS = 4


def redact(value: Any, key: str | None = None) -> Any:
    """Recursively redact credentials while preserving diagnostic structure."""
    if key is not None and key.lower() in _SENSITIVE_KEYS:
        if value in (None, ""):
            return value
        return "<redacted>"

    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    if isinstance(value, bytes):
        return {"length": len(value), "hex": value.hex()}
    return value


class HosmartDebugRecorder:
    """Append-only rotating JSONL recorder.

    The sample log receives every poll. The event journal separately receives
    every non-poll record so important changes survive even if high-frequency
    sample files rotate.
    """

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.hass = hass
        self.directory = Path(hass.config.path("hosmart_debug"))
        self.path = self.directory / f"hosmart_{entry_id}.jsonl"
        self.event_path = self.directory / f"hosmart_{entry_id}_events.jsonl"
        self._lock = threading.Lock()

    @staticmethod
    def _rotate_path(path: Path) -> None:
        if not path.exists() or path.stat().st_size < _MAX_BYTES:
            return

        oldest = path.with_suffix(path.suffix + f".{_BACKUPS}")
        if oldest.exists():
            oldest.unlink()

        for index in range(_BACKUPS - 1, 0, -1):
            src = path.with_suffix(path.suffix + f".{index}")
            dst = path.with_suffix(path.suffix + f".{index + 1}")
            if src.exists():
                src.replace(dst)

        path.replace(path.with_suffix(path.suffix + ".1"))

    @staticmethod
    def _append(path: Path, encoded: str) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.write("\n")

    def record_sync(self, kind: str, **payload: Any) -> None:
        """Synchronously append one structured record."""
        record = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "kind": kind,
            **redact(payload),
        }

        encoded = json.dumps(
            record,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )

        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)

            self._rotate_path(self.path)
            self._append(self.path, encoded)

            # Keep a second, compact journal of anything that is not a routine
            # successful sample. This is the long-lived fallback for scarce
            # real-world trigger opportunities.
            if kind != "poll_snapshot":
                self._rotate_path(self.event_path)
                self._append(self.event_path, encoded)

    async def async_record(self, kind: str, **payload: Any) -> None:
        """Append one record without blocking Home Assistant's event loop."""
        await self.hass.async_add_executor_job(
            partial(self.record_sync, kind, **payload)
        )

    @staticmethod
    def _tail_path(path: Path, lines: int) -> list[dict[str, Any]]:
        if not path.exists():
            return []

        with path.open("r", encoding="utf-8", errors="replace") as handle:
            raw_lines = deque(handle, maxlen=lines)

        result: list[dict[str, Any]] = []
        for line in raw_lines:
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError:
                result.append({"kind": "unparseable_log_line", "raw": line.rstrip()})
        return result

    def tail_sync(self, lines: int = 1000) -> list[dict[str, Any]]:
        """Return newest full-sample records for HA diagnostics."""
        with self._lock:
            return self._tail_path(self.path, lines)

    def event_tail_sync(self, lines: int = 5000) -> list[dict[str, Any]]:
        """Return newest non-routine records for HA diagnostics."""
        with self._lock:
            return self._tail_path(self.event_path, lines)
