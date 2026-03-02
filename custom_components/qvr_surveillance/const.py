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
CONF_STREAM_INDEX = "stream_index"
CONF_ADD_SUBSTREAM = "add_substream"
CONF_EVENT_SCAN_INTERVAL = "event_scan_interval"

DEFAULT_PORT_HTTP = 8080
DEFAULT_PORT_HTTPS = 443
RECONNECT_INTERVAL = 180
DEFAULT_USE_SSL = False
DEFAULT_VERIFY_SSL = False
DEFAULT_CLIENT_ID = "qvr_surveillance"
DEFAULT_EVENT_SCAN_INTERVAL = 15  # polling get_logs dla IVA/alert latch (15–300 w config)

DATA_CLIENT = "client"
DATA_CHANNELS = "channels"

SERVICE_START_RECORD = "start_recording"
SERVICE_STOP_RECORD = "stop_recording"
SERVICE_PTZ = "ptz_control"
SERVICE_RECONNECT = "reconnect"
SERVICE_RESET_ALERT = "reset_alert"
SERVICE_CHANNEL_GUID = "guid"
SERVICE_ENTITY_ID = "entity_id"
SERVICE_CHANNEL_INDEX = "channel_index"
SERVICE_PTZ_ACTION = "action_id"
SERVICE_PTZ_DIRECTION = "direction"

# QVR log types: 1=System, 2=Connections, 3=Surveillance
LOG_TYPE_SYSTEM = 1
LOG_TYPE_CONNECTIONS = 2
LOG_TYPE_SURVEILLANCE = 3

# QVR IVA / Alarm event types (from logs/metadata, pyqvrpro fixtures)
EVENT_TYPES = (
    "alarm_input",
    "alarm_input_manual",
    "alarm_pir",
    "alarm_pir_manual",
    "alarm_output",
    "iva_crossline_manual",
    "iva_audio_detected_manual",
    "iva_tampering_detected_manual",
    "iva_intrusion_detected",
    "iva_intrusion_detected_manual",
    "iva_digital_autotrack_manual",
    "camera_motion",
    "motion_manual",
)

# Max messages in text sensor attributes
ALERT_HISTORY_MAX = 20
