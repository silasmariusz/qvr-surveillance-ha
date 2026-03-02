"""
QVR API wrapper – all endpoints, all param variants, Result-based (never raises).
Standalone HTTP layer for tools/qvr_api_probe.py and other consumers.
"""

from __future__ import annotations

import base64
from typing import Any

try:
    import requests
except ImportError:
    requests = None  # type: ignore

from .types import Result, err_result, ok_result

API_VERSION = "1.1.0"
RECORDING_TIMEOUT = 600


def _ensure_requests() -> None:
    if requests is None:
        raise ImportError("qvr_api requires 'requests'. pip install requests")


def _auth_sid(base_url: str, user: str, password: str) -> str:
    """Get session ID from authLogin.cgi."""
    import xml.etree.ElementTree as ET

    url = f"{base_url}/cgi-bin/authLogin.cgi"
    pwd_b64 = base64.b64encode(password.encode("ascii")).decode("ascii")
    params = {"user": user, "pwd": pwd_b64, "serviceKey": 1, "verify": 0}
    r = requests.get(url, params=params, timeout=10, verify=False)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    sid = root.find(".//authSid")
    if sid is None or not sid.text:
        raise ValueError("No authSid in response")
    return sid.text


class QVRApi:
    """
    QVR Pro / QVR Elite / QVR Surveillance API wrapper.
    All methods return Result(ok, data, error). Never raises.
    """

    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        port: int = 8080,
        protocol: str = "http",
    ) -> None:
        _ensure_requests()
        self._host = host
        self._user = user
        self._password = password
        self._port = port
        self._protocol = protocol
        self._base_url = f"{protocol}://{host}:{port}"
        self._sid: str | None = None
        self._qvr_path: str = "/qvrpro"

    def _ensure_auth(self) -> bool:
        """Ensure we have a valid SID. Returns True on success."""
        if self._sid:
            return True
        try:
            self._sid = _auth_sid(self._base_url, self._user, self._password)
            return True
        except Exception as e:
            return False

    def _discover_qvr_path(self) -> bool:
        """Fetch /qvrentry to get API path."""
        try:
            r = requests.get(f"{self._base_url}/qvrentry", timeout=10, verify=False)
            if not r.ok:
                return False
            data = r.json()
            if data.get("is_qvp") == "yes":
                self._qvr_path = "/qvrpro"
            elif data.get("fw_web_ui_prefix"):
                prefix = data["fw_web_ui_prefix"].strip("/")
                self._qvr_path = f"/{prefix}" if prefix else "/qvrelite"
            else:
                self._qvr_path = "/qvrelite"
            return True
        except Exception:
            self._qvr_path = "/qvrpro"
            return False

    def _get(
        self,
        path: str,
        params: dict | None = None,
        timeout: int = 30,
    ) -> Result:
        """GET request. Returns Result with dict/list/bytes/str or error."""
        try:
            if not self._ensure_auth():
                return err_result("Authentication failed")
            url = f"{self._base_url}{path}"
            p = dict(params or {})
            p["sid"] = self._sid
            p["ver"] = API_VERSION
            r = requests.get(url, params=p, timeout=timeout, verify=False)
            ct = r.headers.get("content-type", "")
            if "application/json" in ct:
                return ok_result(r.json())
            if "image/" in ct or "video/" in ct:
                return ok_result(r.content)
            return ok_result(r.text if r.text else "")
        except Exception as e:
            return err_result(str(e))

    def _post(self, path: str, body: dict, timeout: int = 30) -> Result:
        """POST request."""
        try:
            if not self._ensure_auth():
                return err_result("Authentication failed")
            url = f"{self._base_url}{path}"
            params = {"sid": self._sid, "ver": API_VERSION}
            r = requests.post(url, params=params, json=body, timeout=timeout, verify=False)
            ct = r.headers.get("content-type", "")
            if "application/json" in ct:
                return ok_result(r.json())
            return ok_result(r.text if r.text else "")
        except Exception as e:
            return err_result(str(e))

    def _put(
        self,
        path: str,
        params: dict | None = None,
        timeout: int = 30,
    ) -> Result:
        """PUT request."""
        try:
            if not self._ensure_auth():
                return err_result("Authentication failed")
            url = f"{self._base_url}{path}"
            p = dict(params or {})
            p["sid"] = self._sid
            p["ver"] = API_VERSION
            r = requests.put(url, params=p, timeout=timeout, verify=False)
            ct = r.headers.get("content-type", "")
            if "application/json" in ct and r.text:
                return ok_result(r.json())
            return ok_result(r.text if r.text else "")
        except Exception as e:
            return err_result(str(e))

    # --- Discovery / Entry ---

    def get_qvrentry(self) -> Result:
        """Discover QVR API path. Returns fw_web_ui_prefix, is_qvp, etc."""
        try:
            r = requests.get(f"{self._base_url}/qvrentry", timeout=10, verify=False)
            if not r.ok:
                return err_result(f"HTTP {r.status_code}")
            return ok_result(r.json())
        except Exception as e:
            return err_result(str(e))

    def ensure_qvr_path(self) -> Result:
        """Fetch qvrentry and set internal qvr_path. Call before other endpoints."""
        try:
            res = self.get_qvrentry()
            if not res.ok:
                return res
            data = res.data if isinstance(res.data, dict) else {}
            if data.get("is_qvp") == "yes":
                self._qvr_path = "/qvrpro"
            elif data.get("fw_web_ui_prefix"):
                prefix = str(data["fw_web_ui_prefix"]).strip("/")
                self._qvr_path = f"/{prefix}" if prefix else "/qvrelite"
            else:
                self._qvr_path = "/qvrelite"
            return ok_result({"qvr_path": self._qvr_path})
        except Exception as e:
            return err_result(str(e))

    # --- Channels ---

    def get_channels(self) -> Result:
        """List channels. Returns channelList or channels."""
        self._discover_qvr_path()
        return self._get(f"{self._qvr_path}/qshare/StreamingOutput/channels")

    def get_channel_streams(self, guid: str) -> Result:
        """Get available streams for a channel (Main=0, Sub=1, Mobile=2)."""
        self._discover_qvr_path()
        return self._get(f"{self._qvr_path}/qshare/StreamingOutput/channel/{guid}/streams")

    def get_live_stream(
        self,
        guid: str,
        stream: int = 0,
        protocol: str = "rtsp",
    ) -> Result:
        """Get live stream URL. stream: 0=Main, 1=Substream, 2=Mobile."""
        self._discover_qvr_path()
        path = f"{self._qvr_path}/qshare/StreamingOutput/channel/{guid}/stream/{stream}/liveStream"
        return self._post(path, {"protocol": protocol})

    # --- Snapshot ---

    def get_snapshot(self, guid: str) -> Result:
        """Get camera snapshot (JPEG bytes)."""
        self._discover_qvr_path()
        res = self._get(f"{self._qvr_path}/camera/snapshot/{guid}")
        if res.ok and isinstance(res.data, bytes) and len(res.data) > 10:
            return res
        if res.ok and not isinstance(res.data, bytes):
            return err_result("Snapshot returned non-image (JSON/text)", data=res.data)
        return res

    # --- Recording (all URI × param variants) ---

    def get_recording(
        self,
        guid: str,
        *,
        channel_id: int = 0,
        time_sec: int | None = None,
        time_ms: int | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        start: int | None = None,
        end: int | None = None,
        pre_period: int = 10000,
        post_period: int = 5000,
        uri_variant: str = "recordingfile/0",
    ) -> Result:
        """
        Fetch recording. Specify one of: (time_sec), (time_ms), (start_time,end_time), (start,end).
        uri_variant: "recordingfile/0" | "recordingfile/1" | "recording/"
        """
        self._discover_qvr_path()
        params: dict[str, Any] = {"pre_period": pre_period, "post_period": post_period}
        if time_sec is not None:
            params["time"] = time_sec
        elif time_ms is not None:
            params["time"] = time_ms
        elif start_time is not None and end_time is not None:
            params["start_time"] = start_time
            params["end_time"] = end_time
        elif start is not None and end is not None:
            params["start"] = start
            params["end"] = end
        else:
            return err_result("Specify time_sec, time_ms, or (start_time,end_time) or (start,end)")

        if uri_variant == "recordingfile/0":
            path = f"{self._qvr_path}/camera/recordingfile/{guid}/0"
        elif uri_variant == "recordingfile/1":
            path = f"{self._qvr_path}/camera/recordingfile/{guid}/1"
        elif uri_variant == "recording/":
            path = f"{self._qvr_path}/camera/recording/{guid}"
        else:
            path = f"{self._qvr_path}/camera/recordingfile/{guid}/{channel_id}"

        return self._get(path, params, timeout=RECORDING_TIMEOUT)

    def get_recording_all_variants(
        self,
        guid: str,
        time_sec: int,
        channel_id: int = 0,
        pre_period: int = 10000,
        post_period: int = 5000,
    ) -> list[tuple[str, dict, Result]]:
        """
        Try all recording URI × param combinations. Returns list of (variant_name, params, Result).
        First successful Result may contain resourceUris or bytes.
        """
        self._discover_qvr_path()
        time_ms = time_sec * 1000
        duration = (pre_period + post_period) // 1000
        end_sec = time_sec + duration
        results: list[tuple[str, dict, Result]] = []
        uri_variants = [
            ("recordingfile/0", f"{self._qvr_path}/camera/recordingfile/{guid}/0"),
            ("recordingfile/1", f"{self._qvr_path}/camera/recordingfile/{guid}/1"),
            (f"recordingfile/{channel_id}", f"{self._qvr_path}/camera/recordingfile/{guid}/{channel_id}"),
            ("recording/", f"{self._qvr_path}/camera/recording/{guid}"),
        ]
        param_sets = [
            ("time_sec", {"time": time_sec, "pre_period": pre_period, "post_period": post_period}),
            ("time_ms", {"time": time_ms, "pre_period": pre_period, "post_period": post_period}),
            ("start_end", {"start_time": time_sec, "end_time": end_sec}),
            ("start_end_alt", {"start": time_sec, "end": end_sec}),
        ]
        for uri_name, path in uri_variants:
            for param_name, params in param_sets:
                name = f"{uri_name}:{param_name}"
                res = self._get(path, params, timeout=RECORDING_TIMEOUT)
                results.append((name, params, res))
        return results

    # --- Camera list ---

    def get_camera_list(self, guid: str | None = None) -> Result:
        """Get camera list. guid=None for all, guid=X for one camera."""
        self._discover_qvr_path()
        params = {"guid": guid} if guid else None
        return self._get(f"{self._qvr_path}/camera/list", params)

    # --- Camera capability ---

    def get_camera_capability(
        self,
        guid: str | None = None,
        ptz: int = 0,
    ) -> Result:
        """Get camera capabilities. ptz=0 default, ptz=1 for PTZ presets. guid optional."""
        self._discover_qvr_path()
        params: dict = {"ptz": ptz}
        if guid:
            params["guid"] = guid
        return self._get(f"{self._qvr_path}/camera/capability", params)

    def get_event_capability(self, guid: str | None = None) -> Result:
        """Get IVA/alarm event types per camera (act=get_event_capability). guid optional for per-camera."""
        self._discover_qvr_path()
        params: dict = {"act": "get_event_capability"}
        if guid:
            params["guid"] = guid
        return self._get(f"{self._qvr_path}/camera/capability", params)

    def get_capability_act(self, act: str, guid: str | None = None) -> Result:
        """
        Get capability by explicit act (QVR API). act: 'get_camera_capability' | 'get_event_capability'.
        pyqvrpro uses act=get_camera_capability for basic capability; act=get_event_capability for IVA types.
        """
        self._discover_qvr_path()
        params: dict = {"act": act}
        if guid:
            params["guid"] = guid
        return self._get(f"{self._qvr_path}/camera/capability", params)

    def get_capability_raw(self, guid: str | None = None, **params: Any) -> Result:
        """Low-level: any params for /camera/capability. For probing unknown variants."""
        self._discover_qvr_path()
        p: dict = dict(params)
        if guid:
            p["guid"] = guid
        return self._get(f"{self._qvr_path}/camera/capability", p)

    def get_capability_all_variants(
        self, guid: str | None = None
    ) -> list[tuple[str, dict[str, Any], Result]]:
        """
        Try all known capability variants. Returns (variant_name, params_used, Result).
        Some may 404 on certain QVR products – expected.
        """
        self._discover_qvr_path()
        results: list[tuple[str, dict[str, Any], Result]] = []
        variants: list[tuple[str, dict[str, Any]]] = [
            ("default", {}),
            ("ptz_0", {"ptz": 0}),
            ("ptz_1", {"ptz": 1}),
            ("act_get_camera_capability", {"act": "get_camera_capability"}),
            ("act_get_event_capability", {"act": "get_event_capability"}),
            # Candidate acts (may 404)
            ("act_list", {"act": "list"}),
            ("act_get_features", {"act": "get_features"}),
            ("act_get_ptz", {"act": "get_ptz"}),
        ]
        for name, p in variants:
            full_params = dict(p)
            if guid:
                full_params["guid"] = guid
            res = self._get(f"{self._qvr_path}/camera/capability", full_params)
            results.append((name, full_params, res))
        return results

    # --- Logs ---

    def get_logs(
        self,
        log_type: int,
        *,
        max_results: int = 20,
        start: int = 0,
        sort_field: str = "time",
        dir: str = "DESC",
        global_channel_id: str | None = None,
        channel_id: str | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        level: str | None = None,
    ) -> Result:
        """
        Get QVR logs. log_type: 1=System, 2=Connections, 3=Surveillance, 4=?, 5=?.
        Use global_channel_id for channel-scoped logs (e.g. log_type=3).
        """
        self._discover_qvr_path()
        params: dict = {
            "log_type": log_type,
            "max_results": max_results,
            "start": start,
            "sort_field": sort_field,
            "dir": dir,
        }
        if global_channel_id:
            params["global_channel_id"] = global_channel_id
        if channel_id:
            params["channel_id"] = channel_id
        if start_time is not None:
            params["start_time"] = start_time
        if end_time is not None:
            params["end_time"] = end_time
        if level:
            params["level"] = level
        return self._get(f"{self._qvr_path}/logs/logs", params)

    # --- PTZ ---

    def ptz_control(
        self,
        guid: str,
        action_id: str,
        direction: str | None = None,
    ) -> Result:
        """Invoke PTZ action. direction required for start_move/stop_move."""
        self._discover_qvr_path()
        path = f"{self._qvr_path}/ptz/v1/channel_list/{guid}/ptz/action_list/{action_id}/invoke"
        params = {"direction": direction} if direction else None
        return self._put(path, params)

    # --- Recording control ---

    def start_recording(self, guid: str) -> Result:
        """Start channel recording."""
        self._discover_qvr_path()
        return self._put(f"{self._qvr_path}/camera/mrec/{guid}/start")

    def stop_recording(self, guid: str) -> Result:
        """Stop channel recording."""
        self._discover_qvr_path()
        return self._put(f"{self._qvr_path}/camera/mrec/{guid}/stop")

    # --- Camera search ---

    def get_camera_search(self) -> Result:
        """Search for cameras on LAN (UPnP/UDP)."""
        self._discover_qvr_path()
        return self._get(f"{self._qvr_path}/camera/search")

    # --- Candidate endpoints (may 404) ---

    def get_recordingfile_noch(self, guid: str) -> Result:
        """Candidate: recordingfile without channel suffix. May 404."""
        self._discover_qvr_path()
        return self._get(f"{self._qvr_path}/camera/recordingfile/{guid}")

    def get_recording_list(
        self,
        guid: str,
        *,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> Result:
        """Candidate: list recordings by guid. May 404. Optional start_time/end_time."""
        self._discover_qvr_path()
        params: dict = {}
        if start_time is not None:
            params["start_time"] = start_time
        if end_time is not None:
            params["end_time"] = end_time
        return self._get(f"{self._qvr_path}/camera/recording/{guid}", params or None)

    def get_events(self) -> Result:
        """Candidate: camera events. May 404."""
        self._discover_qvr_path()
        return self._get(f"{self._qvr_path}/camera/events")

    def get_recordings(self) -> Result:
        """Candidate: camera/recordings. May 404."""
        self._discover_qvr_path()
        return self._get(f"{self._qvr_path}/camera/recordings")

    # --- Generic / candidate paths (probe all possibilities) ---

    def get_path(self, path: str, params: dict | None = None, timeout: int = 30) -> Result:
        """Low-level: arbitrary GET under base URL. For probing unknown paths."""
        self._discover_qvr_path()
        url_path = path if path.startswith("/") else f"{self._qvr_path}/{path}"
        return self._get(url_path, params, timeout=timeout)

    def get_camera_search_params(
        self,
        *,
        start_time: int | None = None,
        end_time: int | None = None,
        guid: str | None = None,
        **kwargs: Any,
    ) -> Result:
        """Camera search with optional params (may extend to recording search). Probe."""
        self._discover_qvr_path()
        params: dict = dict(kwargs)
        if start_time is not None:
            params["start_time"] = start_time
        if end_time is not None:
            params["end_time"] = end_time
        if guid:
            params["guid"] = guid
        return self._get(f"{self._qvr_path}/camera/search", params)

    def get_event_path(self, subpath: str = "", params: dict | None = None) -> Result:
        """Candidate: /event/ (QVR Open Event Platform). May 404."""
        self._discover_qvr_path()
        path = f"{self._qvr_path}/event/{subpath}".rstrip("/") if subpath else f"{self._qvr_path}/event"
        return self._get(path, params)

    def get_metadata_path(self, subpath: str = "", params: dict | None = None) -> Result:
        """
        Candidate: /metadata/ (QVR Metadata Platform). May 404.
        subpath: "" (root), "search", "list". params: guid, start_time, end_time, keyword (probe).
        """
        self._discover_qvr_path()
        path = f"{self._qvr_path}/metadata/{subpath}".rstrip("/") if subpath else f"{self._qvr_path}/metadata"
        return self._get(path, params)

    def get_metadata_search(self, guid: str, start_time: int | None = None, end_time: int | None = None, **kwargs: Any) -> Result:
        """Convenience: metadata/search with guid and optional time range. May 404."""
        params: dict = {"guid": guid}
        if start_time is not None:
            params["start_time"] = start_time
        if end_time is not None:
            params["end_time"] = end_time
        params.update(kwargs)
        return self.get_metadata_path("search", params)

    def get_metadata_list(self, guid: str | None = None, **kwargs: Any) -> Result:
        """Convenience: metadata/list. guid optional. May 404."""
        params: dict = dict(kwargs)
        if guid:
            params["guid"] = guid
        return self.get_metadata_path("list", params if params else None)

    def get_qshare_path(self, subpath: str, params: dict | None = None) -> Result:
        """Generic qshare path. subpath e.g. 'RecordingOutput' or 'RecordingOutput/channels'. May 404."""
        self._discover_qvr_path()
        return self._get(f"{self._qvr_path}/qshare/{subpath}", params)

    def get_live_stream_protocol(
        self, guid: str, protocol: str, stream: int = 0
    ) -> Result:
        """Get live stream URL for protocol (rtsp, rtmp, onvif, hls, etc.). Try all."""
        return self.get_live_stream(guid, stream=stream, protocol=protocol)
