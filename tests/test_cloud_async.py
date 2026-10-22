"""Async Ho-Smart HTTPS regression tests independent of Home Assistant."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import socket
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "hosmart"
PACKAGE_NAME = "_hosmart_async_test"
package = types.ModuleType(PACKAGE_NAME)
package.__path__ = [str(ROOT)]
sys.modules[PACKAGE_NAME] = package


def load(name: str):
    spec = importlib.util.spec_from_file_location(
        f"{PACKAGE_NAME}.{name}", ROOT / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cloud = load("cloud")
transport = load("cloud_async")


class FakeResponse:
    def __init__(self, obj=None, status=200, raw=None):
        self.status = status
        self.content = self
        self._raw = (
            json.dumps(obj if obj is not None else {"data": []}).encode()
            if raw is None else raw
        )

    async def read(self, size):
        return self._raw[:size]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class FakeSession:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests = []

    def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply


class CloudTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_pooled_session_is_reused(self):
        session = FakeSession(FakeResponse(), FakeResponse())
        client = transport.HosmartHistoryClient(session)
        await client.query_history("test", 1, 2)
        await client.query_history("test", 1, 2)
        self.assertEqual(client.stats["http_attempts"], 2)
        self.assertEqual(client.stats["retries"], 0)
        self.assertTrue(all(url == cloud.HISTORY_URL for url, _ in session.requests))

    async def test_timeout_is_retried_and_recovers(self):
        session = FakeSession(
            TimeoutError("temporary"), FakeResponse({"data": [{"id": 1}]})
        )
        client = transport.HosmartHistoryClient(session)
        with patch.object(transport.asyncio, "sleep", return_value=None):
            result = await client.query_history("test", 1, 2)
        self.assertEqual(result, [{"id": 1}])
        self.assertEqual(client.stats["retries"], 1)
        self.assertEqual(client.stats["failure_categories"]["timeout"], 1)
        self.assertEqual(client.stats["failed_requests"], 0)

    async def test_dns_error_classification(self):
        import aiohttp
        connector_error = aiohttp.ClientConnectorError(
            None, socket.gaierror(-3, "Try again")
        )
        classified = transport.classify_transport_error(connector_error)
        self.assertEqual(classified.category, "dns")
        self.assertTrue(classified.retryable)

    async def test_http_503_retried(self):
        session = FakeSession(FakeResponse(status=503), FakeResponse())
        with patch.object(transport.asyncio, "sleep", return_value=None):
            await transport.HosmartHistoryClient(session).query_history("test", 1, 2)
        self.assertEqual(len(session.requests), 2)

    async def test_http_401_is_not_retried(self):
        session = FakeSession(FakeResponse(status=401))
        with self.assertRaises(cloud.HosmartCloudAuthError):
            await transport.HosmartHistoryClient(session).query_history("test", 1, 2)
        self.assertEqual(len(session.requests), 1)

    async def test_http_400_is_not_retried(self):
        session = FakeSession(FakeResponse(status=400))
        with self.assertRaises(transport.HosmartHistoryTransportError) as caught:
            await transport.HosmartHistoryClient(session).query_history("test", 1, 2)
        self.assertFalse(caught.exception.retryable)
        self.assertEqual(len(session.requests), 1)

    async def test_both_attempts_fail(self):
        session = FakeSession(TimeoutError("first"), TimeoutError("second"))
        client = transport.HosmartHistoryClient(session)
        with patch.object(transport.asyncio, "sleep", return_value=None):
            with self.assertRaises(transport.HosmartHistoryTransportError):
                await client.query_history("test", 1, 2)
        self.assertEqual(client.stats["failed_requests"], 1)
        self.assertEqual(client.stats["retries"], 1)

    async def test_pagination_success(self):
        session = FakeSession(
            FakeResponse({"data": [{"msgtime": 1}], "lastKey": "second"}),
            FakeResponse({"data": [{"msgtime": 2}]}),
        )
        result = await transport.HosmartHistoryClient(session).query_history(
            "test", 1, 2
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(session.requests[1][1]["json"]["startKeyJson"], "second")

    async def test_repeated_cursor_rejected(self):
        session = FakeSession(
            FakeResponse({"lastKey": "same"}),
            FakeResponse({"lastKey": "same"}),
        )
        with self.assertRaisesRegex(transport.HosmartHistoryTransportError, "repeated"):
            await transport.HosmartHistoryClient(session).query_history("test", 1, 2)

    async def test_pagination_limit_never_returns_partial_data(self):
        session = FakeSession(
            FakeResponse({"data": [{"msgtime": 1}], "lastKey": "more"})
        )
        with self.assertRaisesRegex(transport.HosmartHistoryTransportError, "limit"):
            await transport.HosmartHistoryClient(session).query_history(
                "test", 1, 2, max_pages=1
            )

    async def test_malformed_history_data_rejected(self):
        session = FakeSession(FakeResponse({"data": "bad"}))
        with self.assertRaisesRegex(transport.HosmartHistoryTransportError, "not a list"):
            await transport.HosmartHistoryClient(session).query_history("test", 1, 2)

    async def test_invalid_json_retries_once(self):
        session = FakeSession(FakeResponse(raw=b"invalid"), FakeResponse())
        with patch.object(transport.asyncio, "sleep", return_value=None):
            result = await transport.HosmartHistoryClient(session).query_history(
                "test", 1, 2
            )
        self.assertEqual(result, [])
        self.assertEqual(len(session.requests), 2)

    async def test_response_size_limit(self):
        session = FakeSession(
            FakeResponse(raw=b"x" * (2 * 1024 * 1024 + 1))
        )
        with self.assertRaisesRegex(transport.HosmartHistoryTransportError, "too large"):
            await transport.HosmartHistoryClient(session).query_history("test", 1, 2)

    async def test_query_bounds(self):
        client = transport.HosmartHistoryClient(FakeSession())
        with self.assertRaises(ValueError):
            await client.query_history("test", 4, 3)
        with self.assertRaises(ValueError):
            await client.query_history("test", 1, 2, max_pages=0)

    async def test_cancellation_is_never_swallowed(self):
        session = FakeSession(asyncio.CancelledError())
        with self.assertRaises(asyncio.CancelledError):
            await transport.HosmartHistoryClient(session).query_history("test", 1, 2)


if __name__ == "__main__":
    unittest.main()
