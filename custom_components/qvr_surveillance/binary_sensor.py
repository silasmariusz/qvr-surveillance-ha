"""QVR Surveillance binary_sensor – IVA/Alarm detections, per event type."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .client import QVRClient, QVRConnectionError, QVRResponseError, QVRAuthError
from .const import (
    CONF_EVENT_SCAN_INTERVAL,
    DATA_CHANNELS,
    DATA_CLIENT,
    DEFAULT_EVENT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_TYPES,
    SHORT_NAME,
)
from .events import parse_recent_events_per_channel_and_type

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
    """Set up QVR Surveillance IVA/Alarm binary sensors – per camera, per event type."""
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

    cache: dict[str, dict[str, dict[str, Any]]] = {}
    data["event_cache"] = cache
    data["event_cache_meta"] = {"_last_fetch_per_guid": {}}
    data["event_cache_scan_interval"] = scan_interval

    entities: list[BinarySensorEntity] = []
    for channel in channels:
        guid = channel.get("guid", "")
        name = channel.get("name", "Camera")
        channel_index = channel.get("channel_index", 0)
        for event_type in EVENT_TYPES:
            entities.append(
                QVRSurveillanceBinarySensor(
                    name=name,
                    guid=guid,
                    channel_index=channel_index,
                    event_type=event_type,
                    client=client,
                    unique_id=f"qvr_surveillance_{client_id}_{channel_index}_{event_type}",
                    hass=hass,
                    cache=cache,
                    cache_meta=data["event_cache_meta"],
                    window_sec=scan_interval,
                )
            )

    add_entities(entities)


def _event_type_display_name(event_type: str) -> str:
    """Human-readable name for event type."""
    return event_type.replace("_", " ").title()


class QVRSurveillanceBinarySensor(BinarySensorEntity):
    """Binary sensor for specific IVA/Alarm type on a QVR channel."""

    _attr_device_class = "motion"
    _attr_should_poll = True

    def __init__(
        self,
        name: str,
        guid: str,
        channel_index: int,
        event_type: str,
        client: QVRClient,
        unique_id: str,
        hass: HomeAssistant,
        cache: dict[str, dict[str, dict[str, Any]]],
        cache_meta: dict,
        window_sec: int = 60,
    ) -> None:
        super().__init__()
        self._attr_unique_id = unique_id
        self._attr_name = f"{SHORT_NAME} {name} {_event_type_display_name(event_type)}"
        self._guid = guid
        self._channel_index = channel_index
        self._event_type = event_type
        self._client = client
        self._hass = hass
        self._cache = cache
        self._cache_meta = cache_meta
        self._window_sec = window_sec
        self._scan_interval = timedelta(seconds=window_sec)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        ev = (self._cache.get(self._guid) or {}).get(self._event_type)
        if not ev or not isinstance(ev, dict):
            return {}
        return {
            ATTR_LAST_EVENT_TYPE: self._event_type,
            ATTR_LAST_EVENT_TIME: ev.get("ts"),
            ATTR_LAST_MESSAGE: ev.get("message", ""),
        }

    def update(self) -> None:
        """Fetch recent events – runs in executor (Entity base)."""
        now = time.time()
        last_per_guid = self._cache_meta.get("_last_fetch_per_guid", {})
        last_fetch = last_per_guid.get(self._guid, 0.0)
        since_ts = int(now) - self._window_sec

        if now - last_fetch < self._window_sec and self._cache.get(self._guid):
            ev = (self._cache.get(self._guid) or {}).get(self._event_type)
            if ev and isinstance(ev, dict) and since_ts <= ev.get("ts", 0) <= int(now):
                self._attr_is_on = True
            else:
                self._attr_is_on = False
            return

        def _fetch() -> None:
            try:
                logs_resp = self._client.get_logs(
                    log_type=3,
                    start_time=since_ts,
                    max_results=100,
                    sort_field="time",
                    dir="DESC",
                    global_channel_id=self._guid,
                )
                parsed = parse_recent_events_per_channel_and_type(
                    logs_resp, since_ts, assumed_guid=self._guid
                )
                if not parsed.get(self._guid) and logs_resp:
                    logs_all = self._client.get_logs(
                        log_type=3,
                        start_time=since_ts,
                        max_results=100,
                        sort_field="time",
                        dir="DESC",
                    )
                    parsed = parse_recent_events_per_channel_and_type(logs_all, since_ts)
                if self._guid not in self._cache:
                    self._cache[self._guid] = {}
                for et, data in (parsed.get(self._guid) or {}).items():
                    prev = self._cache[self._guid].get(et)
                    if not prev or data["ts"] > prev["ts"]:
                        self._cache[self._guid][et] = data
                self._cache_meta.setdefault("_last_fetch_per_guid", {})[self._guid] = now
            except (QVRConnectionError, QVRResponseError, QVRAuthError) as ex:
                _LOGGER.debug("IVA fetch failed for %s: %s", self._guid, ex)

        try:
            _fetch()
        except Exception as ex:
            _LOGGER.debug("IVA fetch error for %s: %s", self._guid, ex)

        ev = (self._cache.get(self._guid) or {}).get(self._event_type)
        if ev and isinstance(ev, dict) and since_ts <= ev.get("ts", 0) <= int(now):
            self._attr_is_on = True
        else:
            self._attr_is_on = False
