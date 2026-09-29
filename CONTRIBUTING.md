# Contributing

Contributions are welcome, especially fixes, documentation improvements, and support for additional Ho-Smart-compatible receivers.

## Keep changes focused

Please avoid unrelated rewrites in the same pull request. A focused change is easier to review, test, and safely release.

The current stable behavior in **v0.2.2** should be preserved unless the change specifically fixes or improves it.

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
