<p align="center">
  <img src="logo.png" alt="Ho-Smart for Home Assistant" width="560">
</p>

# Ho-Smart for Home Assistant

[![Add to HACS](https://img.shields.io/badge/Add%20to-HACS-41BDF5?logo=homeassistant&logoColor=white)](https://my.home-assistant.io/redirect/hacs_repository/?owner=gigabytegrove&repository=hosmart-home-assistant&category=integration)
[![Open HACS repository on My Home Assistant](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=gigabytegrove&repository=hosmart-home-assistant&category=integration)

Bring supported Ho-Smart driveway alarm receivers into Home Assistant with local receiver status, alarm history, and automation-friendly entities.

The integration is currently verified with the **Ho-Smart HS006W** receiver running firmware **2.0**.

## What it does

Ho-Smart for Home Assistant can provide:

- Driveway alarm activity
- Receiver power state
- Volume
- Internal battery level
- Channel and zone information
- Zone 1–4 armed states
- Last alarm/activity details
- Home Assistant events for automations
- Local receiver status even if the Ho-Smart cloud is temporarily unavailable

For the HS006W, the receiver exposes normal status locally but does not expose driveway alarm events through its local status data. Because of that, **Hybrid mode** combines local receiver data with Ho-Smart alarm history and is the recommended setup.

## Current release

For the current tested version, installation instructions, and update-specific limitations, consult the [GitHub Releases page](https://github.com/gigabytegrove/hosmart-home-assistant/releases). v0.2.5 specifically addresses intermittent cloud communication failures and alarm-history recovery; it does not guarantee delivery of alarms absent from Ho-Smart's cloud history.

## Installation with HACS

**One-click installation:** Select the [Add to HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=gigabytegrove&repository=hosmart-home-assistant&category=integration) badge at the top of this README. Choose your Home Assistant instance, then download **Ho-Smart for Home Assistant** in HACS.

**Manual installation (if the badge does not work):**

1. Open **HACS** in Home Assistant.
2. Select the three-dot menu in the upper-right corner, then **Custom repositories**.
3. Enter `https://github.com/gigabytegrove/hosmart-home-assistant` and select **Integration** as the type.
4. Select **Add**, open **Ho-Smart for Home Assistant** in HACS, and download the latest release.
5. Restart Home Assistant.
6. Go to **Settings → Devices & services → Add integration** and search for **Ho-Smart**.
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

Other Ho-Smart, Hosmart, or eMACROS receivers may share similar hardware or protocols, but they should not be considered supported until they have been tested.

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

The integration is built around behavior verified on real hardware rather than assumed compatibility.

**v0.2.2 is the current stable baseline.** Future changes should preserve the working local and Hybrid behavior unless testing proves a change is necessary.

## License

MIT


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
