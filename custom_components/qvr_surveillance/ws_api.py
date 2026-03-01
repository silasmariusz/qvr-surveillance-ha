"""WebSocket API for QVR Surveillance."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import DATA_CHANNELS, DATA_CLIENT, DOMAIN

_LOGGER = logging.getLogger(__name__)


def async_setup(hass: HomeAssistant) -> None:
    """Register WebSocket handlers."""
    websocket_api.async_register_command(hass, ws_get_recordings)
    websocket_api.async_register_command(hass, ws_get_recordings_summary)
    websocket_api.async_register_command(hass, ws_get_logs)


def _get_client(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg_id: int):
    """Get QVR Pro client or send error."""
    data = hass.data.get(DOMAIN)
    if not data:
        connection.send_error(msg_id, "not_found", "QVR Surveillance not configured")
        return None
    return data.get(DATA_CLIENT)


def _generate_recording_summary(camera_guid: str, timezone_str: str) -> list:
    """
    Generate synthetic recording summary.
    QVR Pro API doesn't expose "list recordings by date" - assume 24/7 recording
    for the last 7 days (typical NVR behavior).
    """
    try:
        tz = __import__("zoneinfo").ZoneInfo(timezone_str)
    except Exception:
        tz = timezone.utc

    now = datetime.now(tz)
    result = []

    for day_offset in range(7):
        day = now - timedelta(days=day_offset)
        hours_data = []
        for hour in range(24):
            hours_data.append({
                "hour": hour,
                "duration": 3600,
                "events": 0,
            })

        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        total_events = 0
        result.append({
            "day": day_start.strftime("%Y-%m-%d"),
            "events": total_events,
            "hours": hours_data,
        })

    return result


def _generate_recording_segments(camera_guid: str, after_ts: int, before_ts: int) -> list:
    """
    Generate synthetic hourly recording segments for the time range.
    """
    segments = []
    current = after_ts
    segment_id = 0

    while current < before_ts:
        segment_end = min(
            (current // 3600 + 1) * 3600,
            before_ts
        )
        if segment_end <= current:
            segment_end = current + 3600

        segments.append({
            "start_time": current,
            "end_time": segment_end,
            "id": f"{camera_guid}_{segment_id}_{current}",
        })
        current = segment_end
        segment_id += 1

    return segments


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
    """Get recordings summary for a channel (synthetic - assumes 24/7 recording)."""
    client = _get_client(hass, connection, msg["id"])
    if not client:
        return

    summary = _generate_recording_summary(
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

    segments = _generate_recording_segments(
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
        logs = client.get_logs(
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
        )
        connection.send_result(msg["id"], logs)
    except Exception as ex:
        _LOGGER.exception("Failed to get logs: %s", ex)
        connection.send_error(msg["id"], "logs_failed", str(ex))
