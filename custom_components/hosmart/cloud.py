"""Ho-Smart cloud onboarding helpers.

The cloud is used only during config flow to retrieve the receiver's Local
Control metadata. Runtime communication remains fully local.
"""

from __future__ import annotations

import json
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://0pnvdekd48.execute-api.us-west-2.amazonaws.com/dev/v1"


class HosmartCloudError(Exception):
    """Base Ho-Smart cloud onboarding error."""


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
) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    data = None

    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"

    if token:
        headers["Authorization"] = token

    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
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


def get_local_control_nodes(
    username: str,
    password: str,
) -> list[dict[str, Any]]:
    """Return account nodes that expose Local Control credentials."""
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

    local_nodes: list[dict[str, Any]] = []
    for node in all_nodes:
        params = node.get("params")
        if not isinstance(params, dict):
            continue

        local_control = params.get("Local Control")
        if not isinstance(local_control, dict):
            continue

        pop = local_control.get("POP")
        security_type = local_control.get("Type")

        if pop in (None, ""):
            continue

        local_nodes.append(
            {
                "node_id": node.get("id") or node.get("node_id"),
                "pop": str(pop),
                "security_type": security_type,
            }
        )

    return local_nodes
