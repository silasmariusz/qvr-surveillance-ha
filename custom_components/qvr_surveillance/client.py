"""
QVR Surveillance API client - standalone implementation.
No external dependencies. Uses requests (built into HA).
"""

from __future__ import annotations

import base64
import inspect
import logging
import time
from typing import Any, Callable, TypeVar

import requests
import xml.etree.ElementTree as ET

from .errors import (
    QVRAuthError,
    QVRAPIError,
    QVRConnectionError,
    QVRResponseError,
    _log_api_error,
)

API_VERSION = "1.1.0"
DEF_CONN_TIMEOUT = 10
RECONNECT_INTERVAL = 180
REAUTH_INTERVAL = 120  # Re-auth every 2 min (QVR session can expire)
DEFAULT_PORT_HTTP = 8080
DEFAULT_PORT_HTTPS = 443
QVR_SURVEILLANCE_PORT = 38080  # QVR Surveillance default (standalone NVR)

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


class QVRPermissionError(QVRAuthError):
    """Insufficient permissions."""


def _caller_info() -> tuple[int, str]:
    """Get line and cmd from caller frame."""
    frame = inspect.currentframe()
    if frame and frame.f_back:
        return (frame.f_back.f_lineno, frame.f_back.f_code.co_name or "")
    return (0, "")


def _api_caller_cmd() -> str:
    """Get API method name (e.g. get_snapshot) from call stack."""
    frame = inspect.currentframe()
    skip = {"_check_api_response", "_get", "_post", "_put"}
    while frame:
        name = frame.f_code.co_name or ""
        if name not in skip:
            return name
        frame = frame.f_back
    return "unknown"


def _throw_error(
    message: str,
    *,
    level: str = "error",
    service: str = "api",
    response: requests.Response | None = None,
    uri: str = "",
    code: int = 0,
) -> None:
    """Universal error handler. Logs and raises."""
    line, cmd = _caller_info()
    hint = ""
    if response:
        ct = response.headers.get("content-type", "")
        status = response.status_code
        if "text/html" in ct and status in (403, 404):
            hint = " API path may not exist. Check port and ensure QVR Surveillance is running."
        msg = f"{uri} -> {status}. {message}{hint}" if uri else f"{message}{hint}"
    else:
        msg = message

    error_type = "auth" if service.lower() == "auth" else "network" if service.lower() in ("network", "socket") else "api"
    _log_api_error(line, cmd, error_type, code, msg, _LOGGER)

    if service.lower() in ("auth",):
        raise QVRAuthError(msg, line=line, cmd=cmd, code=code, error_type="auth")
    if service.lower() in ("network", "socket"):
        raise QVRConnectionError(msg, line=line, cmd=cmd, code=code, error_type="network")
    if "permission" in msg.lower():
        raise QVRPermissionError(msg, line=line, cmd=cmd, code=code, error_type="auth")
    raise QVRResponseError(msg, line=line, cmd=cmd, code=code, error_type="api")


def _try_establish_conn(
    base_url_fn: Callable[[], str],
    timeout: int = DEF_CONN_TIMEOUT,
) -> bool:
    """Probe connection via /qvrentry. Returns True if reachable."""
    try:
        r = requests.get(
            f"{base_url_fn()}/qvrentry",
            timeout=timeout,
            verify=False,
        )
        return r.ok and "application/json" in r.headers.get("content-type", "")
    except Exception:
        return False


