"""Safely request a user-selected stable or development release via HACS.

This integration NEVER writes to custom_components itself. HACS is the
installer, and the user must press the explicit install button.
"""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientTimeout
from homeassistant.components.update import UpdateEntityFeature
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

from .release_versions import (
    CHANNELS,
    RELEASE_CHANNEL_DEV,
    RELEASE_CHANNEL_MAIN,
    latest_tag_for_channel,
)

REPOSITORY = "gigabytegrove/hosmart-home-assistant"
RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases?per_page=30"


def find_hacs_update_entity(hass: Any) -> str:
    """Locate the HACS-managed update entity, never an unrelated updater."""
    registry = er.async_get(hass)
    matches: list[str] = []
    for item in registry.entities.values():
        if item.domain != "update" or item.platform != "hacs":
            continue
        state = hass.states.get(item.entity_id)
        if state is None:
            continue
        properties = state.attributes
        title = str(properties.get("title") or "")
        name = str(properties.get("friendly_name") or "")
        release_url = str(properties.get("release_url") or "")
        unique = str(item.unique_id or "")
        if (
            REPOSITORY in release_url
            or REPOSITORY in unique
            or ("Ho-Smart" in title and "eMACROS" in title)
            or ("Ho-Smart" in name and "eMACROS" in name)
            or ("Ho-Smart" in title and "Home Assistant" in title)
        ):
            matches.append(item.entity_id)
    if len(matches) != 1:
        raise HomeAssistantError(
            "Cannot identify the HACS update entity for Ho-Smart & eMACROS. "
            "Use HACS > Ho-Smart & eMACROS > Redownload > "
            "Need a different version to select a stable or beta release."
        )
    entity_id = matches[0]
    state = hass.states.get(entity_id)
    features = int(state.attributes.get("supported_features", 0))
    if not features & int(UpdateEntityFeature.INSTALL_SPECIFIC_VERSION):
        raise HomeAssistantError(
            "The installed HACS update entity does not support selecting "
            "a specific release version. Use HACS > Redownload instead."
        )
    return entity_id


async def async_latest_published_tag(hass: Any, channel: str) -> str:
    """Read the authenticated-by-TLS public GitHub release index."""
    try:
        session = async_get_clientsession(hass)
        async with session.get(
            RELEASE_API,
            headers={"Accept": "application/vnd.github+json"},
            timeout=ClientTimeout(total=15),
            allow_redirects=False,
        ) as response:
            if response.status != 200:
                raise HomeAssistantError(
                    f"Cannot read GitHub releases (HTTP {response.status})"
                )
            releases = await response.json(content_type=None)
    except HomeAssistantError:
        raise
    except Exception as err:
        raise HomeAssistantError(
            f"Cannot retrieve Ho-Smart release information: {err}"
        ) from err
    try:
        return latest_tag_for_channel(releases, channel)
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err


async def async_install_channel(hass: Any, channel: str) -> str:
    """Request HACS to install the selected published version.

    No hidden code overwrite, no automatic restart, and no claim of success
    beyond HACS accepting/completing its update action.
    """
    entity_id = find_hacs_update_entity(hass)
    tag = await async_latest_published_tag(hass, channel)
    if not hass.services.has_service("update", "install"):
        raise HomeAssistantError("Home Assistant update.install is unavailable")
    _LOGGER.info(
        "Requesting HACS installation of Ho-Smart %s via %s", tag, entity_id
    )
    try:
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": entity_id, "version": tag},
            blocking=True,
        )
    except Exception as err:
        raise HomeAssistantError(
            f"HACS did not complete the installation request for {tag}: {err}"
        ) from err
    return tag
