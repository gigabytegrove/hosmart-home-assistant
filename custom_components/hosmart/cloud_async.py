"""Pooled, retry-aware Ho-Smart history transport using HA's HTTP session."""

from __future__ import annotations

import asyncio
from collections import Counter
import json
import logging
import socket
import ssl
import time
from typing import Any

import aiohttp

from .cloud import HISTORY_URL, HosmartCloudAuthError, HosmartCloudError, _unwrap

_LOGGER = logging.getLogger(__name__)
_MAX_ATTEMPTS = 2
_BACKOFF_SECONDS = 0.5
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(
    total=12, connect=5, sock_connect=5, sock_read=10
)
_RETRYABLE_HTTP = {408, 425, 429, 500, 502, 503, 504}


class HosmartHistoryTransportError(HosmartCloudError):
    """Cloud retrieval failure with a safe, actionable classification."""

    def __init__(self, category: str, description: str, *, retryable: bool) -> None:
        super().__init__(description)
        self.category = category
        self.retryable = retryable


def classify_transport_error(exc: BaseException) -> HosmartHistoryTransportError:
    """Map aiohttp failures to stable diagnostic categories."""
    if isinstance(exc, aiohttp.ClientConnectorCertificateError):
        return HosmartHistoryTransportError(
            "tls_certificate",
            "Ho-Smart cloud TLS certificate verification failed",
            retryable=False,
        )
    if isinstance(exc, aiohttp.ClientConnectorError):
        original = exc.os_error
        if isinstance(original, socket.gaierror):
            return HosmartHistoryTransportError(
                "dns", "Ho-Smart cloud DNS lookup failed", retryable=True
            )
        if isinstance(original, ssl.SSLError):
            return HosmartHistoryTransportError(
                "tls", "Ho-Smart cloud TLS handshake failed", retryable=True
            )
        return HosmartHistoryTransportError(
            "connect", "Ho-Smart cloud TCP connection failed", retryable=True
        )
    if isinstance(exc, aiohttp.ClientSSLError):
        return HosmartHistoryTransportError(
            "tls", "Ho-Smart cloud TLS handshake failed", retryable=True
        )
    if isinstance(exc, aiohttp.SocketTimeoutError):
        return HosmartHistoryTransportError(
            "read_timeout", "Ho-Smart cloud response timed out", retryable=True
        )
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return HosmartHistoryTransportError(
            "timeout", "Ho-Smart cloud request timed out", retryable=True
        )
    if isinstance(exc, (aiohttp.ClientError, OSError)):
        return HosmartHistoryTransportError(
            "transport", "Ho-Smart cloud connection interrupted", retryable=True
        )
    return HosmartHistoryTransportError(
        "unexpected", "Ho-Smart cloud response failed", retryable=False
    )


