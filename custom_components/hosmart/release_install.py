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
    """Find exactly this repository's update entity in HACS or Marketplace.

    Both providers use the GitHub repository ID for update entity unique_id.
    No fuzzy matching by name/title; other projects must never be updated.
    """
    registry = er.async_get(hass)
    for platform in ("marketplace", "hacs"):
        entity_id = registry.async_get_entity_id(
            "update", platform, "1393997438"
        )
        if entity_id is None:
            continue
        state = hass.states.get(entity_id)
        if state is None:
            continue
        features = int(state.attributes.get("supported_features", 0))
        if not features & int(UpdateEntityFeature.SPECIFIC_VERSION):
            raise HomeAssistantError(
                "The Marketplace update entity does not support specific "
                "versions. Update the Marketplace/HACS before retrying."
            )
        return entity_id
    raise HomeAssistantError(
        "The Ho-Smart & eMACROS HACS/Marketplace update entity is unavailable. "
        "Verify that the repository is installed and its update entity is enabled."
    )

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
