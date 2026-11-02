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

**Current integration version: v0.2.9-dev.5**

**Development preview:** v0.2.9-dev.5 removes the accidental numeric prefixes from legacy schedule labels and detaches those obsolete flat controls from the receiver device page. **Default** and **Ch. 1–4** remain available in one grouped Configure form. Existing schedules and entity IDs are preserved. Update-channel selection continues to synchronize with HACS/Marketplace; stable `main` stays at [v0.2.8](https://github.com/gigabytegrove/hosmart-home-assistant/releases/tag/v0.2.8).

## Main and Development update channels

**Choose once, keep receiving updates on that channel.** During initial
**Settings → Devices & services → Add integration → Ho-Smart & eMACROS**
setup, choose **Update channel**. For an existing installed receiver,
open **Ho-Smart & eMACROS → Configure** and change **Update channel**.

| Choice | Receives in normal HACS/Marketplace update checks | Code source |
| --- | --- | --- |
| **Main — stable releases** | Published non-prerelease GitHub versions | `main` branch |
| **Development — nightly prereleases** | Published `-dev.N` GitHub prereleases, as they become available | `dev` branch |

The selection persists across Home Assistant restarts. When you select
Development, Ho-Smart enables **this repository's HACS/Marketplace
Pre-release switch**; Main turns it off. This is the same switch HACS
uses to decide which releases appear in its normal update entity.
If it is disabled or not yet created, the integration automatically
enables it and retries synchronization every minute until the provider
has loaded. **Update channel status** under the receiver's Diagnostics
reports `main_tracking`, `dev_tracking`, or a pending/error status.
The switch applies to the whole Ho-Smart integration, not independently
to each receiver; changing it in one receiver's settings updates all
configured Ho-Smart receivers.

**No recurring Redownload procedure is required.** After choosing your
channel, future versions appear through **Settings → Updates** or HACS/
Marketplace update entities on the provider's refresh schedule. You
still decide when to press Install; switching channels does not
silently download, overwrite files, or restart Home Assistant.

The companion device-page **Update channel** selector follows the same
stored preference. The optional **Install selected channel** button can
request the most recently published stable or dev version immediately
using the provider's `update.install` action when available, for example
when switching back from an existing dev build to an older stable build.
The button is *not required* for routine future updates.

**One-time bootstrap for existing v0.2.8 users:** v0.2.8 predates
this integration-to-HACS synchronization feature. Install
**v0.2.9-dev.4** once using the repository version picker, restart, then
choose **Development** in Configure. Afterward the channel is persistent.
Users who first install a build containing this feature can select it
during initial integration setup without a second configuration step.

HACS/Marketplace checks for new releases periodically. Custom GitHub
repositories may take up to **48 hours** to refresh metadata unless
repository information is refreshed manually. A new commit to `dev`
is not itself an update: the nightly-style publisher must first publish
a versioned GitHub prerelease. Development versions are opt-in and may
contain unverified behavior.

The installation domain remains `hosmart`, regardless of channel.
Existing credentials, paired receivers, entity IDs, and quiet-hour data
are preserved. You cannot run `main` and `dev` concurrently in one
Home Assistant instance.

## v0.2.9-dev.5 — Corrected Configuration display

The numbers in labels such as **01 Main: Action**, **11 Ch1: Start**, and
**12 Ch1: End** were an earlier attempt to force alphabetical ordering.
They have no functional meaning and have been removed.

**More importantly:** Home Assistant displayed those obsolete entity controls
on the receiver's device page even after the integration marked them
`(Hidden)`. This build detaches the fifteen superseded Time/Select entities
from the receiver device without deleting their registry entries or changing
their entity IDs. Existing scripts and automations can still reference them.
The device page keeps its normal receiver and zone controls; schedules are
edited once in **Configure → Default / Ch. 1 / Ch. 2 / Ch. 3 / Ch. 4**.

The device-registry migration is safe to rerun after each Home Assistant
restart and only affects these fifteen known schedule entities belonging to
the configured receiver. It does not detach other devices or controls.

## Conditional schedule fields

The receiver schedule is edited in a single Home Assistant **Configure**
form with five sections: **Default**, **Ch. 1**, **Ch. 2**, **Ch. 3**,
and **Ch. 4**. There is no step-by-step channel wizard or numbered
flat list to adjust.

On **Home Assistant Core 2026.11 or newer**:

- When **Default → Enabled** is **Off**, Default Action, Start, and End
  are **hidden** and cannot be edited accidentally.
- When a channel is **Off (no schedule)**, only its Schedule selector
  remains visible. Its Action, Start, and End immediately disappear.
- When a channel is **Use Default**, it inherits Default; its own
  Action, Start, and End remain hidden.
- When a channel is **Use this channel's schedule**, Action, Start,
  and End immediately appear. Editing these values affects only that
  channel.

Home Assistant leaves hidden fields **out of submitted form data**.
The integration explicitly preserves the last saved action/start/end for
every hidden section instead of resetting or overwriting them. Turning a
schedule back on restores the old times for editing.

Earlier Home Assistant Core versions lack the dynamic visibility API,
so their form may still show fields that would be hidden in 2026.11.
The compatibility fallback retains existing configuration but cannot
provide live conditional field hiding. Upgrade Home Assistant Core to
2026.11+ for the requested hide/show behavior.

**Off** means **no scheduled action** and does not forcibly arm or disarm
the channel. **Disarm** is a separate action which may prevent detection
or cloud alarm reporting, not just silence the audible tone. Independent
tone-only muting has not yet been established as a supported HS006W
hardware command.

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

## Nighttime schedules — Default and Ch. 1–4 (v0.2.9-dev.2)

For the HS006W, open **Settings → Devices & services → Ho-Smart &
eMACROS → Configure**. The schedule editor is now **one page, one save**,
using Home Assistant's native expandable sections rather than the 15+ flat
time/select controls shown in the previous device-page Configuration list.

- **Default** — Enabled, Action, Start, End. Start is **10:00 PM** and End
  **7:00 AM** unless previously customized; the new action default for
  fresh configurations is **Disarm zone**. Previously stored global mute or
  power-off actions are preserved, not silently converted to disarm.
- **Ch. 1**, **Ch. 2**, **Ch. 3**, **Ch. 4** — All available in the same
  form, each with Mode (**Use Default**, **Always armed**, or **Custom
  schedule**), Action (**Arm zone** or **Disarm zone**), Start, and End.
  The four channel sections are collapsed initially for a compact view.
- **Connection mode** — Remains available at the bottom. Local or Hybrid
  connection is required to send commands to the receiver.

A channel on **Use Default** follows Default's action and hours.
A channel on **Always armed** is never silenced by a global mute/power
operation. **Custom schedule** uses that channel's independent hours and
its own Arm/Disarm action. Previously entered hours are **retained** when
you switch between Use Default and Custom.

Changes save together, preserving all receiver options, channel names,
existing entity IDs, paired credentials and restoration intent. The active
schedules re-arm without reconnecting the receiver. This is not a repeated
onboarding or per-channel setup wizard.

The superseded flat time/select entities are **detached from the receiver
device page** instead of merely marked Hidden. Otherwise Home Assistant
may still list rows like `01 Main: Action (Hidden)` in Configuration.
They remain registered under their original entity IDs for existing
automations, so the integration does not delete or recreate them.
Their names are now plain **Default action**, **Default start/end**,
**Ch. 1 schedule**, **Ch. 1 start/end**, and similarly for Ch. 2–4.
The grouped Configure editor is the recommended way to edit schedules.
The **Default: Enable schedule** switch remains on the receiver page
for quick toggling, and direct arm/disarm switches remain available.

### Conditional field visibility

On Home Assistant Core **2026.11+**, Default's Action/Start/End controls
are shown only if Default is Enabled. Each channel's Action/Start/End
controls show only if its Schedule is **Use this channel's schedule**.
When its Schedule is **Off** or **Use Default**, no channel start/end
time pickers are shown. Hidden inputs cannot be inadvertently edited,
and saving the form preserves the saved times and action for later use.

Earlier Home Assistant Core versions cannot hide these fields dynamically;
they retain a compatibility form. All schedule values persist across
the transition to Core 2026.11+.

### What the available actions really do

| Action | Receiver behavior | Sensor events |
| --- | --- | --- |
| **Arm zone** | Schedule the selected ZoneAlarming flag on, then restore its previous value | Detection remains enabled |
| **Disarm zone** | Schedule the selected ZoneAlarming flag off, then restore its previous value | Detection/cloud reporting may cease |
| **Legacy: mute entire receiver** | Set the shared Volume to zero only if every channel is scheduled for that global action | Physical volume changes for every tone |
| **Tone-only mute** | **Not available on verified HS006W** | No validated independent channel mute command exists |

The previously available whole-receiver Power Off setting is preserved
for existing installations; it is unsafe to assume that Wi-Fi will remain
available to switch the receiver back on later.

**The HS006W has not been physically verified to accept these local
property writes.** ESP Local Control supports property writes in general,
but receiver-specific JSON setters may reject them. Writes are read back,
and failures are logged and shown in diagnostics. The integration
deliberately refuses to substitute disarming, shutting down the receiver,
or changing its shared volume for a requested **tone-only mute**.

If tone-only muting is essential, the device's supported channel-specific
volume/mute command must first be established from vendor protocol evidence
or a sanitized device-parameter capture and verified against the hardware.
The dev build does not claim that capability yet.

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
