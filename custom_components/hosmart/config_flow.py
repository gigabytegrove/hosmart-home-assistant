"""Config flow for Hosmart."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import selector

from .client import (
    HosmartAuthenticationError,
    HosmartClient,
    HosmartConnectionError,
    HosmartError,
)
from .const import CONF_POP, DEFAULT_PORT, DOMAIN


class HosmartConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hosmart."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Set up a receiver from local connection details."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input[CONF_PORT]
            pop = user_input[CONF_POP].strip()

            client = HosmartClient(host, port, pop)
            try:
                snapshot = await self.hass.async_add_executor_job(
                    client.read_snapshot
                )
            except HosmartAuthenticationError:
                errors["base"] = "invalid_auth"
            except (HosmartConnectionError, HosmartError, OSError):
                errors["base"] = "cannot_connect"
            else:
                node_id = snapshot.get("node_id")
                receiver = (snapshot.get("params") or {}).get("Receiver") or {}
                title = receiver.get("Name") or snapshot.get("model") or "Hosmart"

                if node_id:
                    await self.async_set_unique_id(str(node_id))
                    self._abort_if_unique_id_configured(
                        updates={CONF_HOST: host, CONF_PORT: port}
                    )

                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_POP: pop,
                    },
                )
            finally:
                await self.hass.async_add_executor_job(client.close)

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): selector.TextSelector(),
                vol.Required(
                    CONF_PORT, default=DEFAULT_PORT
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=65535,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(CONF_POP): selector.TextSelector(
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