class HosmartHistoryClient:
    """Reuse a HA-owned HTTPS session; never close its connection pool."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._counts: Counter[str] = Counter()
        self._last_error_category: str | None = None
        self._last_latency_ms: float | None = None

    @property
    def stats(self) -> dict[str, Any]:
        """Safe transport counters for integration diagnostics."""
        return {
            "requests": self._counts["requests"],
            "http_attempts": self._counts["http_attempts"],
            "retries": self._counts["retries"],
            "successful_requests": self._counts["successful_requests"],
            "failed_requests": self._counts["failed_requests"],
            "failure_categories": {
                k.removeprefix("error_"): v
                for k, v in sorted(self._counts.items())
                if k.startswith("error_")
            },
            "last_error_category": self._last_error_category,
            "last_latency_ms": self._last_latency_ms,
        }

    async def _post_json(self, body: dict[str, Any]) -> dict[str, Any]:
        """Retry transient connection, DNS, timeout, and server errors once."""
        self._counts["requests"] += 1
        started = time.monotonic()
        for attempt in range(_MAX_ATTEMPTS):
            self._counts["http_attempts"] += 1
            try:
                async with self._session.post(
                    HISTORY_URL, json=body, timeout=_REQUEST_TIMEOUT
                ) as response:
                    status = response.status
                    if status in (401, 403):
                        raise HosmartCloudAuthError(
                            "Ho-Smart cloud authentication failed"
                        )
                    if status >= 400:
                        raise HosmartHistoryTransportError(
                            "http", f"Ho-Smart cloud returned HTTP {status}",
                            retryable=status in _RETRYABLE_HTTP,
                        )
                    raw = await response.content.read(_MAX_RESPONSE_BYTES + 1)
                    if len(raw) > _MAX_RESPONSE_BYTES:
                        raise HosmartHistoryTransportError(
                            "oversize",
                            "Ho-Smart cloud response was too large",
                            retryable=False,
                        )
                    try:
                        decoded = json.loads(raw)
                    except (UnicodeDecodeError, ValueError) as exc:
                        raise HosmartHistoryTransportError(
                            "invalid_json",
                            "Ho-Smart cloud returned invalid JSON",
                            retryable=True,
                        ) from exc
                    decoded = _unwrap(decoded)
                    if not isinstance(decoded, dict):
                        raise HosmartHistoryTransportError(
                            "invalid_json",
                            "Ho-Smart cloud response was not an object",
                            retryable=True,
                        )
                    self._counts["successful_requests"] += 1
                    self._last_latency_ms = round(
                        (time.monotonic() - started) * 1000, 2
                    )
                    return decoded
            except HosmartCloudAuthError:
                self._counts["error_auth"] += 1
                self._counts["failed_requests"] += 1
                self._last_error_category = "auth"
                raise
            except HosmartHistoryTransportError as exc:
                failure = exc
            except (aiohttp.ClientError, TimeoutError, OSError) as exc:
                failure = classify_transport_error(exc)

            self._counts[f"error_{failure.category}"] += 1
            self._last_error_category = failure.category
            if not failure.retryable or attempt == _MAX_ATTEMPTS - 1:
                self._counts["failed_requests"] += 1
                raise failure
            self._counts["retries"] += 1
            _LOGGER.debug(
                "Ho-Smart cloud %s error, retrying once", failure.category
            )
            await asyncio.sleep(_BACKOFF_SECONDS)

        raise RuntimeError("Unreachable Ho-Smart retry state")

    async def query_history(
        self, user_id: str, start_ms: int, end_ms: int, *, max_pages: int = 50
    ) -> list[dict[str, Any]]:
        """Return all pages or fail without returning incomplete notice data."""
        if max_pages < 1 or end_ms < start_ms:
            raise ValueError("Invalid Ho-Smart history query bounds")
        records: list[dict[str, Any]] = []
        seen_cursors: set[str] = set()
        last_key: Any = ""
        for _ in range(max_pages):
            response = await self._post_json(
                {
                    "user_id": user_id,
                    "startTime": int(start_ms),
                    "endTime": int(end_ms),
                    "pageSize": 20,
                    "startKeyJson": last_key,
                }
            )
            data = response.get("data")
            if data is None:
                data = []
            if not isinstance(data, list):
                raise HosmartHistoryTransportError(
                    "invalid_json",
                    "Ho-Smart cloud history 'data' is not a list",
                    retryable=False,
                )
            if any(not isinstance(record, dict) for record in data):
                raise HosmartHistoryTransportError(
                    "invalid_json",
                    "Ho-Smart cloud history includes invalid records",
                    retryable=False,
                )
            records.extend(data)
            key = response.get("lastKey")
            if not key:
                return records
            cursor = json.dumps(key, sort_keys=True, default=str)
            if cursor in seen_cursors:
                raise HosmartHistoryTransportError(
                    "pagination",
                    "Ho-Smart cloud returned a repeated history cursor",
                    retryable=False,
                )
            seen_cursors.add(cursor)
            last_key = key
        raise HosmartHistoryTransportError(
            "pagination",
            "Ho-Smart cloud history exceeded the page limit",
            retryable=False,
        )
