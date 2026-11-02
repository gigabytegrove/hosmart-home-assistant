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
CONF_RELEASE_CHANNEL = "release_channel"

CONF_QUIET_ENABLED = "quiet_enabled"
CONF_QUIET_START = "quiet_start"
CONF_QUIET_END = "quiet_end"
CONF_QUIET_ACTION = "quiet_action"
CONF_CHANNEL_QUIET = "channel_quiet"
CHANNEL_INHERIT = "inherit"
CHANNEL_ALWAYS_ACTIVE = "always_active"
CHANNEL_CUSTOM = "custom"
CHANNEL_MODES = (CHANNEL_INHERIT, CHANNEL_ALWAYS_ACTIVE, CHANNEL_CUSTOM)
QUIET_ACTION_MUTE = "mute"
QUIET_ACTION_POWER = "power_off"
DEFAULT_QUIET_ACTION = QUIET_ACTION_MUTE
DEFAULT_QUIET_START = "22:00:00"
DEFAULT_QUIET_END = "07:00:00"

MODE_LOCAL = "local"
MODE_CLOUD = "cloud"
MODE_HYBRID = "hybrid"
DEFAULT_MODE = MODE_HYBRID

EVENT_ACTIVITY = "hosmart_activity"
EVENT_ALERT = "hosmart_alert"
EVENT_UDP_PACKET = "hosmart_udp_packet"

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.TIME,
    Platform.BUTTON,
]
