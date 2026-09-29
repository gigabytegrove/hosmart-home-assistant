# Hosmart Home Assistant

Local Home Assistant integration for supported Hosmart/eMACROS driveway alarm receivers using the ESP RainMaker local-control protocol.

> **Development status:** early field-test build. The initial target is the HS006W / ESP32-C6 receiver using Security1 local control with the receiver's Proof of Possession (POP). The My Hosmart mobile app and cloud are not required during normal runtime once the receiver is configured.

## Current features

- Local-only runtime communication with the receiver
- ESP Local Control Security1 (X25519 + AES-256-CTR)
- High-frequency development polling at **4 Hz** for short-lived event capture
- Passive UDP/50001 listener
- Every successful poll written to a persistent rotating JSONL capture
- Every receiver-field change written separately with previous/current values
- Every UDP/50001 datagram captured before filtering, including raw text/hex
- Poll errors and UDP listener errors preserved
- Raw event, channel, and channel-name sensors
- Persistent "last activity" sensors so a brief alarm remains inspectable after it clears
- Poll/change/UDP counters and last-seen timestamps
- Receiver battery, volume, child-device count, power, charging, and zone armed-state entities
- Fires `hosmart_activity` whenever `Event`, `Channel`, or `ChannelName` changes
- Fires `hosmart_udp_packet` for every UDP/50001 datagram received
- Home Assistant diagnostics support with a redacted recent capture tail

The development capture intentionally logs far more than a normal production integration. The receiver POP and other credential-like fields are redacted from the persistent debug capture.

## HACS installation

This repository is intended to be installed as a HACS custom integration.

1. Open **HACS**.
2. Open the menu and choose **Custom repositories**.
3. Add:
   - Repository: `https://github.com/gigabytegrove/hosmart-home-assistant`
   - Type: **Integration**
4. Find **Hosmart Home Assistant** in HACS and download it.
5. Restart Home Assistant.
6. Go to **Settings → Devices & services → Add integration**.
7. Search for **Hosmart**.
8. Enter the receiver IP address, local-control port, and Local Control POP.

For the verified HS006W test receiver the port is `8080` and Local Control Type is `1`.

The POP is a device credential. Do not publish it in issues, screenshots, logs, or GitHub commits.

## Field-test capture

The first field-test version is intentionally designed around one-off real-world events that may be inconvenient to reproduce.

Every successful local state read is appended to:

```text
<HA config>/hosmart_debug/hosmart_<config-entry-id>.jsonl
```

The file is structured JSON Lines. It rotates at approximately 50 MiB and keeps four rotated copies in addition to the active file, limiting the capture set to roughly 250 MiB.

Captured record types include:

- `integration_start`
- `poll_snapshot`
- `receiver_fields_changed`
- `event_baseline`
- `event_tuple_changed`
- `poll_error`
- `poll_unexpected_error`
- `udp_listener_started`
- `udp_listener_error`
- `udp_50001_datagram`
- `integration_stop`

Each `poll_snapshot` includes the full locally returned `config` and `params` structures, with the POP redacted. This is deliberate for the initial reverse-engineering phase.

Home Assistant's integration diagnostics also include current state, counters, and the newest 2,000 structured capture records.

## What to watch during a real driveway pass

The live values currently under investigation are:

- `Event`
- `Channel`
- `ChannelName`

The integration does **not** assume what values mean "motion" or "alarm." The initial field test preserves raw evidence first.

Useful entities include:

- `sensor.<device>_event`
- `sensor.<device>_channel`
- `sensor.<device>_channel_name`
- `sensor.<device>_last_activity_event`
- `sensor.<device>_last_activity_channel`
- `sensor.<device>_last_activity_channel_name`
- `sensor.<device>_last_activity_time`
- `sensor.<device>_last_event_change`
- `sensor.<device>_poll_count`
- `sensor.<device>_receiver_change_count`
- `sensor.<device>_udp_packet_count`
- `sensor.<device>_last_udp_packet_time`
- `sensor.<device>_last_udp_packet_source`

You can also listen for these events in **Developer Tools → Events**:

```text
hosmart_activity
hosmart_udp_packet
```

## Verified hardware and protocol

Initial verified target:

- Hosmart/eMACROS HS006W
- ESP32-C6
- firmware reported as `2.0`
- ESP Local Control `v1.0`
- Local Control Security Type `1`
- TCP/8080
- Security1 X25519 + AES-256-CTR
- receiver-specific 8-byte POP
- two local properties: `config` and `params`

Additional devices may use the same protocol, but should not be treated as verified until tested.

## Runtime architecture

```text
HS006W receiver
  ├─ TCP/8080
  │   ├─ /esp_local_ctrl/session
  │   └─ /esp_local_ctrl/control
  │
  └─ UDP/50001 (local notification hint, when visible)
          │
          ▼
Home Assistant
          │
          ├─ entities/events
          └─ persistent redacted JSONL field-test capture
```

## Security

The POP is stored in the Home Assistant config entry because it is required to establish Security1 sessions with the receiver. The development debug recorder redacts `POP`, password, and token-shaped fields before writing JSONL diagnostics.

Do not post your POP publicly.

## License

MIT
