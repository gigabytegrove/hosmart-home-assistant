# Support

Need help with Ho-Smart for Home Assistant? GitHub Issues is the best place to report a reproducible problem or request support for another device.

## Before opening an issue

Please check:

- You are running the latest release.
- Home Assistant has been restarted after updating the integration.
- The receiver IP address has not changed.
- Home Assistant can reach the receiver on the configured port.
- Your selected connection mode matches the behavior you expect.

For the verified HS006W, **Hybrid mode** is recommended because receiver status is local while driveway alarm events are obtained from Ho-Smart alarm history.

## What to include

For a bug report, include:

- Ho-Smart integration version
- Home Assistant version
- Receiver model
- Receiver firmware version
- Connection mode
- Steps to reproduce the problem
- What you expected to happen
- What actually happened
- Relevant sanitized Home Assistant logs or integration diagnostics

The more exact the information, the easier the problem is to reproduce.

## Device support requests

If your Ho-Smart, Hosmart, or eMACROS receiver is not currently verified, include:

- Exact model number
- Firmware version
- Screenshots or documentation showing the device/app behavior when useful
- Sanitized diagnostics or logs if requested

Do not assume another receiver behaves exactly like the HS006W.

## Privacy

Never post:

- Passwords
- Access tokens
- Private keys
- Full authentication responses
- Personal information you do not want public

Review diagnostics before attaching them to a public issue.

## Security problems

Do not report security vulnerabilities in a public issue. Follow [SECURITY.md](SECURITY.md) instead.