class QVRClient:
    """QVR Pro / QVR Elite / QVR Surveillance API client."""

    def __init__(
        self,
        user: str,
        password: str,
        host: str,
        protocol: str = "http",
        port: int = DEFAULT_PORT_HTTP,
        verify_ssl: bool = False,
    ) -> None:
        self._user = user
        self._password = password
        self._host = host
        self._protocol = protocol
        self._port = port
        self._configured_port = port
        self._verify_ssl = verify_ssl
        self._session_id: str | None = None
        self._qvr_uri = "/qvrpro"
        self._authenticated = False
        self._last_connect_fail: float = 0
        self._last_auth_time: float = 0
        self._effective_port = port
        self._ensure_and_auth()

    def _base_url(self) -> str:
        return f"{self._protocol}://{self._host}:{self._effective_port}"

    def _do_auth(self) -> bool:
        """Single auth procedure. Returns True on success, False on failure."""
        auth_url = f"{self._base_url()}/cgi-bin/authLogin.cgi"
        pwd_b64 = base64.b64encode(self._password.encode("ascii")).decode("ascii")
        params = {
            "user": self._user,
            "pwd": pwd_b64,
            "serviceKey": 1,
            "verify": 1 if self._verify_ssl else 0,
        }
        try:
            r = requests.get(
                auth_url,
                params=params,
                timeout=DEF_CONN_TIMEOUT,
                verify=self._verify_ssl,
            )
            r.raise_for_status()
        except requests.RequestException:
            return False

        try:
            root = ET.fromstring(r.content)
        except ET.ParseError:
            _throw_error("Invalid auth response (not XML)", service="auth")
            return False

        auth_passed = root.find(".//authPassed")
        auth_sid = root.find(".//authSid")

        if auth_passed is None or auth_sid is None:
            _throw_error("Invalid login response structure", service="auth")
            return False

        if int(auth_passed.text or 0) != 1:
            _throw_error("Authentication failed - check credentials", service="auth")
            return False

        self._session_id = auth_sid.text or ""
        self._authenticated = True
        self._last_auth_time = time.time()
        return True

    def _discover_qvr_path(self) -> bool:
        """Fetch /qvrentry to get API path (qvrpro, qvrelite, qvrsurveillance)."""
        try:
            r = requests.get(
                f"{self._base_url()}/qvrentry",
                timeout=DEF_CONN_TIMEOUT,
                verify=self._verify_ssl,
            )
            if not r.ok:
                return False
            data = r.json()
            if data.get("is_qvp") == "yes":
                self._qvr_uri = "/qvrpro"
            elif data.get("fw_web_ui_prefix"):
                prefix = data["fw_web_ui_prefix"].strip("/")
                self._qvr_uri = f"/{prefix}" if prefix else "/qvrelite"
            else:
                self._qvr_uri = "/qvrelite"
            return True
        except Exception:
            self._qvr_uri = "/qvrpro"
            return False

    def _try_connect_on_port(self, port: int) -> bool:
        """Try to establish connection and auth on given port."""
        self._effective_port = port
        if not _try_establish_conn(self._base_url, DEF_CONN_TIMEOUT):
            return False
        if not self._discover_qvr_path():
            return False
        return self._do_auth()

    def _ensure_and_auth(self) -> None:
        """Establish connection. Try configured port, then fallback to 8080/443."""
        if self._try_connect_on_port(self._configured_port):
            return

        now = time.time()
        if now - self._last_connect_fail < RECONNECT_INTERVAL:
            self._last_connect_fail = now
            raise QVRConnectionError(
                f"Cannot connect to {self._host}:{self._configured_port}. "
                f"Will retry after {RECONNECT_INTERVAL}s."
            )

        default_port = DEFAULT_PORT_HTTPS if self._protocol == "https" else DEFAULT_PORT_HTTP
        if self._configured_port != default_port:
            _LOGGER.info(
                "[NETWORK] Custom port %s failed, trying default %s",
                self._configured_port,
                default_port,
            )
            if self._try_connect_on_port(default_port):
                return

        if self._configured_port != QVR_SURVEILLANCE_PORT and default_port != QVR_SURVEILLANCE_PORT:
            _LOGGER.info("[NETWORK] Trying QVR Surveillance port %s", QVR_SURVEILLANCE_PORT)
            if self._try_connect_on_port(QVR_SURVEILLANCE_PORT):
                return

        self._last_connect_fail = now
        raise QVRConnectionError(
            f"Cannot connect to {self._host}. Tried ports {self._configured_port} and "
            f"{DEFAULT_PORT_HTTP if self._protocol == 'http' else DEFAULT_PORT_HTTPS}."
        )

    def _ensure_connection(self) -> None:
        """Ensure session is valid. Re-auth if needed or every REAUTH_INTERVAL."""
        now = time.time()
        must_auth = (
            not self._authenticated
            or not self._session_id
            or (now - self._last_auth_time) >= REAUTH_INTERVAL
        )
        if must_auth:
            self._ensure_and_auth()

    def _is_auth_error(self, response: requests.Response | dict) -> bool:
        """Check if response indicates session expiry / authorization failed."""
        if isinstance(response, dict):
            msg = str(response.get("error_message", "")).lower()
            code = response.get("error_code", 0)
            return (
                response.get("success") is False
                and ("authorization failed" in msg or "auth" in msg or code == -1325400063)
            )
        if response.status_code in (401, 403):
            return True
        try:
            data = response.json()
            return self._is_auth_error(data)
        except Exception:
            return False

    def _handle_request_error(
        self,
        response: requests.Response,
        uri: str,
    ) -> None:
        """Handle non-ok response with debug info."""
        self._authenticated = False
        line, cmd = _caller_info()
        code = 0
        msg = response.text[:300] if response.text else str(response.status_code)
        try:
            data = response.json()
            if isinstance(data, dict):
                code = data.get("error_code", response.status_code)
                msg = data.get("error_message", msg)
                if self._is_auth_error(data):
                    _log_api_error(line, cmd, "auth", code, msg, _LOGGER)
                    raise QVRAuthError(msg, line=line, cmd=cmd, code=code, error_type="auth")
        except QVRAuthError:
            raise
        except Exception:
            pass
        ct = response.headers.get("content-type", "")
        if "text/html" in ct and response.status_code in (403, 404):
            msg += " API path may not exist. Check port and ensure QVR Surveillance is running."
        full_msg = f"{uri} -> {response.status_code}. {msg}" if uri else msg
        _log_api_error(line, cmd, "api", code or response.status_code, full_msg, _LOGGER)
        raise QVRResponseError(full_msg, line=line, cmd=cmd, code=code, error_type="api")

    def _request_with_retry(
        self,
        method: str,
        uri: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
        timeout: int = 30,
    ) -> requests.Response:
        """Execute request with connection check and single retry on failure."""
        self._ensure_connection()

        url = f"{self._base_url()}{uri}"
        req_params = params or {}
        req_params["sid"] = self._session_id
        req_params["ver"] = API_VERSION

        def _do_req() -> requests.Response:
            if method == "GET":
                return requests.get(
                    url, params=req_params, timeout=timeout, verify=self._verify_ssl
                )
            if method == "POST":
                return requests.post(
                    url, params={"sid": self._session_id}, json=json_body or {},
                    timeout=timeout, verify=self._verify_ssl
                )
            if method == "PUT":
                return requests.put(
                    url, params=req_params, timeout=timeout, verify=self._verify_ssl
                )
            raise ValueError(f"Unknown method: {method}")

        try:
            r = _do_req()
        except requests.RequestException:
            self._authenticated = False
            self._ensure_connection()
            try:
                r = _do_req()
            except requests.RequestException as e:
                _throw_error(
                    f"Request failed after retry: {e}",
                    level="warning",
                    service="network",
                )
            if r.ok:
                return r
            if self._is_auth_error(r):
                self._authenticated = False
                self._ensure_connection()
                r = _do_req()
            if r.ok:
                return r
            self._handle_request_error(r, uri)

        if r.ok:
            return r

        if self._is_auth_error(r):
            self._authenticated = False
            self._ensure_connection()
            try:
                r2 = _do_req()
                if r2.ok:
                    return r2
            except requests.RequestException:
                pass
        self._handle_request_error(r, uri)

    def get_auth_string(self) -> str:
        """User:password for URL auth."""
        return f"{self._user}:{self._password}"

    def _check_api_response(self, data: dict) -> None:
        """Raise QVRAPIError if API returned success=False."""
        if data.get("success") is False:
            line, _ = _caller_info()
            cmd = _api_caller_cmd()
            code = data.get("error_code", 0)
            msg = data.get("error_message", "Unknown API error")
            _log_api_error(line, cmd, "api", code, msg, _LOGGER)
            if self._is_auth_error(data):
                raise QVRAuthError(msg, line=line, cmd=cmd, code=code, error_type="auth")
            raise QVRAPIError(msg, line=line, cmd=cmd, code=code, error_type="api")

    def _get(self, uri: str, params: dict | None = None) -> dict | bytes:
        req_params = params or {}
        r = self._request_with_retry("GET", uri, params=req_params)
        ct = r.headers.get("content-type", "")
        if "application/json" in ct:
            data = r.json()
            if isinstance(data, dict) and self._is_auth_error(data):
                self._authenticated = False
                self._ensure_connection()
                r2 = self._request_with_retry("GET", uri, params=req_params)
                if "application/json" in r2.headers.get("content-type", ""):
                    data2 = r2.json()
                    if isinstance(data2, dict) and self._is_auth_error(data2):
                        _throw_error(
                            data2.get("error_message", "Authorization failed"),
                            service="auth",
                            code=data2.get("error_code", 0),
                        )
                    if isinstance(data2, dict):
                        self._check_api_response(data2)
                    return data2
            if isinstance(data, dict):
                self._check_api_response(data)
            return data
        if "image/" in ct or "video/" in ct:
            return r.content
        return r.content

    def _post(self, uri: str, json_body: dict) -> dict:
        r = self._request_with_retry("POST", uri, json_body=json_body)
        data = r.json()
        if isinstance(data, dict):
            self._check_api_response(data)
        return data

    def _put(self, uri: str) -> dict:
        r = self._request_with_retry("PUT", uri)
        data = r.json() if r.text else {}
        if isinstance(data, dict):
            self._check_api_response(data)
        return data if isinstance(data, dict) else {}

    def get_channel_list(self) -> dict:
        """List channels."""
        resp = self._get(f"{self._qvr_uri}/qshare/StreamingOutput/channels")
        if isinstance(resp, dict) and resp.get("message") == "Insufficient permission.":
            raise QVRPermissionError("User must have Surveillance Management permission")
        return resp if isinstance(resp, dict) else {}

    def get_snapshot(self, camera_guid: str) -> bytes:
        """Get camera snapshot."""
        resp = self._get(f"{self._qvr_uri}/camera/snapshot/{camera_guid}")
        return resp if isinstance(resp, bytes) else b""

    def get_channel_streams(self, guid: str) -> dict:
        """Get available streams for a channel (Main=0, Sub=1, Mobile=2)."""
        resp = self._get(f"{self._qvr_uri}/qshare/StreamingOutput/channel/{guid}/streams")
        return resp if isinstance(resp, dict) else {}

    def get_channel_live_stream(
        self, guid: str, stream: int = 0, protocol: str = "rtsp"
    ) -> dict:
        """Get live stream URL. stream: 0=Main, 1=Substream, 2=Mobile."""
        uri = f"{self._qvr_uri}/qshare/StreamingOutput/channel/{guid}/stream/{stream}/liveStream"
        return self._post(uri, {"protocol": protocol})

    def get_recording(
        self,
        timestamp: int,
        camera_guid: str,
        channel_id: int = 0,
        pre_period: int = 10000,
        post_period: int = 0,
    ) -> dict | bytes | None:
        """Fetch recording. Tries multiple param formats for QVR Pro vs Surveillance."""
        uri = f"{self._qvr_uri}/camera/recordingfile/{camera_guid}/{channel_id}"
        duration_sec = (pre_period + post_period) // 1000

        params_sets = [
            {"time": timestamp, "pre_period": pre_period, "post_period": post_period},
            {"time": timestamp * 1000, "pre_period": pre_period, "post_period": post_period},
            {"start": timestamp, "end": timestamp + duration_sec},
            {"start_time": timestamp, "end_time": timestamp + duration_sec},
        ]
        for params in params_sets:
            try:
                resp = self._get(uri, params)
                if resp is not None and (
                    isinstance(resp, bytes)
                    or (isinstance(resp, dict) and (resp.get("resourceUris") or resp.get("url")))
                ):
                    return resp
            except (QVRResponseError, QVRAPIError, QVRConnectionError, QVRAuthError):
                continue
        return None

    def start_recording(self, guid: str) -> dict:
        """Start channel recording."""
        return self._put(f"{self._qvr_uri}/camera/mrec/{guid}/start")

    def stop_recording(self, guid: str) -> dict:
        """Stop channel recording."""
        return self._put(f"{self._qvr_uri}/camera/mrec/{guid}/stop")

    def get_camera_list(self, guid: str | None = None) -> dict:
        """Get connection and recording status of one or all cameras."""
        params: dict = {}
        if guid:
            params["guid"] = guid
        resp = self._get(f"{self._qvr_uri}/camera/list", params or None)
        return resp if isinstance(resp, dict) else {}

    def get_camera_capability(
        self, guid: str | None = None, ptz: bool = False
    ) -> dict:
        """Get camera capabilities (PTZ, etc.)."""
        params: dict = {"ptz": 1 if ptz else 0}
        if guid:
            params["guid"] = guid
        resp = self._get(f"{self._qvr_uri}/camera/capability", params)
        return resp if isinstance(resp, dict) else {}

    def ptz_control(
        self,
        guid: str,
        action_id: str,
        direction: str | None = None,
    ) -> dict:
        """Invoke PTZ action. For start_move/stop_move, direction is required."""
        uri = f"{self._qvr_uri}/ptz/v1/channel_list/{guid}/ptz/action_list/{action_id}/invoke"
        params: dict = {}
        if direction:
            params["direction"] = direction
        r = self._request_with_retry("PUT", uri, params=params or None)
        return r.json() if r.text else {}

    def get_logs(
        self,
        *,
        log_type: int | None = None,
        level: str | None = None,
        start: int = 0,
        max_results: int = 20,
        sort_field: str = "time",
        dir: str = "DESC",
        start_time: int | None = None,
        end_time: int | None = None,
        channel_id: str | None = None,
        global_channel_id: str | None = None,
    ) -> dict:
        """Get QVR Pro logs. log_type: 1=System Events, 2=Connections, 3=Surveillance Events, etc."""
        params: dict = {"start": start, "max_results": max_results, "sort_field": sort_field, "dir": dir}
        if log_type is not None:
            params["log_type"] = log_type
        if level is not None:
            params["level"] = level
        if start_time is not None:
            params["start_time"] = start_time
        if end_time is not None:
            params["end_time"] = end_time
        if channel_id:
            params["channel_id"] = channel_id
        if global_channel_id:
            params["global_channel_id"] = global_channel_id
        resp = self._get(f"{self._qvr_uri}/logs/logs", params)
        return resp if isinstance(resp, dict) else {}

    def get_camera_search(self) -> dict:
        """Search for cameras on LAN via UPnP/UDP."""
        resp = self._get(f"{self._qvr_uri}/camera/search")
        return resp if isinstance(resp, dict) else {}

    def force_reconnect(self) -> None:
        """Force re-authentication on next request."""
        self._authenticated = False
        self._session_id = None
        self._last_auth_time = 0

    @property
    def authenticated(self) -> bool:
        return self._authenticated
