"""Constants for Generic OBD BLE."""

# Base component constants
from homeassistant.const import Platform

NAME = "Generic OBD BLE"
DOMAIN = "generic_obd_ble"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "0.1.0"

ATTRIBUTION = "Data provided by http://jsonplaceholder.typicode.com/"
ISSUE_URL = "https://github.com/hamishriley/generic-obd-ble/issues"

# Platforms
PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR]


# Configuration and options
CONF_SERVICE_UUID = "service_uuid"
CONF_CHARACTERISTIC_UUID_READ = "characteristic_uuid_read"
CONF_CHARACTERISTIC_UUID_WRITE = "characteristic_uuid_write"
CONF_QUERY_DTCS = "query_dtcs"
CONF_VEHICLE_MAKE = "vehicle_make"
CONF_VEHICLE_MODEL = "vehicle_model"
CONF_VEHICLE_YEAR = "vehicle_year"
CONF_VEHICLE_PROFILE_ID = "vehicle_profile_id"

DATA_SENSOR_META = "_sensor_meta"

# Defaults
DEFAULT_NAME = DOMAIN
DEFAULT_SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"
DEFAULT_CHARACTERISTIC_UUID_READ = "0000ffe1-0000-1000-8000-00805f9b34fb"
DEFAULT_CHARACTERISTIC_UUID_WRITE = "0000ffe1-0000-1000-8000-00805f9b34fb"
DEFAULT_VEHICLE_MAKE = "Generic"
DEFAULT_VEHICLE_MODEL = "Generic"
DEFAULT_VEHICLE_YEAR = "Generic"
DEFAULT_VEHICLE_PROFILE_ID = "none"


STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a custom integration!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""
