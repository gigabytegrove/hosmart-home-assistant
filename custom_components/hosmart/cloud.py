"""Ho-Smart account onboarding and cloud-alert helpers.

The My Hosmart Android app uses the ESP RainMaker account API for identity/node
metadata and a separate Ho-Smart notice endpoint for alarm history.

Passwords and access tokens are onboarding-only. Runtime alarm checks require
only the Ho-Smart user_id and node_id.
"""

from __future__ import annotations

import json
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://0pnvdekd48.execute-api.us-west-2.amazonaws.com/dev/v1"
HISTORY_URL = (
    "https://qzjrkb1rpe.execute-api.us-west-2.amazonaws.com"
    "/prod/notice/query/page"
)


class HosmartCloudError(Exception):
    """Base Ho-Smart cloud error."""


class HosmartCloudAuthError(HosmartCloudError):
    """Account authentication failed."""


def _unwrap(value: Any) -> Any:
    if isinstance(value, dict) and "body" in value:
        body = value["body"]
        if isinstance(body, dict):
            return body
        if isinstance(body, str):
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return value
    return value


def _request_json(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    token: str | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    data = None

    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"

    if token:
        headers["Content-Type"] = "application/json"
        headers["Authorization"] = token

    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        if err.code in (401, 403):
            raise HosmartCloudAuthError("Ho-Smart account authentication failed") from err
        raise HosmartCloudError(f"Ho-Smart cloud returned HTTP {err.code}") from err
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as err:
        raise HosmartCloudError(f"Could not communicate with Ho-Smart cloud: {err}") from err

    decoded = _unwrap(decoded)
    if not isinstance(decoded, dict):
        raise HosmartCloudError("Unexpected Ho-Smart cloud response")
    return decoded


def _fetch_nodes(token: str) -> list[dict[str, Any]]:
    """Return all detailed nodes using the same pagination as My Hosmart."""
    all_nodes: list[dict[str, Any]] = []
    start_id: str | None = None

    while True:
        query: dict[str, str] = {"node_details": "true"}
        if start_id:
            query["start_id"] = start_id

        response = _request_json(
            BASE_URL + "/user/nodes?" + urllib.parse.urlencode(query),
            token=token,
        )

        details = response.get("node_details", [])
        if isinstance(details, list):
            all_nodes.extend(node for node in details if isinstance(node, dict))

        next_id = response.get("next_id")
        if not isinstance(next_id, str) or not next_id:
            break
        start_id = next_id

    return all_nodes


def _receiver_params(node: dict[str, Any]) -> dict[str, Any]:
    params = node.get("params")
    if not isinstance(params, dict):
        return {}

    receiver = params.get("Receiver")
    if isinstance(receiver, dict):
        return receiver

    config = node.get("config")
    if isinstance(config, dict):
        devices = config.get("devices")
        if isinstance(devices, list):
            for device in devices:
                if not isinstance(device, dict):
                    continue
                name = device.get("name")
                if isinstance(name, str) and isinstance(params.get(name), dict):
                    return params[name]
    return {}


def _normalise_node(node: dict[str, Any]) -> dict[str, Any]:
    params = node.get("params") if isinstance(node.get("params"), dict) else {}
    local_control = params.get("Local Control")
    if not isinstance(local_control, dict):
        local_control = {}

    receiver = _receiver_params(node)
    node_id = node.get("id") or node.get("node_id")
    name = receiver.get("Name") or node.get("name") or node_id or "Ho-Smart"

    return {
        "node_id": str(node_id) if node_id is not None else None,
        "name": str(name),
        "pop": (
            str(local_control.get("POP"))
            if local_control.get("POP") not in (None, "")
            else None
        ),
        "security_type": local_control.get("Type"),
        "params": params,
        "receiver": receiver,
        "config": node.get("config") if isinstance(node.get("config"), dict) else {},
    }


def get_account_setup(
    username: str,
    password: str,
) -> dict[str, Any]:
    """Authenticate and return the user id plus account nodes.

    This reproduces the My Hosmart 1.4.9.3 login flow:
      POST /login2
      GET  /user2?custom_data=true
      GET  /user/nodes?node_details=true

    Password/access token are intentionally not returned.
    """
    login = _request_json(
        BASE_URL + "/login2",
        method="POST",
        body={
            "user_name": username.strip().lower(),
            "password": password,
        },
    )

    token = login.get("accesstoken")
    if not isinstance(token, str) or not token:
        raise HosmartCloudAuthError("Ho-Smart login did not return an access token")

    user = _request_json(
        BASE_URL + "/user2?custom_data=true",
        token=token,
    )
    user_id = user.get("user_id")
    if not isinstance(user_id, str) or not user_id:
        raise HosmartCloudError("Ho-Smart account did not return a user_id")

    nodes = [_normalise_node(node) for node in _fetch_nodes(token)]
    nodes = [node for node in nodes if node.get("node_id")]

    return {
        "user_id": user_id,
        "nodes": nodes,
    }


def get_local_control_nodes(
    username: str,
    password: str,
) -> list[dict[str, Any]]:
    """Compatibility helper returning nodes with usable local-control metadata."""
    setup = get_account_setup(username, password)
    return [
        node
        for node in setup["nodes"]
        if node.get("pop") and node.get("security_type") is not None
    ]


def query_history(
    user_id: str,
    start_ms: int,
    end_ms: int,
    *,
    max_pages: int = 50,
) -> list[dict[str, Any]]:
    """Query Ho-Smart notice history using the app's exact request format."""
    records: list[dict[str, Any]] = []
    last_key: Any = ""

    for _ in range(max_pages):
        response = _request_json(
            HISTORY_URL,
            method="POST",
            body={
                "user_id": user_id,
                "startTime": int(start_ms),
                "endTime": int(end_ms),
                "pageSize": 20,
                "startKeyJson": last_key,
            },
            timeout=15,
        )

        data = response.get("data") or []
        if isinstance(data, list):
            records.extend(record for record in data if isinstance(record, dict))

        next_key = response.get("lastKey")
        if not next_key:
            break
        last_key = next_key

    return records


def history_record_key(record: dict[str, Any]) -> str:
    """Return a stable de-duplication key for a notice-history record."""
    delkey = record.get("delkey")
    if delkey:
        return str(delkey)

    return "|".join(
        (
            str(record.get("msgtime") or ""),
            str(record.get("node_id") or record.get("nodeId") or ""),
            str(record.get("message_body") or ""),
        )
    )


def parse_activity(record: dict[str, Any]) -> dict[str, Any] | None:
    """Extract a receiver activity from a Ho-Smart notice record."""
    node_id = record.get("node_id") or record.get("nodeId")
    message = record.get("message_body")
    payload = record.get("event_data_payload")

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = None

    event = None
    channel = None
    channel_name = None

    if isinstance(payload, dict):
        receiver = payload.get("Receiver")
        if isinstance(receiver, dict):
            event = receiver.get("Event")
            channel = receiver.get("Channel")
            channel_name = receiver.get("ChannelName")

    # Verified HS006W history format:
    #   Alert! GG Sensor Reported Driveway:Alarm
    if isinstance(message, str) and " Reported " in message:
        reported = message.split(" Reported ", 1)[1].strip()
        if ":" in reported:
            parsed_channel, parsed_event = reported.rsplit(":", 1)
            if not channel_name:
                channel_name = parsed_channel.strip()
            if not event:
                event = parsed_event.strip()

    if not event and not channel_name:
        return None

    msgtime = record.get("msgtime")
    try:
        msgtime_ms = int(msgtime)
    except (TypeError, ValueError):
        msgtime_ms = None

    return {
        "node_id": str(node_id) if node_id is not None else None,
        "event": event,
        "channel": channel,
        "channel_name": channel_name,
        "msgtime_ms": msgtime_ms,
        "message": message,
        "record_key": history_record_key(record),
    }
