"""
QVR API → Advanced Camera Card format converters.

Maps QVR responses to the structures ACC expects (Frigate-compatible).
We adhere to QVR API; converters adapt our data to ACC.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


# Event types from QVR IVA / logs metadata
EVENT_TYPES = frozenset({
    "alarm_input", "alarm_input_manual", "alarm_output",
    "alarm_pir", "alarm_pir_manual", "camera_motion", "motion_manual",
    "iva_intrusion", "iva_line_crossing", "iva_loitering",
    "surveillance", "event",
})


def _extract_event_type(entry: dict) -> str:
    """Extract event type from log entry. Returns known type or 'surveillance'."""
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
    msg = str(entry.get("message") or entry.get("content") or "")
    msg_lower = msg.lower()
    for et in EVENT_TYPES:
        if et in msg_lower:
            return et
    return "surveillance"


def logs_to_acc_events(
    raw_logs: list,
    camera_guid: str,
    event_type_filter: str | None = None,
) -> list[dict[str, Any]]:
    """
    Convert QVR get_logs (log_type=3) response to ACC events format.

    QVR logs are application audit; this is a workaround. Real timeline
    source should be recordings. Returns [{id, time, message, type}].
    """
    events: list[dict[str, Any]] = []
    for i, entry in enumerate(raw_logs):
        if isinstance(entry, dict):
            event_type = _extract_event_type(entry)
            if event_type_filter and event_type != event_type_filter:
                continue
            ts = entry.get("time") or entry.get("timestamp")
            if ts is None:
                utc = entry.get("UTC_time") or entry.get("UTC_time_s") or entry.get("server_time")
                if utc is not None:
                    u = int(utc) if isinstance(utc, (int, float)) else int(utc)
                    ts = u // 1000 if u > 1e12 else u
                else:
                    ts = 0
            ts = int(ts) if isinstance(ts, (int, float)) else 0
            if ts > 1e12:
                ts = ts // 1000
            event = {
                "id": entry.get("id") or entry.get("log_id") or f"{camera_guid}_{i}_{ts}",
                "time": ts,
                "message": entry.get("message") or entry.get("content") or "",
                "type": event_type,
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
                "time": int(entry[0]) if isinstance(entry[0], (int, float)) else 0,
                "message": str(entry[1]) if len(entry) > 1 else "",
                "type": "surveillance",
            })
    return events


def synthetic_recordings_summary(
    camera_guid: str,
    timezone_str: str = "UTC",
    days: int = 7,
) -> list[dict[str, Any]]:
    """
    Generate synthetic recording summary (ACC recordings/summary format).

    QVR API has no "list recordings by date". Assumes 24/7 recording.
    Returns [{day, events, hours: [{hour, duration, events}]}].
    """
    try:
        tz = __import__("zoneinfo").ZoneInfo(timezone_str)  # type: ignore
    except Exception:
        tz = timezone.utc
    now = datetime.now(tz)
    result = []
    for day_offset in range(days):
        day = now - timedelta(days=day_offset)
        hours_data = []
        for hour in range(24):
            hours_data.append({
                "hour": hour,
                "duration": 3600,
                "events": 0,
            })
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        result.append({
            "day": day_start.strftime("%Y-%m-%d"),
            "events": 0,
            "hours": hours_data,
        })
    return result


def synthetic_recording_segments(
    camera_guid: str,
    after_ts: int,
    before_ts: int,
) -> list[dict[str, Any]]:
    """
    Generate synthetic recording segments (ACC recordings/get format).

    QVR API has no segment list. Returns hourly blocks. Format:
    [{start_time, end_time, id}].
    """
    segments = []
    current = after_ts
    segment_id = 0
    while current < before_ts:
        hour_end = (current // 3600 + 1) * 3600
        segment_end = min(hour_end, before_ts)
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
