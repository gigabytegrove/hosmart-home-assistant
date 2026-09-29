"""Constants for the Ho-Smart integration."""

from homeassistant.const import Platform

DOMAIN = "hosmart"
DEFAULT_PORT = 8080

# Local state does not carry the driveway alarm event. Five seconds is ample
# for ordinary receiver state while avoiding the 4 Hz development load.
DEFAULT_SCAN_INTERVAL = 5.0

# The validated Ho-Smart history endpoint exposed real alarms roughly 3 seconds
# after the receiver generated them. A 3-second check keeps alarm latency low.
CLOUD_SCAN_INTERVAL = 3.0
ALARM_ACTIVE_SECONDS = 10

UDP_PORT = 50001

CONF_POP = "pop"
CONF_USER_ID = "user_id"
CONF_NODE_ID = "node_id"
CONF_MODE = "connection_mode"
CONF_CHANNEL_NAMES = "channel_names"

MODE_LOCAL = "local"
MODE_CLOUD = "cloud"
MODE_HYBRID = "hybrid"
DEFAULT_MODE = MODE_HYBRID

EVENT_ACTIVITY = "hosmart_activity"
EVENT_ALERT = "hosmart_alert"
EVENT_UDP_PACKET = "hosmart_udp_packet"

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]
