"""Config flow for Ho-Smart."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
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
    get_local_control_nodes,
)
from .const import CONF_POP, DEFAULT_PORT, DOMAIN


class HosmartConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ho-Smart."""

    VERSION = 1

    async def _async_match_receiver(
        self,
        host: str,
        port: int,
        candidates: list[dict],
    ):
        """Find the cloud node whose POP authenticates to this receiver."""
        saw_connection_error = False

        for candidate in candidates:
            # The HS006W we have verified uses Security Type 1. Do not silently
            # reinterpret another scheme as Security1.
            if candidate.get("security_type") != 1:
                continue

            pop = candidate["pop"]
            client = HosmartClient(host, port, pop)
            try:
                snapshot = await self.hass.async_add_executor_job(
                    client.read_snapshot
                )
            except HosmartAuthenticationError:
                # Correct host but wrong device POP is expected when an account
                # contains more than one Ho-Smart receiver.
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

            return snapshot, pop

        if saw_connection_error:
            raise HosmartConnectionError(
                f"Could not establish local control with {host}:{port}"
            )

        raise HosmartAuthenticationError(
            "No Ho-Smart account device matched this local receiver"
        )

    async def async_step_user(self, user_input=None):
        """Set up a receiver and retrieve its POP from the Ho-Smart account."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input[CONF_PORT])
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]

            try:
                candidates = await self.hass.async_add_executor_job(
                    get_local_control_nodes,
                    username,
                    password,
                )

                if not candidates:
                    errors["base"] = "no_local_control_devices"
                else:
                    snapshot, pop = await self._async_match_receiver(
                        host,
                        port,
                        candidates,
                    )

                    node_id = snapshot.get("node_id")
                    receiver = (snapshot.get("params") or {}).get("Receiver") or {}
                    title = (
                        receiver.get("Name")
                        or snapshot.get("model")
                        or "Ho-Smart"
                    )

                    if node_id:
                        await self.async_set_unique_id(str(node_id))
                        self._abort_if_unique_id_configured(
                            updates={CONF_HOST: host, CONF_PORT: port}
                        )

                    # Deliberately store only the local receiver details and POP.
                    # The Ho-Smart username/password are onboarding-only and are
                    # never persisted in the config entry.
                    return self.async_create_entry(
                        title=title,
                        data={
                            CONF_HOST: host,
                            CONF_PORT: port,
                            CONF_POP: pop,
                        },
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
