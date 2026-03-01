"""Constants for QVR Surveillance."""

DOMAIN = "qvr_surveillance"
SHORT_NAME = "QVR Surveillance"

CONF_HOST = "host"
CONF_PASSWORD = "password"
CONF_PORT = "port"
CONF_USERNAME = "username"
CONF_USE_SSL = "use_ssl"
CONF_VERIFY_SSL = "verify_ssl"
CONF_EXCLUDE_CHANNELS = "exclude_channels"
CONF_CLIENT_ID = "client_id"

DEFAULT_PORT_HTTP = 8080
DEFAULT_PORT_HTTPS = 443
RECONNECT_INTERVAL = 180
REAUTH_INTERVAL = 120  # Re-authenticate every 2 min (QVR session expiry)
DEFAULT_USE_SSL = False
DEFAULT_VERIFY_SSL = False
DEFAULT_CLIENT_ID = "qvr_surveillance"

DATA_CLIENT = "client"
DATA_CHANNELS = "channels"

SERVICE_START_RECORD = "start_recording"
SERVICE_STOP_RECORD = "stop_recording"
SERVICE_PTZ = "ptz_control"
SERVICE_RECONNECT = "reconnect"
SERVICE_CHANNEL_GUID = "guid"
SERVICE_PTZ_ACTION = "action_id"
SERVICE_PTZ_DIRECTION = "direction"
