"""QVR Surveillance binary_sensor – IVA/Alarm detections, per event type; alert latch (warning/error)."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .client import QVRClient, QVRConnectionError, QVRResponseError, QVRAuthError
from .const import (
    CONF_EVENT_SCAN_INTERVAL,
    DATA_CHANNELS,
    DATA_CLIENT,
    DEFAULT_EVENT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_TYPES,
    LOG_TYPE_CONNECTIONS,
    LOG_TYPE_SURVEILLANCE,
    LOG_TYPE_SYSTEM,
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
    # Alert latch – system (log 1+2) + per camera (log 3)
    latch_state = {}
    data.setdefault("alert_latch_state", latch_state)
    entities.append(
        QVRAlertLatchBinarySensor(
            name="Alert Latch",
            client=client,
            unique_id=f"qvr_surveillance_{client_id}_alert_latch",
            hass=hass,
            log_types=(LOG_TYPE_SYSTEM, LOG_TYPE_CONNECTIONS),
            guid=None,
            latch_state=latch_state,
            scan_interval=scan_interval,
        )
    )
    for channel in channels:
        guid = channel.get("guid", "")
        name = channel.get("name", "Camera")
        channel_index = channel.get("channel_index", 0)
        entities.append(
            QVRAlertLatchBinarySensor(
                name=name,
                client=client,
                unique_id=f"qvr_surveillance_{client_id}_{channel_index}_alert_latch",
                hass=hass,
                log_types=(LOG_TYPE_SURVEILLANCE,),
                guid=guid,
                latch_state=latch_state,
                scan_interval=scan_interval,
            )
        )
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


def _has_warning_or_error(entry: dict) -> bool:
    """Check if log entry has level warning or error."""
    level = entry.get("level")
    if level is None:
        return False
    if isinstance(level, (int, float)):
        return int(level) >= 2  # assume 0=info, 1=warn, 2=error
    s = str(level).lower()
    return s in ("warning", "error", "warn", "err")


class QVRAlertLatchBinarySensor(BinarySensorEntity, RestoreEntity):
    """Binary sensor: on when warning/error in logs; off after manual reset via service."""

    _attr_device_class = "problem"
    _attr_icon = "mdi:alert-circle"
    _attr_should_poll = True

    def __init__(
        self,
        name: str,
        client: QVRClient,
        unique_id: str,
        hass: HomeAssistant,
        log_types: tuple[int, ...],
        guid: str | None,
        latch_state: dict,
        scan_interval: int = 15,
    ) -> None:
        super().__init__()
        self._attr_unique_id = unique_id
        self._attr_name = f"{SHORT_NAME} {name} Alert Latch" if name != "Alert Latch" else f"{SHORT_NAME} Alert Latch"
        self._client = client
        self._hass = hass
        self._log_types = log_types
        self._guid = guid
        self._latch_state = latch_state
        self._scan_interval = timedelta(seconds=scan_interval)
        self._last_message = ""

    async def async_added_to_hass(self) -> None:
        """Restore state on startup; register for reset_alert service."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state and state.state == "on":
            self._attr_is_on = True
            self._last_message = state.attributes.get("last_message", "")
        registry = self.hass.data.setdefault(DOMAIN, {}).setdefault("alert_latch_registry", {})
        registry[self.entity_id] = self

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"last_message": self._last_message}

    def update(self) -> None:
        """Poll logs; if warning/error and not yet latched, set on. Stays on until reset."""
        if self._attr_is_on:
            return  # Latched – user must reset via service
        since_ts = int(time.time()) - 86400  # last 24h
        for log_type in self._log_types:
            try:
                logs_resp = self._client.get_logs(
                    log_type=log_type,
                    level="warning",  # filter server-side if QVR supports it
                    start_time=since_ts,
                    max_results=50,
                    sort_field="time",
                    dir="DESC",
                    global_channel_id=self._guid,
                )
                raw = logs_resp.get("logs") or logs_resp.get("log") or logs_resp.get("items") or logs_resp.get("data") or []
                if isinstance(raw, dict):
                    raw = list(raw.values()) if raw else []
                for entry in raw:
                    if isinstance(entry, dict) and _has_warning_or_error(entry):
                        self._attr_is_on = True
                        self._last_message = str(entry.get("message", entry.get("content", "")))[:500]
                        return
            except (QVRConnectionError, QVRResponseError, QVRAuthError) as ex:
                _LOGGER.debug("Alert latch fetch failed for log_type=%s: %s", log_type, ex)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister from reset_alert service."""
        registry = self.hass.data.get(DOMAIN, {}).get("alert_latch_registry", {})
        registry.pop(self.entity_id, None)

    def reset_alert(self) -> None:
        """Reset latch to off – called by qvr_surveillance.reset_alert service."""
        self._attr_is_on = False
        self._last_message = ""
        self.schedule_update_ha_state()


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
