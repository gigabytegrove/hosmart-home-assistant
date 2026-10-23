#!/usr/bin/env python3
"""Fail validation when Ho-Smart release-facing documentation falls behind.

Only the standard library is required. Both normal validation and release
publication run this guard before accepting a new integration version.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "custom_components" / "hosmart" / "manifest.json"
README = ROOT / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"

VERSION_LINE = re.compile(
    r"^\*\*Current integration version: v(\d+\.\d+\.\d+)\*\*\s*$",
    re.MULTILINE,
)
CHANGELOG_VERSION = re.compile(r"^##\s+(\d+\.\d+\.\d+)\s*$", re.MULTILINE)
STALE_CLAIMS = (
    re.compile(
        r"\bv(\d+\.\d+\.\d+)\s+(?:is|remains)\s+"
        r"(?:the\s+)?(?:current|latest)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:current|latest)\s+(?:stable\s+)?"
        r"(?:release|version|baseline)\s*[:\-–]\s*v(\d+\.\d+\.\d+)\b",
        re.IGNORECASE,
    ),
)


def validate(version: str, readme: str, changelog: str) -> list[str]:
    """Compare canonical version, README current-version claim, and changelog."""
    issues: list[str] = []
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        return [f"Invalid manifest version: {version!r}"]

    current = VERSION_LINE.findall(readme)
    if len(current) != 1:
        issues.append(
            "README.md must contain exactly one bold line formatted "
            f"'**Current integration version: v{version}**' "
            f"(found {len(current)})."
        )
    elif current[0] != version:
        issues.append(
            f"README.md advertises v{current[0]} but manifest is v{version}."
        )

    change_versions = CHANGELOG_VERSION.findall(changelog)
    if not change_versions:
        issues.append("CHANGELOG.md has no recognized '## X.Y.Z' release heading.")
    elif change_versions[0] != version:
        issues.append(
            f"CHANGELOG.md starts with v{change_versions[0]} "
            f"but manifest is v{version}."
        )

    if "https://github.com/gigabytegrove/hosmart-home-assistant/releases/latest" not in readme:
        issues.append("README.md must link to the authoritative latest release.")

    for pattern in STALE_CLAIMS:
        for match in pattern.finditer(readme):
            if match.group(1) != version:
                issues.append(
                    f"README.md has a stale 'current/latest' claim for "
                    f"v{match.group(1)}; expected v{version}."
                )

    return sorted(set(issues))


def main() -> int:
    version = json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]
    issues = validate(
        version,
        README.read_text(encoding="utf-8"),
        CHANGELOG.read_text(encoding="utf-8"),
    )
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}", file=sys.stderr)
        return 1
    print(f"PASS: README, changelog and manifest agree on v{version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
