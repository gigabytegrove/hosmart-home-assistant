"""Config flow for Ho-Smart."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .client import (
    HosmartAuthenticationError,
    HosmartClient,
    HosmartConnectionError,
    HosmartError,
)
from .cloud import (
    HosmartCloudAuthError,
    HosmartCloudError,
    get_account_setup,
)
from .const import (
    CONF_CHANNEL_NAMES,
    CONF_MODE,
    CONF_NODE_ID,
    CONF_POP,
    CONF_USER_ID,
    DEFAULT_MODE,
    DEFAULT_PORT,
    DOMAIN,
    MODE_CLOUD,
    MODE_HYBRID,
    MODE_LOCAL,
)
from .discovery import async_discover_hosts


MODE_OPTIONS = [
    {"value": MODE_HYBRID, "label": "Hybrid (local state + cloud alarms)"},
    {"value": MODE_LOCAL, "label": "Local only"},
    {"value": MODE_CLOUD, "label": "Cloud alarm mode"},
]


def _channel_names(receiver: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for index in range(1, 5):
        value = receiver.get(f"Channel{index}Name")
        if value not in (None, ""):
            result[str(index)] = str(value)
    return result


def _candidate_label(candidate: dict[str, Any]) -> str:
    name = str(candidate.get("name") or "Ho-Smart receiver")
    node_id = str(candidate.get("node_id") or "")
    return f"{name} ({node_id})" if node_id else name


class HosmartConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ho-Smart."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config-flow state."""
        self._setup: dict[str, Any] | None = None
        self._mode: str = DEFAULT_MODE
        self._discovered_matches: list[
            tuple[str, dict[str, Any], str, dict[str, Any]]
        ] = []

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "HosmartOptionsFlow":
        """Return the options flow."""
        return HosmartOptionsFlow()

    async def _async_match_receiver(
        self,
        host: str,
        port: int,
        candidates: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], str, dict[str, Any]]:
        """Find the account node whose POP authenticates to this receiver."""
        saw_connection_error = False

        for candidate in candidates:
            if candidate.get("security_type") != 1 or not candidate.get("pop"):
                continue

            pop = str(candidate["pop"])
            client = HosmartClient(host, port, pop)

            try:
                snapshot = await self.hass.async_add_executor_job(client.read_snapshot)
            except HosmartAuthenticationError:
                continue
            except (HosmartConnectionError, HosmartError, OSError):
                saw_connection_error = True
                continue
            finally:
                await self.hass.async_add_executor_job(client.close)

            expected_node = candidate.get("node_id")
            actual_node = snapshot.get("node_id")

            if expected_node and actual_node and str(expected_node) != str(actual_node):
                continue

            return snapshot, pop, candidate

        if saw_connection_error:
            raise HosmartConnectionError(
                f"Could not establish local control with {host}:{port}"
            )

        raise HosmartAuthenticationError(
            "No Ho-Smart account device matched this local receiver"
        )

    async def _async_discover_receivers(
        self,
        candidates: list[dict[str, Any]],
        port: int = DEFAULT_PORT,
    ) -> list[tuple[str, dict[str, Any], str, dict[str, Any]]]:
        """Discover and authenticate Ho-Smart receivers on enabled HA networks."""
        matches: list[tuple[str, dict[str, Any], str, dict[str, Any]]] = []

        for host in await async_discover_hosts(self.hass, port):
            try:
                snapshot, pop, candidate = await self._async_match_receiver(
                    host,
                    port,
                    candidates,
                )
            except (HosmartAuthenticationError, HosmartConnectionError):
                continue

            matches.append((host, snapshot, pop, candidate))

        return matches

    async def _async_create_receiver_entry(
        self,
        *,
        setup: dict[str, Any],
        mode: str,
        candidate: dict[str, Any],
        snapshot: dict[str, Any] | None = None,
        pop: str | None = None,
        host: str | None = None,
        port: int | None = None,
    ) -> ConfigFlowResult:
        """Create a config entry from a verified account/local receiver."""
        node_id = (
            snapshot.get("node_id")
            if snapshot is not None
            else candidate.get("node_id")
        )
        receiver = (
            (snapshot.get("params") or {}).get("Receiver") or {}
            if snapshot is not None
            else candidate.get("receiver") or {}
        )
        title = receiver.get("Name") or candidate.get("name") or "Ho-Smart"

        if node_id:
            await self.async_set_unique_id(str(node_id))
            updates: dict[str, Any] = {
                CONF_USER_ID: setup["user_id"],
                CONF_NODE_ID: str(node_id),
            }
            if host is not None:
                updates[CONF_HOST] = host
            if port is not None:
                updates[CONF_PORT] = port

            self._abort_if_unique_id_configured(updates=updates)

        data: dict[str, Any] = {
            CONF_USER_ID: setup["user_id"],
            CONF_NODE_ID: str(node_id),
            CONF_CHANNEL_NAMES: _channel_names(receiver),
        }
        if host is not None:
            data[CONF_HOST] = host
        if port is not None:
            data[CONF_PORT] = port
        if pop or candidate.get("pop"):
            data[CONF_POP] = str(pop or candidate["pop"])

        return self.async_create_entry(
            title=str(title),
            data=data,
            options={CONF_MODE: mode},
        )

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Authenticate the account and automatically locate a receiver."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]
            self._mode = user_input[CONF_MODE]

            try:
                self._setup = await self.hass.async_add_executor_job(
                    get_account_setup,
                    username,
                    password,
                )
                candidates = self._setup["nodes"]

                if not candidates:
                    errors["base"] = "no_devices"
                elif self._mode == MODE_CLOUD:
                    if len(candidates) == 1:
                        return await self._async_create_receiver_entry(
                            setup=self._setup,
                            mode=self._mode,
                            candidate=candidates[0],
                            pop=candidates[0].get("pop"),
                        )
                    return await self.async_step_select_cloud_receiver()
                else:
                    self._discovered_matches = await self._async_discover_receivers(
                        candidates,
                        DEFAULT_PORT,
                    )

                    if len(self._discovered_matches) == 1:
                        host, snapshot, pop, candidate = self._discovered_matches[0]
                        return await self._async_create_receiver_entry(
                            setup=self._setup,
                            mode=self._mode,
                            candidate=candidate,
                            snapshot=snapshot,
                            pop=pop,
                            host=host,
                            port=DEFAULT_PORT,
                        )

                    if len(self._discovered_matches) > 1:
                        return await self.async_step_select_receiver()

                    return await self.async_step_manual()

            except HosmartCloudAuthError:
                errors["base"] = "invalid_cloud_auth"
            except HosmartCloudError:
                errors["base"] = "cloud_error"

        schema = vol.Schema(
            {
                vol.Required(CONF_MODE, default=DEFAULT_MODE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=MODE_OPTIONS,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_USERNAME): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.EMAIL,
                    )
                ),
                vol.Required(CONF_PASSWORD): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.PASSWORD,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_select_receiver(self, user_input=None) -> ConfigFlowResult:
        """Let the user select one of multiple locally discovered receivers."""
        if self._setup is None or not self._discovered_matches:
            return self.async_abort(reason="discovery_expired")

        options = []
        for index, (host, _snapshot, _pop, candidate) in enumerate(
            self._discovered_matches
        ):
            options.append(
                {
                    "value": str(index),
                    "label": f"{candidate.get('name') or 'Ho-Smart receiver'} — {host}",
                }
            )

        if user_input is not None:
            selected = self._discovered_matches[int(user_input["receiver"])]
            host, snapshot, pop, candidate = selected
            return await self._async_create_receiver_entry(
                setup=self._setup,
                mode=self._mode,
                candidate=candidate,
                snapshot=snapshot,
                pop=pop,
                host=host,
                port=DEFAULT_PORT,
            )

        return self.async_show_form(
            step_id="select_receiver",
            data_schema=vol.Schema(
                {
                    vol.Required("receiver"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_select_cloud_receiver(
        self,
        user_input=None,
    ) -> ConfigFlowResult:
        """Select an account receiver when cloud-only mode has several devices."""
        if self._setup is None:
            return self.async_abort(reason="discovery_expired")

        candidates = self._setup["nodes"]
        options = [
            {
                "value": str(index),
                "label": _candidate_label(candidate),
            }
            for index, candidate in enumerate(candidates)
        ]

        if user_input is not None:
            candidate = candidates[int(user_input["receiver"])]
            return await self._async_create_receiver_entry(
                setup=self._setup,
                mode=self._mode,
                candidate=candidate,
                pop=candidate.get("pop"),
            )

        return self.async_show_form(
            step_id="select_cloud_receiver",
            data_schema=vol.Schema(
                {
                    vol.Required("receiver"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_manual(self, user_input=None) -> ConfigFlowResult:
        """Fall back to manual receiver address entry when discovery finds nothing."""
        if self._setup is None:
            return self.async_abort(reason="discovery_expired")

        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input[CONF_PORT])

            try:
                snapshot, pop, candidate = await self._async_match_receiver(
                    host,
                    port,
                    self._setup["nodes"],
                )
                return await self._async_create_receiver_entry(
                    setup=self._setup,
                    mode=self._mode,
                    candidate=candidate,
                    snapshot=snapshot,
                    pop=pop,
                    host=host,
                    port=port,
                )
            except HosmartAuthenticationError:
                errors["base"] = "cannot_match_device"
            except (HosmartConnectionError, HosmartError, OSError):
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): selector.TextSelector(),
                    vol.Required(
                        CONF_PORT,
                        default=DEFAULT_PORT,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=65535,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
            errors=errors,
        )


class HosmartOptionsFlow(OptionsFlow):
    """Configure Local / Cloud / Hybrid runtime behavior."""

    _pending_mode: str | None = None

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Choose the runtime mode."""
        current = self.config_entry.options.get(
            CONF_MODE,
            MODE_LOCAL if CONF_USER_ID not in self.config_entry.data else DEFAULT_MODE,
        )

        if user_input is not None:
            mode = user_input[CONF_MODE]

            if mode in (MODE_CLOUD, MODE_HYBRID) and not self.config_entry.data.get(
                CONF_USER_ID
            ):
                self._pending_mode = mode
                return await self.async_step_cloud_credentials()

            return self.async_create_entry(
                data={
                    **self.config_entry.options,
                    CONF_MODE: mode,
                }
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODE, default=current): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=MODE_OPTIONS,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_cloud_credentials(
        self,
        user_input=None,
    ) -> ConfigFlowResult:
        """Acquire user_id for an existing local-only config entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]

            try:
                setup = await self.hass.async_add_executor_job(
                    get_account_setup,
                    username,
                    password,
                )
                expected_node = (
                    self.config_entry.data.get(CONF_NODE_ID)
                    or self.config_entry.unique_id
                )
                candidate = next(
                    (
                        item
                        for item in setup["nodes"]
                        if str(item.get("node_id")) == str(expected_node)
                    ),
                    None,
                )
                if candidate is None:
                    errors["base"] = "cannot_match_device"
                else:
                    receiver = candidate.get("receiver") or {}
                    new_data = {
                        **self.config_entry.data,
                        CONF_USER_ID: setup["user_id"],
                        CONF_NODE_ID: str(candidate["node_id"]),
                        CONF_CHANNEL_NAMES: _channel_names(receiver),
                    }
                    if candidate.get("pop") and not new_data.get(CONF_POP):
                        new_data[CONF_POP] = str(candidate["pop"])

                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data=new_data,
                    )

                    return self.async_create_entry(
                        data={
                            **self.config_entry.options,
                            CONF_MODE: self._pending_mode or DEFAULT_MODE,
                        }
                    )

            except HosmartCloudAuthError:
                errors["base"] = "invalid_cloud_auth"
            except HosmartCloudError:
                errors["base"] = "cloud_error"

        return self.async_show_form(
            step_id="cloud_credentials",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.EMAIL,
                        )
                    ),
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        )
                    ),
                }
            ),
            errors=errors,
        )
