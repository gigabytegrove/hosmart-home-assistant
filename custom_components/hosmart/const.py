"""Constants for the Hosmart integration."""

from homeassistant.const import Platform

DOMAIN = "hosmart"
DEFAULT_PORT = 8080

# Development capture rate. The initial HS006W field test deliberately samples
# four times per second so a short-lived driveway event is much less likely to
# fall between polls. This can be relaxed once real event timing is measured.
DEFAULT_SCAN_INTERVAL = 0.25

UDP_PORT = 50001

CONF_POP = "pop"

EVENT_ACTIVITY = "hosmart_activity"
EVENT_UDP_PACKET = "hosmart_udp_packet"

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]
