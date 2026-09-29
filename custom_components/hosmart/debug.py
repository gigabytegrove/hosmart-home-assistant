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

    The development integration deliberately records every local state sample,
    every detected change, every UDP/50001 datagram, and every polling error so
    a one-off driveway pass can be reconstructed later.
    """

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.hass = hass
        self.directory = Path(hass.config.path("hosmart_debug"))
        self.path = self.directory / f"hosmart_{entry_id}.jsonl"
        self._lock = threading.Lock()

    def _rotate_locked(self) -> None:
        if not self.path.exists() or self.path.stat().st_size < _MAX_BYTES:
            return

        oldest = self.path.with_suffix(self.path.suffix + f".{_BACKUPS}")
        if oldest.exists():
            oldest.unlink()

        for index in range(_BACKUPS - 1, 0, -1):
            src = self.path.with_suffix(self.path.suffix + f".{index}")
            dst = self.path.with_suffix(self.path.suffix + f".{index + 1}")
            if src.exists():
                src.replace(dst)

        self.path.replace(self.path.with_suffix(self.path.suffix + ".1"))

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
            self._rotate_locked()
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(encoded)
                handle.write("\n")

    async def async_record(self, kind: str, **payload: Any) -> None:
        """Append one record without blocking Home Assistant's event loop."""
        await self.hass.async_add_executor_job(
            partial(self.record_sync, kind, **payload)
        )

    def tail_sync(self, lines: int = 1000) -> list[dict[str, Any]]:
        """Return the newest structured records for HA diagnostics."""
        if not self.path.exists():
            return []

        with self._lock:
            with self.path.open("r", encoding="utf-8", errors="replace") as handle:
                raw_lines = deque(handle, maxlen=lines)

        result: list[dict[str, Any]] = []
        for line in raw_lines:
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError:
                result.append({"kind": "unparseable_log_line", "raw": line.rstrip()})
        return result
