"""
QVR API wrapper library.

Standalone, Result-based, never raises. All methods return Result(ok, data, error).

Usage:
    from qvr_api import QVRApi, Result

    api = QVRApi(host="10.0.0.1", user="admin", password="...")
    res = api.get_channels()
    if res.ok:
        channels = res.data.get("channelList", [])
"""

from .api import QVRApi
from .converters import (
    events_response_to_acc_events,
    recording_list_to_acc_segments,
    recording_list_to_acc_summary,
)
from .types import Result, err_result, ok_result

__all__ = [
    "QVRApi",
    "Result",
    "err_result",
    "ok_result",
    "events_response_to_acc_events",
    "recording_list_to_acc_summary",
    "recording_list_to_acc_segments",
]
