"""Config flow for Ho-Smart / eMACROS."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

try:
    import probatio as pvol
except ImportError:
    # Core before 2026.11 lacks conditional form-field support.
    pvol = vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.config_entries import ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
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
    CHANNEL_ALWAYS_ACTIVE,
    CHANNEL_CUSTOM,
    CHANNEL_INHERIT,
    CONF_CHANNEL_NAMES,
    CONF_CHANNEL_QUIET,
    CONF_MODE,
    CONF_NODE_ID,
    CONF_POP,
    CONF_QUIET_ACTION,
    CONF_QUIET_ENABLED,
    CONF_QUIET_END,
    CONF_QUIET_START,
    CONF_RELEASE_CHANNEL,
    CONF_USER_ID,
    DEFAULT_MODE,
    DEFAULT_PORT,
    DEFAULT_QUIET_ACTION,
    DEFAULT_QUIET_END,
    DEFAULT_QUIET_START,
    DOMAIN,
    MODE_CLOUD,
    MODE_HYBRID,
    MODE_LOCAL,
)
from .night_schedule import parse_time
from .settings import merge_schedule_section, updated_quiet_options


UPDATE_CHANNEL_OPTIONS = [
    {"value": "main", "label": "Main — stable releases"},
    {"value": "dev", "label": "Development — nightly prereleases"},
]


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
    """Handle a config flow for Ho-Smart / eMACROS."""

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
            "No Ho-Smart / eMACROS account device matched this local receiver"
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
                        or "Ho-Smart / eMACROS"
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
                        options={
                            CONF_MODE: mode,
                            CONF_RELEASE_CHANNEL: user_input[CONF_RELEASE_CHANNEL],
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
                vol.Required(CONF_MODE, default=DEFAULT_MODE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=MODE_OPTIONS,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_RELEASE_CHANNEL, default="main"
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=UPDATE_CHANNEL_OPTIONS,
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
    """One form with Default, Ch. 1–4 sections and connection mode.

    Unlike the obsolete sequential wizard, every channel is configurable
    before a single Save. Existing per-channel settings are read unchanged.
    """

    _pending_mode: str | None = None
    _pending_options: dict[str, Any] | None = None

    @staticmethod
    def _conditional_field(
        name: str,
        default: Any,
        *,
        depends_on: str,
        value: Any,
    ) -> Any:
        """Hide and disable irrelevant fields on Home Assistant 2026.11+.

        Older HA versions have no conditional field API, so their forms
        retain visible fields for backwards compatibility.
        """
        required = getattr(data_entry_flow, "Required", None)
        if required is None:
            return vol.Required(name, default=default)
        return required(
            name, default=default, visible={"field": depends_on, "value": value}
        )

    @staticmethod
    def _mode_selector() -> selector.SelectSelector:
        return selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=MODE_OPTIONS,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )

    @staticmethod
    def _action_selector(*, default: bool) -> selector.SelectSelector:
        options = [
            {"value": "disarm", "label": "Disarm zone during window"},
            {"value": "arm", "label": "Arm zone during window"},
        # A physical channel-tone mute is not a verified HS006W capability.
        # Do not offer a nonfunctional choice that could be mistaken for
        # an active zone disarm or real receiver audio suppression.
        ]
        if default:
            options.extend(
                [
                    {
                        "value": "mute",
                        "label": "Mute ALL receiver audio (legacy)",
                    },
                    {
                        "value": "power_off",
                        "label": "Power off ALL channels (legacy)",
                    },
                ]
            )
        return selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=options,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )

    def _section_data(
        self, section_name: str, submitted: dict[str, Any],
    ) -> dict[str, Any]:
        options = self.config_entry.options
        values = submitted.get(section_name, {})
        return values if isinstance(values, dict) else {}

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Present all five independent collapsible sections in one form."""
        old = self.config_entry.options
        current_mode = old.get(
            CONF_MODE,
            MODE_LOCAL if CONF_USER_ID not in self.config_entry.data else DEFAULT_MODE,
        )
        provided = user_input or {}
        errors: dict[str, str] = {}

        if user_input is not None:
            options = dict(old)
            default = provided.get("default", {})
            if not isinstance(default, dict):
                errors["base"] = "invalid_schedule"
            else:
                try:
                    # Build all fields first. Validating each time picker
                    # separately would reject a legal Start/End pair if one
                    # intermediate value happened to equal the previous end.
                    merged_default = merge_schedule_section(
                        {
                            "enabled": options.get(CONF_QUIET_ENABLED, False),
                            "action": options.get(
                                CONF_QUIET_ACTION, DEFAULT_QUIET_ACTION
                            ),
                            "start": options.get(
                                CONF_QUIET_START, DEFAULT_QUIET_START
                            ),
                            "end": options.get(
                                CONF_QUIET_END, DEFAULT_QUIET_END
                            ),
                        },
                        default,
                    )
                    options.update(
                        {
                            CONF_QUIET_ENABLED: merged_default["enabled"],
                            CONF_QUIET_ACTION: merged_default["action"],
                            CONF_QUIET_START: merged_default["start"],
                            CONF_QUIET_END: merged_default["end"],
                        }
                    )
                    rules = options.get(CONF_CHANNEL_QUIET, {})
                    rules = {
                        key: dict(value) for key, value in rules.items()
                        if isinstance(key, str) and isinstance(value, dict)
                    } if isinstance(rules, dict) else {}
                    for index in range(1, 5):
                        values = provided[f"ch{index}"]
                        saved = rules.get(str(index), {})
                        rules[str(index)] = merge_schedule_section(
                            saved, values, channel=index
                        )
                    options[CONF_CHANNEL_QUIET] = rules
                    selected_mode = provided[CONF_MODE]
                    options[CONF_MODE] = selected_mode
                    release_channel = provided[CONF_RELEASE_CHANNEL]
                    if release_channel not in ("main", "dev"):
                        raise ValueError("Unknown integration update channel")
                    options[CONF_RELEASE_CHANNEL] = release_channel
                    # Check mode after merging all fields; a Cloud-only
                    # transition cannot abandon pending local restoration.
                    options = updated_quiet_options(
                        options, key=CONF_QUIET_ENABLED,
                        value=options.get(CONF_QUIET_ENABLED, False),
                    )
                    runtime = self.hass.data.get(DOMAIN, {}).get(
                        self.config_entry.entry_id
                    )
                    quiet = runtime.get("quiet") if runtime else None
                    if selected_mode == MODE_CLOUD and getattr(quiet, "_managed", {}):
                        raise ValueError(
                            "Restore existing local schedule changes before "
                            "switching to Cloud-only mode"
                        )
                except (KeyError, TypeError, ValueError) as err:
                    errors["base"] = "invalid_schedule"
            if not errors:
                if options == dict(old):
                    return self.async_create_entry(data=options)
                if (
                    options[CONF_MODE] in (MODE_CLOUD, MODE_HYBRID)
                    and not self.config_entry.data.get(CONF_USER_ID)
                ):
                    self._pending_mode = options[CONF_MODE]
                    self._pending_options = options
                    return await self.async_step_cloud_credentials()
                return self.async_create_entry(data=options)

        default_saved = self._section_data("default", provided)
        default_schema = pvol.Schema(
            {
                pvol.Required(
                    "enabled",
                    default=default_saved.get(
                        "enabled", old.get(CONF_QUIET_ENABLED, False)
                    ),
                ): selector.BooleanSelector(),
                self._conditional_field(
                    "action",
                    default_saved.get(
                        "action", old.get(CONF_QUIET_ACTION, DEFAULT_QUIET_ACTION)
                    ),
                    depends_on="enabled",
                    value=True,
                ): self._action_selector(default=True),
                self._conditional_field(
                    "start",
                    default_saved.get(
                        "start", old.get(CONF_QUIET_START, DEFAULT_QUIET_START)
                    ),
                    depends_on="enabled",
                    value=True,
                ): selector.TimeSelector(),
                self._conditional_field(
                    "end",
                    default_saved.get(
                        "end", old.get(CONF_QUIET_END, DEFAULT_QUIET_END)
                    ),
                    depends_on="enabled",
                    value=True,
                ): selector.TimeSelector(),
            }
        )

        fields: dict[Any, Any] = {
            pvol.Required("default"): section(
                default_schema, {"collapsed": False}
            ),
        }
        rules = old.get(CONF_CHANNEL_QUIET, {})
        if not isinstance(rules, dict):
            rules = {}
        for index in range(1, 5):
            name = f"ch{index}"
            submitted = self._section_data(name, provided)
            saved = rules.get(str(index), {})
            if not isinstance(saved, dict):
                saved = {}
            schema = pvol.Schema(
                {
                    pvol.Required(
                        "mode",
                        default=submitted.get(
                            "mode", saved.get("mode", CHANNEL_INHERIT)
                        ),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {
                                    "value": CHANNEL_INHERIT,
                                    "label": "Use Default",
                                },
                                {
                                    "value": CHANNEL_ALWAYS_ACTIVE,
                                    "label": "Off (no schedule; keep current zone state)",
                                },
                                {
                                    "value": CHANNEL_CUSTOM,
                                    "label": "Use this channel's schedule",
                                },
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    self._conditional_field(
                        "action",
                        submitted.get(
                            "action", saved.get("action", "disarm")
                        ),
                        depends_on="mode",
                        value=CHANNEL_CUSTOM,
                    ): self._action_selector(default=False),
                    self._conditional_field(
                        "start",
                        submitted.get(
                            "start", saved.get("start", DEFAULT_QUIET_START)
                        ),
                        depends_on="mode",
                        value=CHANNEL_CUSTOM,
                    ): selector.TimeSelector(),
                    self._conditional_field(
                        "end",
                        submitted.get(
                            "end", saved.get("end", DEFAULT_QUIET_END)
                        ),
                        depends_on="mode",
                        value=CHANNEL_CUSTOM,
                    ): selector.TimeSelector(),
                }
            )
            fields[pvol.Required(name)] = section(
                schema, {"collapsed": True}
            )

        fields[pvol.Required(
            CONF_MODE, default=provided.get(CONF_MODE, current_mode)
        )] = self._mode_selector()
        fields[pvol.Required(
            CONF_RELEASE_CHANNEL,
            default=provided.get(
                CONF_RELEASE_CHANNEL, old.get(CONF_RELEASE_CHANNEL, "main")
            ),
        )] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=UPDATE_CHANNEL_OPTIONS,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )
        return self.async_show_form(
            step_id="init",
            data_schema=pvol.Schema(fields),
            errors=errors,
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
                        data=self._pending_options or {
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
