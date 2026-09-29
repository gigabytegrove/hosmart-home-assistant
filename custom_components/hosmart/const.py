"""Constants for the Hosmart integration."""

from homeassistant.const import Platform

DOMAIN = "hosmart"
DEFAULT_PORT = 8080
DEFAULT_SCAN_INTERVAL = 0.5
UDP_PORT = 50001

CONF_POP = "pop"

EVENT_ACTIVITY = "hosmart_activity"

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]
