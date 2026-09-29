# Changelog

## 0.2.2

- Fixed startup failure in v0.2.1 caused by a missing `CONF_NODE_ID` import in `__init__.py`.
- Restores normal config-entry setup so existing Ho-Smart receivers can complete initialization and entities can come online.
- No credential or configuration reset is required.

## 0.2.1

- Fixed a v0.2.0 availability regression where an unexpected Ho-Smart cloud/history failure could mark the whole coordinator unavailable in Hybrid mode.
- Hybrid mode now keeps healthy local Security1 entities online when cloud alarm history is temporarily unavailable or malformed.
- Added defensive handling for invalid/missing cloud history timestamps.
- Backfills the node ID into legacy pre-v0.2.0 config entries after a successful local refresh.
- Preserves Cloud-only failure semantics: a Cloud-only entry still reports unavailable when the cloud path itself is unavailable.

## 0.2.0

- Added Hybrid, Local-only, and Cloud alarm connection modes.
- Added Ho-Smart cloud alarm-history polling and driveway-alarm events/entities.
- Added one-time credential onboarding without storing email/password/access tokens.
- Added historical activity backfill, channel-name mapping, diagnostics, and UDP/50001 capture.
- Reduced local polling from the development 4 Hz rate to 5 seconds after field testing proved alarms are not exposed in local params.
