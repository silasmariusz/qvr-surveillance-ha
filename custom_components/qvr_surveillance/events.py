"""
QVR Surveillance event helpers – IVA/Alarm event parsing.
"""

from __future__ import annotations

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
    """Extract IVA/Alarm event type from log entry. Returns known types or metadata.event_name (LPR etc)."""
    meta = entry.get("metadata")
    if isinstance(meta, dict) and meta.get("event_name"):
        name = str(meta["event_name"]).strip().lower()
        if name in EVENT_TYPES:
            return name
        return name  # Pass through unknown types (e.g. LPR) for text sensors

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


def _extract_guid(entry: dict, channel_guid_map: dict[str, str] | None = None) -> str | None:
    """Extract channel GUID from log entry. channel_guid_map: channel_index -> guid for fallback."""
    guid = entry.get("global_channel_id") or entry.get("channel_id") or entry.get("channel_guid")
    if guid:
        return str(guid)
    idx = entry.get("channel_index") or entry.get("channelIndex")
    if channel_guid_map and idx is not None:
        return channel_guid_map.get(str(idx)) or channel_guid_map.get(int(idx) if isinstance(idx, (int, float)) else idx)
    return None


def parse_recent_events_per_channel(
    logs_resp: dict,
    since_ts: int,
    channel_guid_map: dict | None = None,
) -> dict[str, dict[str, Any]]:
    """Parse into {channel_guid: {ts, type, message}} – most recent per channel."""
    per_type = parse_recent_events_per_channel_and_type(logs_resp, since_ts, channel_guid_map)
    result: dict[str, dict[str, Any]] = {}
    for guid, types_map in per_type.items():
        best = None
        for et, data in types_map.items():
            if best is None or data["ts"] > best["ts"]:
                best = {"ts": data["ts"], "type": et, "message": data["message"]}
        if best:
            result[guid] = best
    return result


def parse_recent_events_per_channel_and_type(
    logs_resp: dict,
    since_ts: int,
    channel_guid_map: dict | None = None,
    assumed_guid: str | None = None,
) -> dict[str, dict[str, dict[str, Any]]]:
    """
    Parse into {guid: {event_type: {ts, message}}} for per-type binary sensors.
    When assumed_guid is set (e.g. we filtered by that channel), use it for entries without guid.
    """
    raw = logs_resp.get("logs") or logs_resp.get("log") or logs_resp.get("items") or logs_resp.get("data") or []
    if isinstance(raw, dict):
        raw = list(raw.values()) if raw else []
    if not isinstance(raw, list):
        return {}

    result: dict[str, dict[str, dict[str, Any]]] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        guid = _extract_guid(entry, channel_guid_map) or assumed_guid
        if not guid:
            continue
        guid = str(guid)
        ts = _parse_timestamp(entry)
        if ts < since_ts:
            continue
        event_type = _extract_event_type(entry) or entry.get("type") or entry.get("event_type") or "surveillance"
        message = entry.get("message") or entry.get("content") or ""

        if guid not in result:
            result[guid] = {}
        prev = result[guid].get(event_type)
        if not prev or prev["ts"] < ts:
            result[guid][event_type] = {"ts": ts, "message": str(message)}

    return result


def parse_log_entries_to_messages(
    logs_resp: dict,
    max_count: int = 20,
    assumed_guid: str | None = None,
) -> list[dict[str, Any]]:
    """
    Parse logs into list of {time, type, message, channel_guid} for text sensors.
    assumed_guid: when response was filtered by channel, use for entries without guid.
    """
    raw = logs_resp.get("logs") or logs_resp.get("log") or logs_resp.get("items") or logs_resp.get("data") or []
    if isinstance(raw, dict):
        raw = list(raw.values()) if raw else []
    if not isinstance(raw, list):
        return []

    out: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict) or len(out) >= max_count:
            continue
        ts = _parse_timestamp(entry)
        event_type = _extract_event_type(entry) or entry.get("type") or entry.get("event_type") or "event"
        message = entry.get("message") or entry.get("content") or ""
        guid = _extract_guid(entry) or assumed_guid
        out.append({
            "time": ts,
            "type": event_type,
            "message": str(message),
            "channel_guid": guid,
        })
    return out
