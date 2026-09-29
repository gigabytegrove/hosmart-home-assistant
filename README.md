# Hosmart Home Assistant

Local Home Assistant integration for supported Hosmart/eMACROS driveway alarm receivers using the ESP RainMaker local-control protocol.

> **Development status:** early test build. This integration currently targets the HS006W / ESP32-C6 receiver and uses Security1 local control with the receiver's Proof of Possession (POP). It does not require the My Hosmart mobile app at runtime.

## Current features

- Local-only runtime communication with the receiver
- ESP Local Control Security1 (X25519 + AES-256-CTR)
- 1-second polling fallback for event discovery
- Passive UDP/50001 listener to request immediate refreshes when local notifications are visible to Home Assistant
- Raw event, channel, and channel-name sensors for reverse-engineering real driveway activations
- Receiver battery, volume, child-device count, power, charging, and zone armed-state entities
- Fires a Home Assistant event named `hosmart_activity` whenever `Event`, `Channel`, or `ChannelName` changes

## HACS installation

1. Open **HACS**.
2. Open the menu and choose **Custom repositories**.
3. Add:
   - Repository: `https://github.com/gigabytegrove/hosmart-home-assistant`
   - Type: **Integration**
4. Find **Hosmart Home Assistant** in HACS and download it.
5. Restart Home Assistant.
6. Go to **Settings → Devices & services → Add integration**.
7. Search for **Hosmart**.
8. Enter the receiver IP address, port, and Local Control POP.

The POP is a device credential. Do not publish it in issues, screenshots, logs, or GitHub commits.

## Test focus

For the initial HS006W test, watch these entities while triggering the driveway sensor:

- `sensor.<device>_event`
- `sensor.<device>_channel`
- `sensor.<device>_channel_name`
- `sensor.<device>_last_event_change`

You can also listen for `hosmart_activity` in **Developer Tools → Events**.

The integration intentionally does not assume what an alarm event looks like yet. It preserves the receiver's raw values so real trigger behavior can be documented from evidence.

## Supported hardware

Initial development target:

- Hosmart/eMACROS HS006W
- ESP32-C6
- ESP Local Control v1.0
- Security type 1

Additional devices may work if they use the same local-control schema, but have not yet been verified.

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
```

The integration establishes a local Security1 session with the receiver and reads the `params` local-control property. The cloud and My Hosmart app are not required during normal runtime.

## License

MIT
