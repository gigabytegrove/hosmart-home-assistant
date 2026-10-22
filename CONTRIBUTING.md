# Contributing

Contributions are welcome, especially fixes, documentation improvements, and support for additional Ho-Smart-compatible receivers.

## Keep changes focused

Please avoid unrelated rewrites in the same pull request. A focused change is easier to review, test, and safely release.

Previously verified HS006W behavior should be preserved unless the change specifically fixes or improves it.

## Device support

Do not assume two Ho-Smart, Hosmart, or eMACROS models use the same behavior just because they look similar.

For device-specific changes, include:

- Exact model number
- Firmware version
- What was tested
- Sanitized evidence when relevant
- Any compatibility impact on already-supported devices

## Before submitting

Please:

- Run the repository validation checks.
- Keep existing functionality working outside the scope of your change.
- Update the README when user-facing behavior changes.
- Update the changelog when a release-visible behavior changes.
- Do not commit credentials, tokens, private configuration, or personal data.

## Pull requests

Describe:

- What changed
- Why it changed
- How it was tested
- Which devices or firmware versions are affected

Evidence from real hardware is preferred for protocol or device-behavior changes.

## Mandatory GitHub release notes

Every new version must include `.github/release-notes/vX.Y.Z.md`, with the version
matching `custom_components/hosmart/manifest.json`.

The **GitHub Release page itself** must explain what the update is aimed at.
Required content, in this order:

1. A descriptive title and a concise **Focus:** statement written for users.
2. **Why** the update is being made: the symptom, bug, use case, or field evidence.
3. **What changed:** concrete user-visible fixes/improvements, not only commit names.
4. **Limitations:** what it cannot resolve and what still requires real-device verification.
5. **Installation/upgrade** instructions, including restart requirements when applicable.
6. **Full changelog** comparison link *optionally*, always at the very end.

A generated release consisting only of **Full Changelog** or an unrelated list
of dependency commits is **never acceptable**. The release automation has no
`--generate-notes` fallback and CI will reject missing or incomplete notes.
Run `python scripts/validate_release_notes.py` before publishing.

A GitHub Release is not complete until its **published description** contains
these meaningful notes. Changelog links provide additional context, not the
main announcement.
