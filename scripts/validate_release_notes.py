"""Enforce meaningful, version-specific GitHub Release notes.

Run before any release is published, never fall back to generated notes.
Only standard-library dependencies, for CI and local verification.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
NOTES_DIR = ROOT / ".github" / "release-notes"
MANIFEST = ROOT / "custom_components" / "hosmart" / "manifest.json"
RELEASE_NAME = re.compile(r"^v(\d+\.\d+\.\d+)\.md$")
H1 = re.compile(r"^#\s+Ho-Smart v(\d+\.\d+\.\d+)\b", re.I)
HEADING = re.compile(r"^##\s+(.+)$", re.M)


def validate_notes(path: Path) -> list[str]:
    """Return reasons a release's GitHub-facing description is inadequate."""
    failures: list[str] = []
    version_match = RELEASE_NAME.fullmatch(path.name)
    if version_match is None:
        return [f"Invalid filename: {path.name} (expected vX.Y.Z.md)"]
    version = version_match.group(1)
    body = path.read_text(encoding="utf-8")
    meaningful_lines = [line.strip() for line in body.splitlines() if line.strip()]
    first = meaningful_lines[0] if meaningful_lines else ""
    title_match = H1.match(first)
    if title_match is None or title_match.group(1) != version:
        failures.append(f"{path.name}: title must name its exact release version")
    if len(body.strip()) < 450:
        failures.append(f"{path.name}: add a substantive explanation (450+ characters)")
    if not re.search(r"\*\*Focus:\*\*\s*\S", body):
        failures.append(f"{path.name}: include a concrete **Focus:** statement")
    headings = [heading.casefold() for heading in HEADING.findall(body)]
    if not any("why" in heading or "purpose" in heading for heading in headings):
        failures.append(f"{path.name}: explain why this release exists")
    if not any("changed" in heading or "improvement" in heading or "fix" in heading for heading in headings):
        failures.append(f"{path.name}: list meaningful fixes or improvements")
    if not any("limitation" in heading or ("does" in heading and "not" in heading) for heading in headings):
        failures.append(f"{path.name}: explain limitations of the release")
    if not any("installation" in heading or "upgrade" in heading for heading in headings):
        failures.append(f"{path.name}: give installation/upgrade instructions")
    if len(re.findall(r"^\s*[-*]\s+", body, flags=re.M)) < 2:
        failures.append(f"{path.name}: describe at least two concrete changes")
    changelog_lines = [
        index for index, line in enumerate(meaningful_lines)
        if "full changelog" in line.casefold() or
        ("changes since" in line.casefold() and "compare/" in line)
    ]
    if changelog_lines and changelog_lines[-1] != len(meaningful_lines) - 1:
        failures.append(f"{path.name}: the optional full changelog must be last")
    if len(changelog_lines) > 1:
        failures.append(f"{path.name}: only one full changelog reference is permitted")
    return failures


def main() -> int:
    version = json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]
    expected = NOTES_DIR / f"v{version}.md"
    errors: list[str] = []
    if not expected.is_file():
        errors.append(
            f"Release blocked: {expected.relative_to(ROOT)} is missing. "
            "Every release requires its own purpose and change description."
        )
    for path in sorted(NOTES_DIR.glob("v*.md")):
        errors.extend(validate_notes(path))
    if errors:
        for problem in errors:
            print(f"ERROR: {problem}", file=sys.stderr)
        return 1
    print(f"PASS: detailed release notes validated for v{version} "
          f"({len(list(NOTES_DIR.glob('v*.md')))} versions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
