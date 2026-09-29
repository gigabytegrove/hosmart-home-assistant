<p align="center">
  <img src="logo.png" alt="Ho-Smart" width="560">
</p>

# Ho-Smart for Home Assistant

Home Assistant integration for supported Ho-Smart / Hosmart / eMACROS driveway-alarm receivers. The verified HS006W implementation combines ESP RainMaker Security1 local control with the Ho-Smart alarm-history path discovered in the My Hosmart Android app.

## Connection modes

The integration supports three selectable runtime modes:

- **Hybrid** — local Security1 receiver state plus Ho-Smart cloud alarm events. This is the default and provides the fullest verified functionality.
- **Local only** — local receiver state/control transport only. No Ho-Smart cloud calls occur after setup. The HS006W driveway alarm itself is not exposed by the receiver's local `params` property, so alarm events are not currently available in this mode.
- **Cloud alarm mode** — Ho-Smart alarm history without continuous local polling. Intended for users who only need alarm/activity events.

The account email/password are used during setup only. They are **not stored**. Runtime cloud alarm checks use the account `user_id` returned by the exact My Hosmart 1.4.9.3 flow; access tokens and passwords are discarded.

## Verified HS006W behavior

Reverse engineering and live field tests established:

- Receiver: HS006W / ESP32-C6, firmware `2.0`
- ESP Local Control `v1.0`
- TCP/8080
- Security Type `1`
- X25519 + AES-256-CTR Security1 session
- Receiver-specific 8-character POP
- Local properties: `config` and `params`
- Local state is genuinely live; physical volume changes were observed immediately through local control
- Driveway alarm events do **not** alter the local `params` object
- Two independently triggered real driveway alarms produced no local field changes and no UDP/50001 datagrams, while Ho-Smart history recorded both as `Alert! <receiver> Reported Driveway:Alarm`
- My Hosmart's native local notification server listens on UDP/50001; it does not perform a registration handshake before binding. The listener remains supported as a diagnostic/local hint, but the tested HS006W did not emit those datagrams during the two proven alarm events.

## Alarm behavior

Hybrid/cloud mode polls the same Ho-Smart notice endpoint used by My Hosmart. A real alert such as:

```text
Alert! GG Sensor Reported Driveway:Alarm
```

is parsed into:

- Event: `Alarm`
- Channel name: `Driveway`
- Channel number: resolved by matching the local/configured channel names (for example, Driveway → Channel 1)
- Activity timestamp: the receiver/cloud event's `msgtime`, not the later polling time
- Source: `cloud`

The integration de-duplicates notices by Ho-Smart's `delkey` when available.

On startup, Hybrid/cloud mode reads recent history so the **Last activity** entities are populated immediately instead of remaining unavailable until the next vehicle passes.

## Entities

Primary entities include:

- **Driveway alarm** — binary motion/alarm entity; active briefly after a newly observed alarm
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
- Zone 1–4 armed states

Diagnostic entities are disabled by default:

- Last poll time
- Poll count
- Receiver change count
- UDP packet count
- Last UDP packet source
- Last UDP packet time
- Cloud alert count
- Last cloud check

The UDP last-seen diagnostics report `Never observed` until a datagram is actually received; they no longer appear as unexplained empty production entities by default.

## Home Assistant events

The integration fires:

```text
hosmart_activity
hosmart_alert
hosmart_udp_packet
```

`hosmart_alert` is fired for newly observed alarm records. Event data includes the node, receiver name, event, channel, channel name, activity timestamp, source, message and record key.

## Polling

The initial reverse-engineering build polled local state at 4 Hz so a short-lived parameter transition would not be missed. Live field tests proved that HS006W alarm events are not represented in the local `params` stream, so production local polling is now **5 seconds**.

Hybrid/cloud alarm history checks run every **3 seconds**. In the verified two-pass field test, Ho-Smart history exposed the alarms roughly three seconds after their recorded trigger timestamps.

## Upgrade notes

### v0.2.1

v0.2.1 fixes the v0.2.0 Hybrid-mode availability regression. A failure in the Ho-Smart history service no longer takes healthy local receiver entities offline. Existing pre-v0.2.0 entries are also backfilled with their node ID after the next successful local refresh.

## Existing installations

Entries created before v0.2.0 contain the local POP but not the Ho-Smart `user_id`.

After updating:

1. Open **Settings → Devices & services → Ho-Smart**.
2. Select **Configure**.
3. Choose **Hybrid**.
4. Enter the My Hosmart email/password once when prompted.

Home Assistant retrieves the account `user_id`, verifies that the account contains the already-configured node, discards the credentials/token, reloads the integration, and backfills the latest activity from alarm history.

## HACS installation

1. Open **HACS**.
2. Add `https://github.com/gigabytegrove/hosmart-home-assistant` as a custom **Integration** repository.
3. Download **Ho-Smart for Home Assistant**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration**.
6. Search for **Ho-Smart**.
7. Enter the receiver IP, port (verified default `8080`), desired connection mode, and My Hosmart account credentials.

Users do not need to locate or manually enter the Local Control POP.

## Runtime architecture

```text
                         ┌──────────────────────────────┐
                         │       Ho-Smart cloud         │
                         │ notice/query/page alarm log  │
                         └──────────────┬───────────────┘
                                        │ Hybrid / Cloud
                                        ▼
HS006W receiver ── Security1 TCP/8080 ──► Home Assistant
      │                 Local / Hybrid       │
      │                                      ├─ Driveway alarm
      └─ UDP/50001 listener (diagnostic)     ├─ state entities
                                             └─ HA events
```

## Security and diagnostics

The receiver POP is stored because it is required for local Security1 sessions. The Ho-Smart account password and access token are never persisted. The account `user_id`, POP, password/token-shaped fields and other credentials are redacted from integration diagnostics and JSONL debug records.

Structured logs are stored under:

```text
<HA config>/hosmart_debug/
```

Routine local snapshots and a separate event journal are rotated automatically.

## License

MIT
