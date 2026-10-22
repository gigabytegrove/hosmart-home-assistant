# Changelog

## 0.2.5

- Replace repeated one-off HTTPS cloud-history connections with Home Assistant's managed, keep-alive aiohttp session and DNS cache.
- Retry transient cloud DNS, TCP/TLS, response timeout, invalid JSON, HTTP 429, and HTTP 5xx failures once with a short backoff; fail fast on authentication and certificate verification errors.
- Split low-latency alarm polling (3-minute window, every 3 seconds) from complete cloud-history reconciliation (hour-overlap catch-up, once a minute). Continue from the persisted reconciliation checkpoint across outages/restarts instead of advancing its cursor on incomplete responses.
- Retain all-or-nothing pagination validation, limit oversized responses, and expose categorized transport errors, retries, request latency, and reconciliation statistics in diagnostics.
- Retry intermittent local receiver connection failures once without hiding authentication errors.
- Immediately publish the driveway motion ON transition while cloud pagination is still processing. Suppress spurious live alarms from cloud records with malformed timestamps.
- No DNS, firewall, receiver configuration, accounts, or credentials are changed.


## 0.2.4

- Add restart-safe alarm recovery with an atomic, per-device cursor and cloud notice deduplication checkpoint.
- Expand cloud-history overlap to one hour so delayed vendor uploads are not silently missed after otherwise successful polls.
- Reject cloud pagination loops and truncated history, preserving the checkpoint for the next successful reconciliation.
- Preserve the v0.2.3 channel-one motion pulse and prevent stale recovered notices from triggering automations.
- No new credentials, onboarding, or settings required.


## 0.2.3

- Recovers cloud history using the last successful query time rather than permanently skipping events after a three-minute outage.
- Uses a full 10-second receipt-time motion pulse with an independent expiration callback, fixing late cloud delivery hiding fresh activity.
- Marks recovered notices older than two minutes as historical to avoid false live-motion alerts and records their count in diagnostics.
- Prevents older recovered events from overwriting newer activity and restricts driveway motion to channel one.
- Adds a cloud reporting connectivity diagnostic sensor, last successful cloud poll, and last received live alarm time.
- Does not require account or receiver reconfiguration. Manufacturer cloud events absent from all receiver interfaces cannot be reconstructed.


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
