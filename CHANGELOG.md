# Changelog

## Unreleased — Channel quiet hours and dual-brand recognition

- Add per-channel inherit, always-active and custom start/end quiet-hours settings.
- Preserve active/protected channels by avoiding receiver-wide mute/power-off.
- Schedule targeted zone disarming, preserve previous armed values across restarts and restore after the quiet window.
- Show per-channel status diagnostics, update tests and document device write caveats.
- Clearly distinguish supported Ho-Smart and eMACROS branding from unverified device models.
- **Hardware limitation:** Zone disarming may suppress notifications as well as sound; receiver write operations require field qualification.


## 0.2.6

**Purpose:** Introduce per-receiver automated overnight quiet hours without disturbing proven cloud alarm history and local-monitoring behavior. Receiver write commands remain unverified on physical HS006W hardware; use this release's control feature cautiously.

- Add independent per-receiver enablement, configurable quiet-hours start/end, and mute or power-off choice (default 10:00 PM–7:00 AM, off until enabled).
- Restore the last observed volume/power state after the schedule ends; keep restoration intent in Home Assistant persistent storage across restarts.
- Serialize local receiver reads and writes through the existing authenticated Security1 session, require a positive protocol acknowledgement and readback, and back off failed writes.
- Add a Night quiet status diagnostic sensor for schedule state and communication errors.
- Continue Hybrid cloud alarm polling without pausing during quiet hours; retain the existing v0.2.5 reliability protections.
- Include unit tests for same-day, cross-midnight, and boundary scheduling and surface exact setup/risks in documentation.

**Limitations:** ESP Local Control supports property-write messages, but the receiver-specific firmware's JSON property-write semantics have not been validated on physical HS006W hardware. A hardware power-off might also disable Wi-Fi, blocking remote wake-up. Prefer volume mute; the feature is disabled by default. No hardware write success or automatic wakeup is claimed without field testing.

See [detailed v0.2.6 release notes](.github/release-notes/v0.2.6.md).


## 0.2.5

**Purpose:** Reduce missed Home Assistant driveway-alarm notifications caused by intermittent Ho-Smart cloud DNS/TLS/HTTPS failures, delayed history delivery, and transient local receiver connection errors. This is a reliability and recovery release, **not** a new feature release. It cannot reconstruct physical alarms that the manufacturer never records.

See [detailed v0.2.5 release notes](.github/release-notes/v0.2.5.md) for the original incident, safeguards, limitations, and upgrade/testing instructions.

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
