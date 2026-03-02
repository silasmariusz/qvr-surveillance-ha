"""QVR Surveillance text sensors – last alert messages per camera and system alerts."""

from __future__ import annotations

import logging
import time
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .client import QVRClient, QVRConnectionError, QVRResponseError, QVRAuthError
from .const import (
    ALERT_HISTORY_MAX,
    DATA_CHANNELS,
    DATA_CLIENT,
    DOMAIN,
    LOG_TYPE_CONNECTIONS,
    LOG_TYPE_SYSTEM,
    LOG_TYPE_SURVEILLANCE,
    SHORT_NAME,
)
from .events import parse_log_entries_to_messages

_LOGGER = logging.getLogger(__name__)

ATTR_RECENT_MESSAGES = "recent_messages"
ATTR_COUNT = "count"


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up QVR Surveillance alert text sensors."""
    if discovery_info is None:
        return

    data = hass.data.get(DOMAIN)
    if not data:
        return

    client: QVRClient = data[DATA_CLIENT]
    channels = data.get(DATA_CHANNELS, [])
    client_id = data.get("client_id", "qvr_surveillance")

    entities: list[SensorEntity] = []

    for channel in channels:
        guid = channel.get("guid", "")
        name = channel.get("name", "Camera")
        channel_index = channel.get("channel_index", 0)
        entities.append(
            QVRSurveillanceAlertSensor(
                name=name,
                guid=guid,
                channel_index=channel_index,
                client=client,
                unique_id=f"qvr_surveillance_{client_id}_{channel_index}_alerts",
                hass=hass,
                log_type=LOG_TYPE_SURVEILLANCE,
            )
        )

    entities.append(
        QVRSystemAlertSensor(
            client=client,
            unique_id=f"qvr_surveillance_{client_id}_system_alerts",
            hass=hass,
        )
    )
    entities.append(
        QVRConnectionAlertSensor(
            client=client,
            unique_id=f"qvr_surveillance_{client_id}_connection_alerts",
            hass=hass,
        )
    )

    add_entities(entities)


class QVRSurveillanceAlertSensor(SensorEntity):
    """Text sensor with last surveillance alert messages for a camera."""

    _attr_icon = "mdi:alert-circle"

    def __init__(
        self,
        name: str,
        guid: str,
        channel_index: int,
        client: QVRClient,
        unique_id: str,
        hass: HomeAssistant,
        log_type: int,
    ) -> None:
        super().__init__()
        self._attr_unique_id = unique_id
        self._attr_name = f"{SHORT_NAME} {name} Alerts"
        self._guid = guid
        self._channel_index = channel_index
        self._client = client
        self._hass = hass
        self._log_type = log_type
        self._messages: list[dict] = []
        self._scan_interval = timedelta(seconds=60)

    @property
    def native_value(self) -> str:
        if not self._messages:
            return ""
        last = self._messages[0]
        return str(last.get("message", ""))[:255]

    @property
    def extra_state_attributes(self) -> dict:
        return {
            ATTR_RECENT_MESSAGES: [
                {"time": m.get("time"), "type": m.get("type"), "message": m.get("message", "")[:200]}
                for m in self._messages[:ALERT_HISTORY_MAX]
            ],
            ATTR_COUNT: len(self._messages),
        }

    def update(self) -> None:
        since_ts = int(time.time()) - 3600
        try:
            logs_resp = self._client.get_logs(
                log_type=self._log_type,
                start_time=since_ts,
                max_results=50,
                sort_field="time",
                dir="DESC",
                global_channel_id=self._guid,
            )
            msgs = parse_log_entries_to_messages(
                logs_resp, max_count=ALERT_HISTORY_MAX, assumed_guid=self._guid
            )
            self._messages = msgs
        except (QVRConnectionError, QVRResponseError, QVRAuthError) as ex:
            _LOGGER.debug("Alerts fetch failed for %s: %s", self._guid, ex)


class QVRSystemAlertSensor(SensorEntity):
    """Text sensor with last QVR system alerts (log_type=1)."""

    _attr_icon = "mdi:server-alert"
    _attr_name = f"{SHORT_NAME} System Alerts"

    def __init__(
        self,
        client: QVRClient,
        unique_id: str,
        hass: HomeAssistant,
    ) -> None:
        super().__init__()
        self._attr_unique_id = unique_id
        self._client = client
        self._hass = hass
        self._messages: list[dict] = []
        self._scan_interval = timedelta(seconds=120)

    @property
    def native_value(self) -> str:
        if not self._messages:
            return ""
        last = self._messages[0]
        return str(last.get("message", ""))[:255]

    @property
    def extra_state_attributes(self) -> dict:
        return {
            ATTR_RECENT_MESSAGES: [
                {"time": m.get("time"), "type": m.get("type"), "message": m.get("message", "")[:200]}
                for m in self._messages[:ALERT_HISTORY_MAX]
            ],
            ATTR_COUNT: len(self._messages),
        }

    def update(self) -> None:
        since_ts = int(time.time()) - 86400
        try:
            logs_resp = self._client.get_logs(
                log_type=LOG_TYPE_SYSTEM,
                start_time=since_ts,
                max_results=50,
                sort_field="time",
                dir="DESC",
            )
            self._messages = parse_log_entries_to_messages(logs_resp, max_count=ALERT_HISTORY_MAX)
        except (QVRConnectionError, QVRResponseError, QVRAuthError) as ex:
            _LOGGER.debug("System alerts fetch failed: %s", ex)


class QVRConnectionAlertSensor(SensorEntity):
    """Text sensor with last QVR connection alerts (log_type=2 – client connect/disconnect)."""

    _attr_icon = "mdi:connection"
    _attr_name = f"{SHORT_NAME} Connection Alerts"

    def __init__(
        self,
        client: QVRClient,
        unique_id: str,
        hass: HomeAssistant,
    ) -> None:
        super().__init__()
        self._attr_unique_id = unique_id
        self._client = client
        self._hass = hass
        self._messages: list[dict] = []
        self._scan_interval = timedelta(seconds=120)

    @property
    def native_value(self) -> str:
        if not self._messages:
            return ""
        last = self._messages[0]
        return str(last.get("message", ""))[:255]

    @property
    def extra_state_attributes(self) -> dict:
        return {
            ATTR_RECENT_MESSAGES: [
                {"time": m.get("time"), "type": m.get("type"), "message": m.get("message", "")[:200]}
                for m in self._messages[:ALERT_HISTORY_MAX]
            ],
            ATTR_COUNT: len(self._messages),
        }

    def update(self) -> None:
        since_ts = int(time.time()) - 86400
        try:
            logs_resp = self._client.get_logs(
                log_type=LOG_TYPE_CONNECTIONS,
                start_time=since_ts,
                max_results=50,
                sort_field="time",
                dir="DESC",
            )
            self._messages = parse_log_entries_to_messages(logs_resp, max_count=ALERT_HISTORY_MAX)
        except (QVRConnectionError, QVRResponseError, QVRAuthError) as ex:
            _LOGGER.debug("Connection alerts fetch failed: %s", ex)
