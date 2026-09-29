<p align="center">
  <img src="logo.png" alt="Ho-Smart for Home Assistant" width="560">
</p>

# Ho-Smart for Home Assistant

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

## Current stable version

**v0.2.2** is the current known-good baseline for the verified HS006W setup.

It fixes the startup and availability problems found in earlier v0.2 releases while keeping local and cloud operation independent in Hybrid mode.

## Installation with HACS

1. Open **HACS** in Home Assistant.
2. Add this repository as a custom **Integration** repository:
   `https://github.com/gigabytegrove/hosmart-home-assistant`
3. Install **Ho-Smart for Home Assistant**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration**.
6. Search for **Ho-Smart**.
7. Follow the setup prompts.

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

The **Driveway alarm** binary sensor becomes active briefly when a newly observed alarm is detected.

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
