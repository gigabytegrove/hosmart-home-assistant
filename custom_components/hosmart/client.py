"""Local ESP RainMaker client for Hosmart receivers."""

from __future__ import annotations

import hashlib
import http.client
import json
import logging
import socket
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

_LOGGER = logging.getLogger(__name__)


class HosmartError(Exception):
    """Base Hosmart client error."""


class HosmartConnectionError(HosmartError):
    """Connection or protocol transport error."""


class HosmartAuthenticationError(HosmartError):
    """Security1 authentication error."""


def _encode_varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while True:
        if pos >= len(data):
            raise HosmartError("Truncated protobuf varint")
        byte = data[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, pos
        shift += 7
        if shift > 63:
            raise HosmartError("Invalid protobuf varint")


def _field_bytes(field: int, value: bytes) -> bytes:
    return _encode_varint((field << 3) | 2) + _encode_varint(len(value)) + value


def _field_varint(field: int, value: int) -> bytes:
    return _encode_varint(field << 3) + _encode_varint(value)


def _parse_fields(data: bytes) -> list[tuple[int, int, int | bytes]]:
    fields: list[tuple[int, int, int | bytes]] = []
    pos = 0
    while pos < len(data):
        key, pos = _read_varint(data, pos)
        number = key >> 3
        wire = key & 7

        if wire == 0:
            value, pos = _read_varint(data, pos)
            fields.append((number, wire, value))
        elif wire == 2:
            length, pos = _read_varint(data, pos)
            end = pos + length
            if end > len(data):
                raise HosmartError("Truncated protobuf field")
            fields.append((number, wire, data[pos:end]))
            pos = end
        elif wire == 1:
            end = pos + 8
            if end > len(data):
                raise HosmartError("Truncated protobuf fixed64")
            fields.append((number, wire, data[pos:end]))
            pos = end
        elif wire == 5:
            end = pos + 4
            if end > len(data):
                raise HosmartError("Truncated protobuf fixed32")
            fields.append((number, wire, data[pos:end]))
            pos = end
        else:
            raise HosmartError(f"Unsupported protobuf wire type {wire}")
    return fields


def _first(
    fields: list[tuple[int, int, int | bytes]], number: int
) -> tuple[int, int, int | bytes] | None:
    return next((field for field in fields if field[0] == number), None)


def _bytes_value(
    fields: list[tuple[int, int, int | bytes]], number: int
) -> bytes | None:
    field = _first(fields, number)
    if field is None or field[1] != 2 or not isinstance(field[2], bytes):
        return None
    return field[2]


def _int_value(
    fields: list[tuple[int, int, int | bytes]], number: int, default: int = 0
) -> int:
    field = _first(fields, number)
    if field is None or field[1] != 0 or not isinstance(field[2], int):
        return default
    return field[2]


class HosmartClient:
    """Synchronous local client.

    Home Assistant runs these methods in its executor. The client keeps a
    Security1 session open between polls and transparently reconnects once if
    the receiver closes the connection.
    """

    def __init__(self, host: str, port: int, pop: str, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.pop = pop
        self.timeout = timeout

        self._connection: http.client.HTTPConnection | None = None
        self._cookie: str | None = None
        self._cipher = None
        self._property_indexes: dict[str, int] = {}
        self._config: dict[str, Any] = {}

    def close(self) -> None:
        """Close the current local session."""
        if self._connection is not None:
            try:
                self._connection.close()
            except OSError:
                pass
        self._connection = None
        self._cookie = None
        self._cipher = None
        self._property_indexes = {}
        self._config = {}

    def _connect(self) -> None:
        self._connection = http.client.HTTPConnection(
            self.host, self.port, timeout=self.timeout
        )
        try:
            self._connection.connect()
        except (OSError, socket.error) as err:
            self.close()
            raise HosmartConnectionError(
                f"Unable to connect to {self.host}:{self.port}: {err}"
            ) from err

    def _post(self, path: str, body: bytes) -> bytes:
        if self._connection is None:
            self._connect()
        assert self._connection is not None

        headers = {
            "Accept": "text/plain",
            "Content-type": "application/x-www-form-urlencoded",
            "Connection": "Keep-Alive",
        }
        if self._cookie:
            headers["Cookie"] = self._cookie

        try:
            self._connection.request("POST", path, body=body, headers=headers)
            response = self._connection.getresponse()
            set_cookie = response.getheader("Set-Cookie")
            if set_cookie:
                self._cookie = set_cookie.split(";", 1)[0]
            data = response.read()
        except (OSError, http.client.HTTPException) as err:
            raise HosmartConnectionError(f"Local HTTP request failed: {err}") from err

        if response.status != 200:
            raise HosmartConnectionError(
                f"Receiver returned HTTP {response.status} for {path}"
            )
        return data

    @staticmethod
    def _sec1_command0(client_public_key: bytes) -> bytes:
        cmd0 = _field_bytes(1, client_public_key)
        sec1 = _field_bytes(20, cmd0)
        return _field_varint(2, 1) + _field_bytes(11, sec1)

    @staticmethod
    def _parse_sec1_response0(data: bytes) -> tuple[bytes, bytes]:
        session = _parse_fields(data)
        if _int_value(session, 2, -1) != 1:
            raise HosmartAuthenticationError("Receiver did not select Security1")

        sec1_raw = _bytes_value(session, 11)
        if sec1_raw is None:
            raise HosmartAuthenticationError("Security1 payload missing")
        sec1 = _parse_fields(sec1_raw)
        if _int_value(sec1, 1, -1) != 1:
            raise HosmartAuthenticationError("Expected Security1 Response0")

        resp_raw = _bytes_value(sec1, 21)
        if resp_raw is None:
            raise HosmartAuthenticationError("Security1 Response0 payload missing")
        resp = _parse_fields(resp_raw)
        if _int_value(resp, 1, 0) != 0:
            raise HosmartAuthenticationError("Security1 Response0 rejected")

        device_public = _bytes_value(resp, 2)
        device_random = _bytes_value(resp, 3)
        if device_public is None or len(device_public) != 32:
            raise HosmartAuthenticationError("Invalid device public key")
        if device_random is None or len(device_random) != 16:
            raise HosmartAuthenticationError("Invalid device random")
        return device_public, device_random

    @staticmethod
    def _sec1_command1(client_verify: bytes) -> bytes:
        cmd1 = _field_bytes(2, client_verify)
        sec1 = _field_varint(1, 2) + _field_bytes(22, cmd1)
        return _field_varint(2, 1) + _field_bytes(11, sec1)

    @staticmethod
    def _parse_sec1_response1(data: bytes) -> bytes:
        session = _parse_fields(data)
        if _int_value(session, 2, -1) != 1:
            raise HosmartAuthenticationError("Security version changed")

        sec1_raw = _bytes_value(session, 11)
        if sec1_raw is None:
            raise HosmartAuthenticationError("Security1 payload missing")
        sec1 = _parse_fields(sec1_raw)
        if _int_value(sec1, 1, -1) != 3:
            raise HosmartAuthenticationError("Expected Security1 Response1")

        resp_raw = _bytes_value(sec1, 23)
        if resp_raw is None:
            raise HosmartAuthenticationError("Security1 Response1 payload missing")
        resp = _parse_fields(resp_raw)
        if _int_value(resp, 1, 0) != 0:
            raise HosmartAuthenticationError("Security1 Response1 rejected")

        verify = _bytes_value(resp, 3)
        if verify is None or len(verify) != 32:
            raise HosmartAuthenticationError("Invalid device verification data")
        return verify

    def _crypt(self, data: bytes) -> bytes:
        if self._cipher is None:
            raise HosmartAuthenticationError("Security1 session is not established")
        result = self._cipher.update(data)
        if len(result) != len(data):
            raise HosmartAuthenticationError("Unexpected AES-CTR result length")
        return result

    def _establish_session(self) -> None:
        self.close()
        self._connect()

        client_private = X25519PrivateKey.generate()
        client_public = client_private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

        response0 = self._post(
            "/esp_local_ctrl/session", self._sec1_command0(client_public)
        )
        device_public, device_random = self._parse_sec1_response0(response0)

        shared_key = bytearray(
            client_private.exchange(X25519PublicKey.from_public_bytes(device_public))
        )
        pop_hash = hashlib.sha256(self.pop.encode("utf-8")).digest()
        for index in range(32):
            shared_key[index] ^= pop_hash[index]

        self._cipher = Cipher(
            algorithms.AES(bytes(shared_key)), modes.CTR(device_random)
        ).encryptor()

        client_verify = self._crypt(device_public)
        response1 = self._post(
            "/esp_local_ctrl/session", self._sec1_command1(client_verify)
        )
        device_verify = self._parse_sec1_response1(response1)
        verified_client_public = self._crypt(device_verify)

        if verified_client_public != client_public:
            self.close()
            raise HosmartAuthenticationError(
                "Security1 device verification failed; check the POP"
            )

    @staticmethod
    def _count_request() -> bytes:
        return b"\x52\x00"

    @staticmethod
    def _parse_count_response(data: bytes) -> int:
        outer = _parse_fields(data)
        payload = _bytes_value(outer, 11)
        if payload is None:
            raise HosmartError("Property-count response missing")
        inner = _parse_fields(payload)
        if _int_value(inner, 1, 0) != 0:
            raise HosmartError("Receiver rejected property-count request")
        count = _int_value(inner, 2, 0)
        if count <= 0 or count > 100:
            raise HosmartError(f"Implausible property count {count}")
        return count

    @staticmethod
    def _values_request(indices: list[int]) -> bytes:
        packed = b"".join(_encode_varint(index) for index in indices)
        cmd = _field_bytes(1, packed)
        return _field_varint(1, 4) + _field_bytes(12, cmd)

    @staticmethod
    def _parse_values_response(data: bytes) -> list[dict[str, Any]]:
        outer = _parse_fields(data)
        payload = _bytes_value(outer, 13)
        if payload is None:
            raise HosmartError("Property-values response missing")

        response = _parse_fields(payload)
        if _int_value(response, 1, 0) != 0:
            raise HosmartError("Receiver rejected property-values request")

        properties: list[dict[str, Any]] = []
        for number, wire, raw_prop in response:
            if number != 2 or wire != 2 or not isinstance(raw_prop, bytes):
                continue
            prop = _parse_fields(raw_prop)
            name_raw = _bytes_value(prop, 2) or b""
            value = _bytes_value(prop, 5) or b""
            properties.append(
                {
                    "name": name_raw.decode("utf-8", errors="replace"),
                    "type": _int_value(prop, 3, 0),
                    "flags": _int_value(prop, 4, 0),
                    "status": _int_value(prop, 1, 0),
                    "value": value,
                }
            )
        return properties

    def _get_count(self) -> int:
        encrypted = self._crypt(self._count_request())
        response = self._post("/esp_local_ctrl/control", encrypted)
        return self._parse_count_response(self._crypt(response))

    def _get_values(self, indices: list[int]) -> list[dict[str, Any]]:
        encrypted = self._crypt(self._values_request(indices))
        response = self._post("/esp_local_ctrl/control", encrypted)
        return self._parse_values_response(self._crypt(response))

    @staticmethod
    def _decode_json_property(prop: dict[str, Any]) -> dict[str, Any]:
        try:
            decoded = prop["value"].decode("utf-8")
            value = json.loads(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as err:
            raise HosmartError(f"Invalid JSON in property {prop['name']}") from err
        if not isinstance(value, dict):
            raise HosmartError(f"Property {prop['name']} did not contain an object")
        return value

    def _discover_properties(self) -> dict[str, Any]:
        self._establish_session()
        count = self._get_count()
        props = self._get_values(list(range(count)))

        self._property_indexes = {
            prop["name"]: index for index, prop in enumerate(props) if prop["name"]
        }
        by_name = {prop["name"]: prop for prop in props}

        if "config" not in by_name or "params" not in by_name:
            raise HosmartError("Receiver did not expose config and params properties")

        self._config = self._decode_json_property(by_name["config"])
        params = self._decode_json_property(by_name["params"])
        return self._snapshot(params)

    def _snapshot(self, params: dict[str, Any]) -> dict[str, Any]:
        info = self._config.get("info") or {}
        return {
            "node_id": self._config.get("node_id"),
            "model": info.get("model"),
            "fw_version": info.get("fw_version"),
            "platform": info.get("platform"),
            "config": self._config,
            "params": params,
        }

    def _read_current(self) -> dict[str, Any]:
        if self._cipher is None or "params" not in self._property_indexes:
            return self._discover_properties()

        index = self._property_indexes["params"]
        props = self._get_values([index])
        if not props or props[0]["name"] != "params":
            return self._discover_properties()
        params = self._decode_json_property(props[0])
        return self._snapshot(params)

    def read_snapshot(self) -> dict[str, Any]:
        """Read current receiver state, reconnecting once if needed."""
        try:
            return self._read_current()
        except HosmartAuthenticationError:
            self.close()
            raise
        except (HosmartError, OSError, socket.error, http.client.HTTPException) as err:
            _LOGGER.debug("Hosmart local session reset after error: %s", err)
            self.close()
            try:
                return self._discover_properties()
            except HosmartAuthenticationError:
                self.close()
                raise
            except Exception as retry_err:
                self.close()
                if isinstance(retry_err, HosmartError):
                    raise
                raise HosmartConnectionError(str(retry_err)) from retry_err
