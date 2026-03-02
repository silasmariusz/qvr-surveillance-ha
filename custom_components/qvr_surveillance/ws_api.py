"""WebSocket API for QVR Surveillance."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import DATA_CHANNELS, DATA_CLIENT, DOMAIN, EVENT_TYPES

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


def _extract_event_type(entry: dict) -> str | None:
    """
    Extract event type from log entry.
    Sources: metadata.event_name, type, event_type, or message containing IVA names.
    """
    meta = entry.get("metadata")
    if isinstance(meta, dict) and meta.get("event_name"):
        name = str(meta["event_name"]).strip().lower()
        if name in EVENT_TYPES:
            return name

    for key in ("type", "event_type", "event_name"):
        val = entry.get(key)
        if val and isinstance(val, str):
            v = val.strip().lower()
            if v in EVENT_TYPES:
                return v

    msg = entry.get("message") or entry.get("content") or ""
    if isinstance(msg, str):
        msg_lower = msg.lower()
        for et in EVENT_TYPES:
            if et in msg_lower:
                return et

    return None


def _map_logs_to_events(raw_logs: list, camera_guid: str, event_type_filter: str | None = None) -> list:
    """Map get_logs(log_type=3) response to events list for the card."""
    events = []
    for i, entry in enumerate(raw_logs):
        if isinstance(entry, dict):
            event_type = _extract_event_type(entry) or entry.get("type") or entry.get("event_type") or "surveillance"

            if event_type_filter and event_type != event_type_filter:
                continue

            ts = entry.get("time") or entry.get("timestamp")
            if ts is None:
                utc = entry.get("UTC_time") or entry.get("UTC_time_s") or entry.get("server_time")
                if utc is not None:
                    u = int(utc) if isinstance(utc, (int, float)) else int(utc)
                    ts = u // 1000 if u > 1e12 else u  # ms -> sec
                else:
                    ts = 0
            event = {
                "id": entry.get("id") or entry.get("log_id") or f"{camera_guid}_{i}_{ts}",
                "time": ts,
                "message": entry.get("message") or entry.get("content") or "",
                "type": event_type,
                "level": entry.get("level"),
                "channel_id": entry.get("channel_id") or entry.get("global_channel_id"),
            }
            meta = entry.get("metadata")
            if isinstance(meta, dict) and meta:
                event["metadata"] = meta

            events.append({k: v for k, v in event.items() if v is not None})
        elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
            if event_type_filter:
                continue
            events.append({
                "id": f"{camera_guid}_{i}",
                "time": entry[0] if isinstance(entry[0], (int, float)) else 0,
                "message": str(entry[1]) if len(entry) > 1 else "",
            })
    return events


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
    """Get surveillance events (log_type=3) for a channel, mapped for the card."""
    client = _get_client(hass, connection, msg["id"])
    if not client:
        return

    try:
        camera_guid = msg["camera"]
        logs_resp = await hass.async_add_executor_job(
            lambda: client.get_logs(
                log_type=3,
                start=msg.get("start", 0),
                max_results=msg.get("max_results", 50),
                sort_field="time",
                dir="DESC",
                start_time=msg.get("start_time"),
                end_time=msg.get("end_time"),
                global_channel_id=camera_guid,
            ),
        )
        raw_logs = logs_resp.get("logs") or logs_resp.get("log") or logs_resp.get("items") or logs_resp.get("data") or []
        if isinstance(raw_logs, dict):
            raw_logs = list(raw_logs.values()) if raw_logs else []
        events = _map_logs_to_events(
            raw_logs,
            camera_guid,
            event_type_filter=msg.get("event_type"),
        )
        connection.send_result(msg["id"], events)
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
    client = data.get(DATA_CLIENT)
    if client:
        try:
            event_capability = await hass.async_add_executor_job(client.get_event_capability)
        except Exception as ex:
            _LOGGER.debug("get_event_capability failed: %s", ex)

    connection.send_result(msg["id"], {
        "event_types": list(EVENT_TYPES),
        "cameras": cameras,
        "event_capability": event_capability,
    })
