<p align="center">
  <img src="logo.png" alt="Ho-Smart" width="560">
</p>

# Ho-Smart for Home Assistant

Local Home Assistant integration for supported Ho-Smart / Hosmart / eMACROS driveway alarm receivers using the ESP RainMaker local-control protocol.

> **Development status:** early field-test build. The initial target is the HS006W / ESP32-C6 receiver using Security1 local control. During setup, the integration signs in to the user's Ho-Smart account once to retrieve the receiver's local-control key (POP). The Ho-Smart email/password are not saved, and normal runtime communication is local.

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
8. Enter the receiver IP address, local-control port, and your **Ho-Smart app account email/password**.

The integration uses those credentials only during onboarding to call Ho-Smart's device API, retrieve the receiver's Local Control metadata, and identify the POP that actually authenticates to the receiver. The account email/password are **not stored** in the Home Assistant config entry. Only the receiver address, port, and local-control POP are retained for local runtime communication.

For the verified HS006W receiver the local-control port is `8080` and Local Control Type is `1`. Users do not need to know or manually enter the POP.

## Field-test capture

The first field-test version is intentionally designed around one-off real-world events that may be inconvenient to reproduce.

Every successful local state read is appended to the high-frequency sample log:

```text
<HA config>/hosmart_debug/hosmart_<config-entry-id>.jsonl
```

Every non-routine record is also copied into a separate long-lived event journal:

```text
<HA config>/hosmart_debug/hosmart_<config-entry-id>_events.jsonl
```

Both are structured JSON Lines and rotate at approximately 50 MiB with four rotated copies. The sample log records the complete live `params` object on every 4 Hz poll. Static `config` is recorded once and again only if it changes, avoiding needless repetition while preserving all state. The event journal preserves all field changes, complete parameter changes, UDP datagrams, errors, startup/shutdown records, and event transitions separately from routine polls.

Captured record types include:

- `integration_start`
- `poll_snapshot`
- `params_changed`
- `receiver_fields_changed`
- `event_baseline`
- `event_tuple_changed`
- `poll_error`
- `poll_unexpected_error`
- `udp_listener_started`
- `udp_listener_error`
- `udp_50001_datagram`
- `integration_stop`

Each `poll_snapshot` includes the full live `params` structure, with the POP redacted. `config_snapshot` preserves the full static receiver configuration whenever it changes. This is deliberate for the initial reverse-engineering phase.

Home Assistant's integration diagnostics include current state, counters, the newest 1,000 sample records, and up to 5,000 event-journal records.

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
- `sensor.<device>_last_poll_time` *(diagnostic; disabled by default because it changes four times per second)*
- `sensor.<device>_poll_count` *(diagnostic; disabled by default because it changes four times per second)*
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

The receiver's POP (Proof of Possession) is the per-device key used by ESP Security1 to authenticate local-control sessions. It is **not something the user should have to locate or type manually**. During setup, the integration retrieves it from the user's Ho-Smart account, verifies it against the receiver, and stores only that device key for future local access.

The Ho-Smart account email/password are onboarding-only and are not persisted by this integration. The development debug recorder redacts `POP`, password, and token-shaped fields before writing JSONL diagnostics.

Do not publish a receiver POP if you obtain one separately.

## License

MIT
