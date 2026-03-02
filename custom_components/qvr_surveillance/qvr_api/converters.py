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


def events_response_to_acc_events(
    raw: dict | list,
    camera_guid: str,
    event_type_filter: str | None = None,
) -> list[dict[str, Any]] | None:
    """
    Convert get_events() response to ACC events. Returns None if format unrecognized.
    Expected: {events: [...]} or {items: [...]} or list of dicts with id/time/type.
    Filters by camera_guid when entry has camera/guid/channel_id.
    """
    items: list = []
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = raw.get("events") or raw.get("items") or raw.get("data") or raw.get("recordings") or []
    if not isinstance(items, list):
        return None
    events: list[dict[str, Any]] = []
    for i, entry in enumerate(items):
        if not isinstance(entry, dict):
            continue
        if camera_guid:
            entry_cam = entry.get("camera") or entry.get("guid") or entry.get("channel_id") or entry.get("channel_guid")
            if entry_cam is not None and str(entry_cam).strip() and str(entry_cam) != str(camera_guid):
                continue
        ev_type = _extract_event_type(entry)
        if event_type_filter and ev_type != event_type_filter:
            continue
        ts = entry.get("time") or entry.get("start_time") or entry.get("timestamp")
        if ts is None:
            ts = 0
        ts = int(ts) if isinstance(ts, (int, float)) else 0
        if ts > 1e12:
            ts = ts // 1000
        ev = {
            "id": entry.get("id") or f"{camera_guid}_ev_{i}_{ts}",
            "time": ts,
            "message": entry.get("message") or entry.get("content") or "",
            "type": ev_type,
        }
        if entry.get("metadata"):
            ev["metadata"] = entry["metadata"]
        events.append({k: v for k, v in ev.items() if v is not None})
    return events


def recording_list_to_acc_summary(
    raw: dict,
    camera_guid: str,
    timezone_str: str = "UTC",
) -> list[dict[str, Any]] | None:
    """
    Convert get_recording_list() to ACC recordings/summary. Returns None if unrecognized.
    Expected: {days: [...]} or {summary: [...]} with day/hour structure.
    """
    if not isinstance(raw, dict):
        return None
    days_data = raw.get("days") or raw.get("summary") or raw.get("recordings_summary")
    if not isinstance(days_data, list) or not days_data:
        return None
    result = []
    for day_ent in days_data:
        if not isinstance(day_ent, dict):
            continue
        day_str = day_ent.get("day") or day_ent.get("date")
        hours_raw = day_ent.get("hours") or day_ent.get("segments")
        if not day_str or not isinstance(hours_raw, list):
            continue
        hours_data = []
        for h in hours_raw:
            if isinstance(h, dict):
                hours_data.append({
                    "hour": h.get("hour", 0),
                    "duration": h.get("duration", 3600),
                    "events": h.get("events", 0),
                })
            elif isinstance(h, (int, float)):
                hours_data.append({"hour": int(h), "duration": 3600, "events": 0})
        if hours_data:
            result.append({
                "day": str(day_str)[:10],
                "events": day_ent.get("events", 0),
                "hours": hours_data,
            })
    return result if result else None


def recording_list_to_acc_segments(
    raw: dict | list,
    camera_guid: str,
    after_ts: int,
    before_ts: int,
) -> list[dict[str, Any]] | None:
    """
    Convert get_recording_list(guid, start_time, end_time) to ACC segments. Returns None if unrecognized.
    Expected: {segments: [...]} or list of {start_time, end_time, id}.
    """
    items: list = []
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = raw.get("segments") or raw.get("recordings") or raw.get("items") or []
    if not isinstance(items, list):
        return None
    segments = []
    for i, ent in enumerate(items):
        if not isinstance(ent, dict):
            continue
        start_t = ent.get("start_time") or ent.get("start")
        end_t = ent.get("end_time") or ent.get("end")
        if start_t is None or end_t is None:
            continue
        start_t, end_t = int(start_t), int(end_t)
        if end_t <= after_ts or start_t >= before_ts:
            continue
        seg_id = ent.get("id") or f"{camera_guid}_seg_{i}_{start_t}"
        segments.append({
            "start_time": start_t,
            "end_time": end_t,
            "id": str(seg_id),
        })
    return segments if segments else None


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
