"""WebSocket API for QVR Surveillance."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import DATA_CHANNELS, DATA_CLIENT, DOMAIN, EVENT_TYPES
from .qvr_api.converters import (
    events_response_to_acc_events,
    recording_list_to_acc_segments,
    recording_list_to_acc_summary,
)

_LOGGER = logging.getLogger(__name__)


def async_setup(hass: HomeAssistant) -> None:
    """Register WebSocket handlers."""
    websocket_api.async_register_command(hass, ws_get_recordings)
    websocket_api.async_register_command(hass, ws_get_recordings_summary)
    websocket_api.async_register_command(hass, ws_get_logs)
    websocket_api.async_register_command(hass, ws_get_events)
    websocket_api.async_register_command(hass, ws_get_events_summary)


def _get_client(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg_id: int):
    """Get QVR Pro client or send error."""
    data = hass.data.get(DOMAIN)
    if not data:
        connection.send_error(msg_id, "not_found", "QVR Surveillance not configured")
        return None
    return data.get(DATA_CLIENT)


def _get_recording_summary(client, camera_guid: str, timezone_str: str) -> list:
    """get_recording_list from API only. Returns [] when no data (API has no list-by-date)."""
    raw = client.get_recording_list(camera_guid)
    if raw:
        acc = recording_list_to_acc_summary(raw, camera_guid, timezone_str)
        if acc:
            return acc
    return []


def _get_recording_segments(client, camera_guid: str, after_ts: int, before_ts: int) -> list:
    """get_recording_list with time range from API only. Returns [] when no data."""
    raw = client.get_recording_list(camera_guid, start_time=after_ts, end_time=before_ts)
    if raw:
        acc = recording_list_to_acc_segments(raw, camera_guid, after_ts, before_ts)
        if acc:
            return acc
    return []


@websocket_api.websocket_command({
    vol.Required("type"): "qvr_surveillance/recordings/summary",
    vol.Required("instance_id"): str,
    vol.Required("camera"): str,
    vol.Optional("timezone", default="UTC"): str,
})
@websocket_api.async_response
async def ws_get_recordings_summary(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Get recordings summary from API only. Returns [] when QVR has no list-by-date."""
    client = _get_client(hass, connection, msg["id"])
    if not client:
        return

    summary = _get_recording_summary(
        client,
        msg["camera"],
        msg.get("timezone", "UTC"),
    )
    connection.send_result(msg["id"], summary)


@websocket_api.websocket_command({
    vol.Required("type"): "qvr_surveillance/recordings/get",
    vol.Required("instance_id"): str,
    vol.Required("camera"): str,
    vol.Required("after"): int,
    vol.Required("before"): int,
})
@websocket_api.async_response
async def ws_get_recordings(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Get recording segments for a channel."""
    client = _get_client(hass, connection, msg["id"])
    if not client:
        return

    segments = _get_recording_segments(
        client,
        msg["camera"],
        msg["after"],
        msg["before"],
    )
    connection.send_result(msg["id"], segments)


@websocket_api.websocket_command({
    vol.Required("type"): "qvr_surveillance/logs/get",
    vol.Optional("log_type"): int,
    vol.Optional("level"): str,
    vol.Optional("start", default=0): int,
    vol.Optional("max_results", default=20): int,
    vol.Optional("sort_field", default="time"): str,
    vol.Optional("dir", default="DESC"): str,
    vol.Optional("start_time"): int,
    vol.Optional("end_time"): int,
    vol.Optional("channel_id"): str,
    vol.Optional("global_channel_id"): str,
})
@websocket_api.async_response
async def ws_get_logs(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Get QVR Pro logs via WebSocket."""
    client = _get_client(hass, connection, msg["id"])
    if not client:
        return

    try:
        logs = await hass.async_add_executor_job(
            lambda: client.get_logs(
                log_type=msg.get("log_type"),
                level=msg.get("level"),
                start=msg.get("start", 0),
                max_results=msg.get("max_results", 20),
                sort_field=msg.get("sort_field", "time"),
                dir=msg.get("dir", "DESC"),
                start_time=msg.get("start_time"),
                end_time=msg.get("end_time"),
                channel_id=msg.get("channel_id"),
                global_channel_id=msg.get("global_channel_id"),
            ),
        )
        connection.send_result(msg["id"], logs)
    except Exception as ex:
        _LOGGER.exception("Failed to get logs: %s", ex)
        connection.send_error(msg["id"], "logs_failed", str(ex))


@websocket_api.websocket_command({
    vol.Required("type"): "qvr_surveillance/events/get",
    vol.Required("instance_id"): str,
    vol.Required("camera"): str,
    vol.Optional("start", default=0): int,
    vol.Optional("max_results", default=50): int,
    vol.Optional("start_time"): int,
    vol.Optional("end_time"): int,
    vol.Optional("event_type"): str,
})
@websocket_api.async_response
async def ws_get_events(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Get timeline events from API (get_events) only. Logs are for HA sensors, NOT for timeline."""
    client = _get_client(hass, connection, msg["id"])
    if not client:
        return

    try:
        camera_guid = msg["camera"]
        events_raw = await hass.async_add_executor_job(client.get_events)
        if not events_raw:
            connection.send_result(msg["id"], [])
            return
        acc_events = events_response_to_acc_events(
            events_raw,
            camera_guid,
            event_type_filter=msg.get("event_type"),
        )
        connection.send_result(msg["id"], acc_events if acc_events else [])
    except Exception as ex:
        _LOGGER.exception("Failed to get events: %s", ex)
        connection.send_error(msg["id"], "events_failed", str(ex))


@websocket_api.websocket_command({
    vol.Required("type"): "qvr_surveillance/events/summary",
    vol.Required("instance_id"): str,
})
@websocket_api.async_response
async def ws_get_events_summary(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Get events filter metadata (event types, cameras, capability) for the card."""
    data = hass.data.get(DOMAIN)
    if not data:
        connection.send_error(msg["id"], "not_found", "QVR Surveillance not configured")
        return

    channels = data.get(DATA_CHANNELS, [])
    cameras = [
        {"guid": ch.get("guid"), "name": ch.get("channel_name") or ch.get("name") or f"Channel {ch.get('channel_index', 0) + 1}"}
        for ch in channels
        if ch.get("guid")
    ]

    event_capability = {}
    event_types_set = set(EVENT_TYPES)
    client = data.get(DATA_CLIENT)
    if client:
        try:
            event_capability = await hass.async_add_executor_job(client.get_event_capability)
            if isinstance(event_capability, dict):
                for val in event_capability.values():
                    if isinstance(val, (list, tuple)):
                        for v in val:
                            if isinstance(v, str) and v.strip():
                                event_types_set.add(v.strip().lower())
                    elif isinstance(val, dict):
                        for k in val.keys():
                            if isinstance(k, str) and k.strip():
                                event_types_set.add(k.strip().lower())
        except Exception as ex:
            _LOGGER.debug("get_event_capability failed: %s", ex)

    connection.send_result(msg["id"], {
        "event_types": sorted(event_types_set),
        "cameras": cameras,
        "event_capability": event_capability,
    })
