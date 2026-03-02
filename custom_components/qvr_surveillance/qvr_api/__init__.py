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
    logs_to_acc_events,
    synthetic_recording_segments,
    synthetic_recordings_summary,
)
from .types import Result, err_result, ok_result

__all__ = [
    "QVRApi",
    "Result",
    "err_result",
    "ok_result",
    "logs_to_acc_events",
    "synthetic_recordings_summary",
    "synthetic_recording_segments",
]
