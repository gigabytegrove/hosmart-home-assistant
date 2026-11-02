<p align="center">
  <img src="logo.png" alt="Ho-Smart and eMACROS for Home Assistant" width="560">
</p>

# Ho-Smart & eMACROS for Home Assistant

[![GitHub stars](https://img.shields.io/github/stars/gigabytegrove/hosmart-home-assistant?style=flat&label=Stars)](https://github.com/gigabytegrove/hosmart-home-assistant/stargazers)
[![GitHub repository](https://img.shields.io/badge/GitHub-Repository-181717?logo=github&logoColor=white)](https://github.com/gigabytegrove/hosmart-home-assistant)
[![Open issues](https://img.shields.io/github/issues/gigabytegrove/hosmart-home-assistant)](https://github.com/gigabytegrove/hosmart-home-assistant/issues)
[![Latest GitHub release](https://img.shields.io/github/v/release/gigabytegrove/hosmart-home-assistant?label=Release)](https://github.com/gigabytegrove/hosmart-home-assistant/releases)
[![Donate with PayPal](https://img.shields.io/badge/Donate-PayPal-0070BA?logo=paypal&logoColor=white)](https://paypal.me/gigabytegrove)

[![Add to HACS](https://img.shields.io/badge/Add%20to-HACS-41BDF5?logo=homeassistant&logoColor=white)](https://my.home-assistant.io/redirect/hacs_repository/?owner=gigabytegrove&repository=hosmart-home-assistant&category=integration)
[![Open HACS repository on My Home Assistant](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=gigabytegrove&repository=hosmart-home-assistant&category=integration)

Bring supported **Ho-Smart and eMACROS** driveway alarm receivers into Home Assistant with local receiver status, alarm history, and automation-friendly entities.

**Brand compatibility:** Ho-Smart and eMACROS are brands of the same manufacturer, and certain Wi-Fi products share the **My Hosmart** app ecosystem. Hardware is **not universally interchangeable across models**. The verified protocol baseline remains the **HS006W receiver with firmware 2.0**; other branded models require individual testing. See [manufacturer information](https://www.hosmartmall.com/pages/our-story) and [compatibility guidance](https://myhosmart.com/technical-support-2/).

## What it does

Ho-Smart & eMACROS for Home Assistant can provide:

- Driveway alarm activity
- Receiver power state
- Volume
- Optional per-receiver nighttime quiet hours (experimental receiver writes; disabled by default)
- Internal battery level
- Channel and zone information
- Zone 1–4 armed states
- Last alarm/activity details
- Home Assistant events for automations
- Local receiver status even if the Ho-Smart cloud is temporarily unavailable

For the HS006W, the receiver exposes normal status locally but does not expose driveway alarm events through its local status data. Because of that, **Hybrid mode** combines local receiver data with Ho-Smart alarm history and is the recommended setup.

## Current release

**Current integration version: v0.2.9-dev.1**

**Development preview:** v0.2.9-dev.1 is a prerelease built from `dev`. The production release remains [v0.2.8](https://github.com/gigabytegrove/hosmart-home-assistant/releases/tag/v0.2.8) from `main`. Use HACS's specific-version chooser to install the beta (or use the new **Software channel** and **Install selected channel** controls when HACS exposes a supported update entity). Selecting a channel alone does **not** install software. All installs require a Home Assistant restart. Power/Volume and ZoneAlarming writes are not hardware-qualified on HS006W.

## Main and dev installation channels

| Track | GitHub branch | HACS installer selection | Intended use |
| --- | --- | --- | --- |
| **Main (stable)** | `main` | Latest normal GitHub release, currently v0.2.8 | Everyday use |
| **Dev (beta)** | `dev` | Latest published `vX.Y.Z-dev.N` GitHub prerelease | Explicit opt-in testing |

You can select **Software channel** on the receiver device page and press
**Install selected channel** to request the chosen *published release* through
Home Assistant's `update.install` service. The operation locates the
Ho-Smart HACS update entity and asks HACS to install the exact version.
**It does not directly edit files and never silently updates just because
you change the selector.** If the matching HACS updater cannot be identified,
or it does not support specific-version installs, the button reports an
actionable error instead of claiming that an installation succeeded.

The supported manual fallback is always **HACS → Ho-Smart & eMACROS →
Redownload → Need a different version? → select Release**, and choose the
stable or `-dev.N` prerelease. HACS may require showing beta versions
before they appear. Restart Home Assistant after download.

The `hosmart` domain, existing entry IDs, receiver pairings, schedule data,
and unique entity IDs are identical on both tracks; you cannot load both
builds concurrently under the same domain. The `dev` release is **not**
automatically promoted to `main`: it must pass validation and be merged.
For development status, see the [dev branch](https://github.com/gigabytegrove/hosmart-home-assistant/tree/dev).

## Configuration labels on narrow screens

The Configuration section uses concise, ordered labels:
**00 Main: Quiet hours**, **01 Main: Action**, **02 Main: Start**,
**03 Main: End**, followed by **10 Ch1: Mode**, **11 Ch1: Start**,
**12 Ch1: End** through Channel 4. These are one start/end pair per channel,
**not duplicated schedules**. Previous labels were both truncated to
“Channel N quiet…” and alphabetical sorting could put End above Start.
Only display names change; stored times and entity unique IDs remain intact.

## Installation with HACS

**One-click installation:** Select the [Add to HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=gigabytegrove&repository=hosmart-home-assistant&category=integration) badge at the top of this README. Choose your Home Assistant instance, then download **Ho-Smart & eMACROS for Home Assistant** in HACS.

**Manual installation (if the badge does not work):**

1. Open **HACS** in Home Assistant.
2. Select the three-dot menu in the upper-right corner, then **Custom repositories**.
3. Enter `https://github.com/gigabytegrove/hosmart-home-assistant` and select **Integration** as the type.
4. Select **Add**, open **Ho-Smart & eMACROS for Home Assistant** in HACS, and download the latest release.
5. Restart Home Assistant.
6. Go to **Settings → Devices & services → Add integration** and search for **Ho-Smart & eMACROS**.
7. Follow the setup prompts.

**Note:** This is a custom HACS repository, not currently listed in HACS's default catalog. The badge opens the custom repository in your HACS installation; it does not bypass the download, restart, or initial configuration steps. HACS must already be installed.

## Setup

You will be asked for:

- **Receiver IP address**
- **Receiver port** — the verified HS006W default is `8080`
- **Connection mode**
- **My Hosmart account email and password** when using Hybrid or Cloud mode

You do **not** need to locate or manually enter the receiver's Local Control POP. The integration obtains the information it needs during setup.

Your My Hosmart email and password are used during setup and are **not stored** by the integration.

## Connection modes

### Hybrid — recommended

Uses:

- Local communication for receiver status
- Ho-Smart alarm history for driveway alarm events

This provides the fullest verified HS006W functionality and keeps local receiver entities available if the Ho-Smart alarm-history service has a temporary problem.

### Local only

Uses only the receiver on your local network.

This mode provides local receiver status and avoids Ho-Smart cloud calls after setup.

**Important:** on the verified HS006W, driveway alarm events are not exposed in the receiver's local status data. That means the driveway alarm entity cannot currently receive proven alarm events in Local-only mode.

### Cloud alarm mode

Uses Ho-Smart alarm history without continuously polling the receiver locally.

This is intended for users who only need alarm/activity information.

## Entities

The exact entity list can vary as support expands, but the verified HS006W exposes these primary entities:

- **Driveway alarm**
- Event
- Channel
- Channel name
- Last activity event
- Last activity channel
- Last activity channel name
- Last activity source
- Last activity time
- Last event change
- Internal battery
- Volume
- Child device count
- Power
- Internal charging
- Zone 1 armed
- Zone 2 armed
- Zone 3 armed
- Zone 4 armed
- Receiver-wide quiet-hours switch, start/end times, and action selector
- Channel 1–4 quiet behavior selectors and individual start/end times
- Channel 1–4 direct arm/disarm switches (local receiver mode required)

Several troubleshooting and diagnostic entities are also available but are disabled by default so normal installations stay uncluttered.

## Using alarms in automations

The **Driveway alarm** binary sensor becomes active for 10 seconds upon receipt of a recent channel-one alarm, with an independent timer to turn it off even if cloud polling subsequently fails.

The integration also fires Home Assistant events:

```text
hosmart_activity
hosmart_alert
hosmart_udp_packet
```

For most automations, use the **Driveway alarm** entity or the `hosmart_alert` event.

Alarm event data can include:

- Receiver name
- Event type
- Channel number
- Channel name
- Activity time
- Source
- Original Ho-Smart message
- Record key

## How alarm detection works

The verified HS006W reports normal receiver information locally, including power, volume, battery, channel names, and armed-zone state.

During live testing, real driveway alarms did **not** appear in the receiver's local status values. They did appear in the same Ho-Smart alarm history used by the My Hosmart app.

Hybrid mode therefore uses:

- Local receiver communication for normal status
- Ho-Smart alarm history for actual driveway alerts

This is why Hybrid mode is the recommended configuration.

On startup, recent alarm history is loaded so the **Last activity** entities can show meaningful information immediately. Historical alarms are not treated as new alarms.

## Polling

Production polling is intentionally modest:

- Local receiver status: approximately every **5 seconds**
- Ho-Smart alarm history in Hybrid/Cloud mode: approximately every **3 seconds**

The faster development polling used during reverse engineering is not used in normal releases.

## Existing installations

If you installed a version before v0.2.0, your existing entry may contain only the local receiver information.

To enable Hybrid mode:

1. Go to **Settings → Devices & services → Ho-Smart**.
2. Select **Configure**.
3. Choose **Hybrid**.
4. Enter your My Hosmart email and password when prompted.

The credentials are used to connect the existing receiver entry to the correct Ho-Smart account and are then discarded.

## Nighttime quiet hours — direct device controls (v0.2.8)

**You do not need to run Configure to set quiet hours.** The old two-step
receiver/channel wizard was removed because routine settings belong on the
receiver's Home Assistant **device page**. Existing schedules from v0.2.6
and v0.2.7 stay intact. There is no re-pairing, factory reset, or migration.

After upgrading through HACS and restarting Home Assistant:

1. Go to **Settings → Devices & services → Ho-Smart & eMACROS → Devices**.
2. Open the relevant receiver. Its **Configuration** section includes the
   receiver-wide quiet-hours switch, start/end time pickers, action selector,
   and **all four** channel behavior selectors and time pickers at once.
3. Choose the channels that must keep working. For example, set **Channel 1
   overnight behavior** to **Always armed (protected)** if Channel 1 is the
   driveway. Choose **Follow receiver-wide hours** for other channels, or
   **Disarm on custom schedule** and set each channel's times.
4. Turn on **Receiver overnight quiet hours** to enable the main schedule;
   default hours are **10:00 PM–7:00 AM** in Home Assistant's timezone.
5. Review **Night quiet status** and Channel 1–4 status diagnostics, and
   confirm behavior physically before leaving schedules unattended.

**Every channel is visible from the beginning.** Editing one channel saves
that change alone, without requiring you to save Channel 1 to access Channel 2
or running another configuration wizard. Settings change live and persist
across Home Assistant restarts; schedules re-arm without reconnecting.

### Receiver-wide controls

| Device entity | Purpose |
| --- | --- |
| Receiver overnight quiet hours | Enable/disable the main daily schedule |
| Receiver quiet starts | Main quiet-hours start (10:00 PM default) |
| Receiver quiet ends | Main quiet-hours end (7:00 AM default) |
| Receiver quiet-hours action | Mute receiver audio, or power off receiver |

### Channel controls — always available together

Each of the four channels exposes **Channel N overnight behavior**,
**Channel N quiet starts**, **Channel N quiet ends**, and a direct
**Channel N armed** switch. The mode choices are:

- **Follow receiver-wide hours:** obey the main quiet-hours window.
- **Always armed (protected):** do not schedule this channel off.
  Protecting even one channel prevents receiver-wide mute/power-off.
- **Disarm on custom schedule (stops detection):** independently choose
  the hours when the named zone will be disarmed. You can edit the time
  fields even if the channel has not yet been switched to this mode.

Direct **Channel N armed** switches send an arm or disarm command to the
receiver; they are different from the read-only historical armed-status
binary sensors. While a schedule is active, its next evaluation can undo
a conflicting manual change.

If the receiver is Cloud-only, local receiver controls are unavailable.
Open **Configure** only to change its connection mode, not to manage schedules.

### Important receiver limitations

A HS006W exposes **one receiver-wide volume** plus
`ZoneAlarming1`–`ZoneAlarming4` armed flags. There is no validated
per-channel audio-only volume control. Disarming a channel can suppress
**the physical alarm and the cloud notification** for that channel.
Do **not** schedule disarming for sensors whose detection you depend on.

If all four channels are scheduled quiet during the receiver's quiet-hours
window, the configured master action can mute/power-off the receiver. When
any channel must remain active, the integration instead attempts to
disarm only the scheduled channels. Prior armed/volume/power values are
persisted before writes and restored when each quiet period ends, including
after Home Assistant restarts.

**Write support still requires real hardware testing.** ESP Local Control
defines property writes, but Ho-Smart/eMACROS firmware may reject partial
JSON `params` writes. The integration checks protocol acknowledgement and
reads back state; failed writes show as errors rather than silently
claiming success. **Power-off may disable the receiver's Wi-Fi**, so
automatic power-on could be impossible without manual intervention.
Try changes with the hardware available to you, preferably starting
with volume mute.

## Privacy and security

The integration stores the receiver information required for local communication.

The following are **not persisted**:

- My Hosmart account password
- Ho-Smart access token

Sensitive values are redacted from Home Assistant diagnostics and the integration's structured debug records.

If you share logs or diagnostics in a GitHub issue, review them first and remove anything you consider private.

## Troubleshooting

### Everything is unavailable

Confirm that:

- You are running the current release.
- Home Assistant can reach the receiver IP and port.
- The receiver IP has not changed.
- Hybrid/Cloud setup completed successfully.

Then restart Home Assistant and check **Settings → System → Logs** for entries containing `hosmart`.

### Local entities work but alarms do not

If you are using **Local only**, this is expected on the verified HS006W because real driveway alarm events are not exposed by its local status interface.

Use **Hybrid** mode for verified alarm reporting.

### Alarm history works but local receiver entities do not

Check network access between Home Assistant and the receiver. The verified HS006W uses TCP port `8080`.

### Need to report a problem?

Open a GitHub issue and include:

- Ho-Smart integration version
- Home Assistant version
- Receiver model and firmware
- Connection mode
- What you expected
- What actually happened
- Relevant sanitized logs or diagnostics

Do not include passwords, tokens, private keys, or other secrets.

See [SUPPORT.md](SUPPORT.md) for more information.

## Supported hardware

### Verified

| Device | Firmware | Status |
| --- | --- | --- |
| Ho-Smart HS006W | 2.0 | Verified |

Ho-Smart and eMACROS are related brands, but their different product kits are not necessarily compatible. Receiver models other than the verified HS006W/firmware 2.0 require independent device testing.

If you have another model and want support added, open a device support request with the exact model and firmware.

## Technical details

These details are mainly useful for contributors and troubleshooting.

The verified HS006W uses:

- ESP32-C6
- ESP RainMaker Local Control v1.0
- TCP port 8080
- Security Type 1
- X25519 key exchange
- AES-256-CTR session encryption
- Receiver-specific 8-character Local Control POP

The integration also listens on UDP port `50001` because the My Hosmart app uses a local UDP notification listener. In verified HS006W testing, real driveway alarms did not produce usable UDP alarm packets, so UDP is treated as diagnostic rather than the primary alarm source.

Structured integration logs are stored under:

```text
<HA config>/hosmart_debug/
```

These logs are rotated automatically.

## Project status

The integration recognizes both Ho-Smart and eMACROS; hardware compatibility is based on verified receiver model/protocol behavior, not merely the brand.

The current integration version is listed in [Current release](#current-release), and the authoritative published version is available on [GitHub Releases](https://github.com/gigabytegrove/hosmart-home-assistant/releases/latest). Verified device support remains limited to the **HS006W with firmware 2.0**. Future releases must preserve known-good local and Hybrid behavior unless testing supports a change.

## Reliability changes by version

### Alarm-delivery reliability (v0.2.3)

The **Cloud alarm reporting available** diagnostic sensor reports recent successful cloud history access; it does not guarantee the receiver uploaded an event. Cloud interruptions now recover from the last successful query (up to seven days) rather than a moving three-minute window. Notices delayed more than two minutes are logged as historical, not announced as new motion. See diagnostic fields `last_cloud_success_time`, `missed_cloud_alert_count`, and `last_alarm_received_at`.

**Hardware limitation:** HS006W local status polling has not exposed actual driveway triggers, and testing has not established a working UDP alarm source. If its cloud never receives an alarm, this integration cannot infer it from static local status. Use an independently connected local motion sensor for safety-critical automations until a validated local event source is available.


### Alarm recovery after restarts (v0.2.4)

In Hybrid/Cloud mode, successful Ho-Smart history checks persist a recovery cursor
to `/config/hosmart_debug/`. After an outage or Home Assistant restart, Ho-Smart
reconciles the notice history with an hour of overlap (up to seven days of
interruption recovery) and deduplicates already processed notices. Older recovered
alerts are recorded without firing new motion automations. The receiver's physical
alarm can still sound independently of Ho-Smart's cloud notice service; vendor
non-delivery cannot be corrected locally.


### Resilient network handling (v0.2.5)

Ho-Smart reuses Home Assistant's shared HTTPS connection pool and cached DNS.
Transient cloud DNS/connection/TLS handshake errors, read timeouts, HTTP 429,
and server-side errors are retried once. Authentication and TLS certificate
verification failures are not bypassed. Cloud history is checked frequently
for live alarms and reconciled once per minute for late notifications.
Successful reconciliation progress is stored across restarts; partial history
does not advance the recovery checkpoint. Diagnostics now include
`cloud_transport` categorized failures and retries, `cloud_reconcile_count`,
`cloud_realtime_count`, `last_cloud_reconciliation`, and `local_retry_count`.

These changes minimize recoverable misses but cannot guarantee notice delivery
when the manufacturer never uploads a physical alarm to its cloud service.

## License

MIT

## Support Gigabyte Grove

If this project is useful to you, you can support ongoing Gigabyte Grove development with an optional [PayPal donation](https://paypal.me/gigabytegrove). Donations are appreciated but never required to use this integration.
