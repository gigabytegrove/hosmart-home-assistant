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


class HosmartConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ho-Smart."""

    VERSION = 1

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

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Set up a receiver and retrieve account/local metadata."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input[CONF_PORT])
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]
            mode = user_input[CONF_MODE]

            try:
                setup = await self.hass.async_add_executor_job(
                    get_account_setup,
                    username,
                    password,
                )
                candidates = setup["nodes"]

                if not candidates:
                    errors["base"] = "no_devices"
                else:
                    snapshot = None
                    pop = None
                    candidate = None

                    if mode in (MODE_LOCAL, MODE_HYBRID):
                        snapshot, pop, candidate = await self._async_match_receiver(
                            host,
                            port,
                            candidates,
                        )
                    else:
                        # Cloud alarm mode does not require local control at runtime.
                        # If the account has one receiver we can identify it directly.
                        # With multiple receivers, the entered host is used only once
                        # to identify the matching node without storing credentials.
                        if len(candidates) == 1:
                            candidate = candidates[0]
                            pop = candidate.get("pop")
                        else:
                            snapshot, pop, candidate = await self._async_match_receiver(
                                host,
                                port,
                                candidates,
                            )

                    assert candidate is not None
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
                    title = (
                        receiver.get("Name")
                        or candidate.get("name")
                        or "Ho-Smart"
                    )

                    if node_id:
                        await self.async_set_unique_id(str(node_id))
                        self._abort_if_unique_id_configured(
                            updates={
                                CONF_HOST: host,
                                CONF_PORT: port,
                                CONF_USER_ID: setup["user_id"],
                                CONF_NODE_ID: str(node_id),
                            }
                        )

                    data: dict[str, Any] = {
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_USER_ID: setup["user_id"],
                        CONF_NODE_ID: str(node_id),
                        CONF_CHANNEL_NAMES: _channel_names(receiver),
                    }
                    if pop:
                        data[CONF_POP] = str(pop)

                    return self.async_create_entry(
                        title=str(title),
                        data=data,
                        options={CONF_MODE: mode},
                    )

            except HosmartCloudAuthError:
                errors["base"] = "invalid_cloud_auth"
            except HosmartCloudError:
                errors["base"] = "cloud_error"
            except HosmartAuthenticationError:
                errors["base"] = "cannot_match_device"
            except (HosmartConnectionError, HosmartError, OSError):
                errors["base"] = "cannot_connect"

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): selector.TextSelector(),
                vol.Required(
                    CONF_PORT, default=DEFAULT_PORT
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=65535,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
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
