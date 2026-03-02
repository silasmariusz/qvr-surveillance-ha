"""QVR Surveillance binary_sensor platform – IVA/Alarm detections."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .client import QVRClient, QVRConnectionError, QVRResponseError
from .const import (
    CONF_EVENT_SCAN_INTERVAL,
    DATA_CHANNELS,
    DATA_CLIENT,
    DEFAULT_EVENT_SCAN_INTERVAL,
    DOMAIN,
    SHORT_NAME,
)
from .events import parse_recent_events_per_channel

_LOGGER = logging.getLogger(__name__)

ATTR_LAST_EVENT_TYPE = "last_event_type"
ATTR_LAST_EVENT_TIME = "last_event_time"
ATTR_LAST_MESSAGE = "last_message"


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up QVR Surveillance IVA binary sensors."""
    if discovery_info is None:
        return

    data = hass.data.get(DOMAIN)
    if not data:
        return

    client: QVRClient = data[DATA_CLIENT]
    channels = data.get(DATA_CHANNELS, [])
    client_id = data.get("client_id", "qvr_surveillance")
    domain_config = config.get(DOMAIN) or {}
    scan_interval = domain_config.get(CONF_EVENT_SCAN_INTERVAL, DEFAULT_EVENT_SCAN_INTERVAL)

    cache: dict[str, dict[str, Any]] = {}
    data["event_cache"] = cache
    data["event_cache_scan_interval"] = scan_interval

    entities = []
    for channel in channels:
        guid = channel.get("guid", "")
        name = channel.get("name", "Camera")
        channel_index = channel.get("channel_index", 0)
        entities.append(
            QVRSurveillanceBinarySensor(
                name=name,
                guid=guid,
                channel_index=channel_index,
                client=client,
                unique_id=f"qvr_surveillance_{client_id}_{channel_index}_iva",
                hass=hass,
                cache=cache,
                window_sec=scan_interval,
            )
        )

    add_entities(entities)


class QVRSurveillanceBinarySensor(BinarySensorEntity):
    """Binary sensor for IVA/Alarm detections on a QVR channel."""

    _attr_device_class = "motion"
    _attr_should_poll = True

    def __init__(
        self,
        name: str,
        guid: str,
        channel_index: int,
        client: QVRClient,
        unique_id: str,
        hass: HomeAssistant,
        cache: dict[str, dict[str, Any]],
        window_sec: int = 60,
    ) -> None:
        super().__init__()
        self._attr_unique_id = unique_id
        self._attr_name = f"{SHORT_NAME} {name} IVA"
        self._guid = guid
        self._channel_index = channel_index
        self._client = client
        self._hass = hass
        self._cache = cache
        self._window_sec = window_sec
        self._cache_meta_key = "_iva_last_fetch"
        self._scan_interval = timedelta(seconds=window_sec)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        ev = self._cache.get(self._guid)
        if not ev or not isinstance(ev, dict):
            return {}
        return {
            ATTR_LAST_EVENT_TYPE: ev.get("type", ""),
            ATTR_LAST_EVENT_TIME: ev.get("ts"),
            ATTR_LAST_MESSAGE: ev.get("message", ""),
        }

    def update(self) -> None:
        """Fetch recent events and update state."""
        now = time.time()
        last_fetch = self._cache.get(self._cache_meta_key, 0.0)
        since_ts = int(now) - self._window_sec

        if now - last_fetch < self._window_sec and self._cache:
            ev = self._cache.get(self._guid)
            if ev and isinstance(ev, dict) and since_ts <= ev.get("ts", 0) <= int(now):
                self._attr_is_on = True
            else:
                self._attr_is_on = False
            return

        try:
            logs_resp = self._client.get_logs(
                log_type=3,
                start_time=since_ts,
                max_results=100,
                sort_field="time",
                dir="DESC",
            )
            parsed = parse_recent_events_per_channel(logs_resp, since_ts)
            self._cache.clear()
            self._cache.update(parsed)
            self._cache[self._cache_meta_key] = now
        except (QVRConnectionError, QVRResponseError) as ex:
            _LOGGER.debug("IVA fetch failed for %s: %s", self._guid, ex)
            return

        ev = self._cache.get(self._guid)
        if ev and isinstance(ev, dict) and since_ts <= ev.get("ts", 0) <= int(now):
            self._attr_is_on = True
        else:
            self._attr_is_on = False
