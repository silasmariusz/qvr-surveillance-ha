"""
QVR Surveillance event helpers – IVA/Alarm event parsing for binary_sensor.
"""

from __future__ import annotations

import time
from typing import Any

from .const import EVENT_TYPES


def _parse_timestamp(entry: dict) -> int:
    """Parse unix timestamp from log entry. Handles ms vs seconds."""
    ts = entry.get("time") or entry.get("timestamp")
    if ts is not None:
        return int(ts) if isinstance(ts, (int, float)) else 0
    utc = entry.get("UTC_time") or entry.get("UTC_time_s") or entry.get("server_time")
    if utc is not None:
        u = int(utc) if isinstance(utc, (int, float)) else int(utc)
        return u // 1000 if u > 1e12 else u
    return 0


def _extract_event_type(entry: dict) -> str | None:
    """Extract IVA/Alarm event type from log entry."""
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


def parse_recent_events_per_channel(
    logs_resp: dict,
    since_ts: int,
) -> dict[str, dict[str, Any]]:
    """
    Parse get_logs(log_type=3) response into {channel_guid: {ts, type, message}}.
    Keeps only the most recent event per channel within since_ts.
    """
    raw = logs_resp.get("logs") or logs_resp.get("log") or logs_resp.get("items") or []
    if isinstance(raw, dict):
        raw = list(raw.values()) if raw else []
    if not isinstance(raw, list):
        return {}

    result: dict[str, dict[str, Any]] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        guid = entry.get("global_channel_id") or entry.get("channel_id")
        if not guid:
            guid = str(guid) if guid is not None else ""
            if not guid:
                continue
        guid = str(guid)
        ts = _parse_timestamp(entry)
        if ts < since_ts:
            continue
        event_type = _extract_event_type(entry) or entry.get("type") or entry.get("event_type") or "surveillance"
        message = entry.get("message") or entry.get("content") or ""
        if guid not in result or result[guid]["ts"] < ts:
            result[guid] = {"ts": ts, "type": event_type, "message": str(message)}

    return result
