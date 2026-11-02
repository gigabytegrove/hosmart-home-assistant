"""Pure GitHub release channel selection rules (standard-library only).

Stable uses non-prerelease tags, while dev uses only published GitHub
prereleases on the explicit versioned -dev.N track.
"""

from __future__ import annotations

import re
from typing import Any

RELEASE_CHANNEL_MAIN = "main"
RELEASE_CHANNEL_DEV = "dev"
CHANNELS = (RELEASE_CHANNEL_MAIN, RELEASE_CHANNEL_DEV)

_STABLE_RE = re.compile(r"^v\d+\.\d+\.\d+$")
_DEV_RE = re.compile(r"^v\d+\.\d+\.\d+-dev\.\d+$")


def latest_tag_for_channel(releases: Any, channel: str) -> str:
    """Return a published tag, never a guessed branch tip or unvalidated SHA."""
    if channel not in CHANNELS:
        raise ValueError("Unknown Ho-Smart software channel")
    if not isinstance(releases, list):
        raise ValueError("Invalid GitHub release response")
    for item in releases:
        if not isinstance(item, dict) or item.get("draft"):
            continue
        tag = item.get("tag_name")
        if not isinstance(tag, str):
            continue
        prerelease = bool(item.get("prerelease"))
        if channel == RELEASE_CHANNEL_MAIN and (
            not prerelease and _STABLE_RE.fullmatch(tag)
        ):
            return tag
        if channel == RELEASE_CHANNEL_DEV and (
            prerelease and _DEV_RE.fullmatch(tag)
        ):
            return tag
    raise ValueError(
        "No published stable release" if channel == RELEASE_CHANNEL_MAIN
        else "No published dev prerelease; select Main until a beta is available"
    )
