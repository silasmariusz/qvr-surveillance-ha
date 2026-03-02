# QVR API Wrapper

Standalone Python wrapper for QVR Pro / QVR Elite / QVR Surveillance API. All methods return `Result(ok, data, error)` and **never raise**. Follows the official QVR API (we adhere to QVR, not reverse engineering).

**Requires:** `pip install requests`

## Quick Start

```python
from qvr_api import QVRApi, Result

api = QVRApi(host="10.0.0.1", user="admin", password="secret")
res = api.get_channels()
if res.ok:
    for ch in res.data.get("channelList", []):
        print(ch.get("guid"))
else:
    print(res.error)
```

## Result Type

```python
@dataclass
class Result:
    ok: bool       # True if request succeeded
    data: ...      # dict | list | bytes | str | None
    error: str     # Error message when ok=False
```

## API Reference

### Discovery

#### `get_qvrentry() -> Result`

Discover QVR API path. Call first to determine whether the NVR uses `/qvrpro`, `/qvrelite`, or another prefix.

| Params | - |
| Returns | `dict` with `fw_web_ui_prefix`, `is_qvp`, etc. |
| QVR API | `GET /qvrentry` |

#### `ensure_qvr_path() -> Result`

Fetch `/qvrentry` and set internal `qvr_path`. Other methods call `_discover_qvr_path()` automatically; this is optional for pre-warming.

| Returns | `{"qvr_path": "/qvrpro"}` or similar |
| QVR API | `GET /qvrentry` |

---

### Channels & Streams

#### `get_channels() -> Result`

List all channels.

| Returns | `channelList` or `channels` with `guid` per channel |
| QVR API | `GET {qvr_path}/qshare/StreamingOutput/channels` |

#### `get_channel_streams(guid: str) -> Result`

Get available stream profiles for a channel (Main, Sub, Mobile).

| Params | `guid` – channel GUID |
| Returns | `streams[]` or similar |
| QVR API | `GET .../channel/{guid}/streams` |

#### `get_live_stream(guid, stream=0, protocol="rtsp") -> Result`

Get live stream URL.

| Params | `guid` – channel GUID; `stream` – 0=Main, 1=Substream, 2=Mobile; `protocol` – e.g. `"rtsp"` |
| Returns | `resourceUris` or `resourceUri` or `url` (depending on QVR version) |
| QVR API | `POST .../channel/{guid}/stream/{stream}/liveStream` with body `{"protocol": "rtsp"}` |

---

### Snapshot

#### `get_snapshot(guid: str) -> Result`

Get camera snapshot (JPEG).

| Params | `guid` – channel GUID |
| Returns | `bytes` (JPEG image) on success |
| QVR API | `GET {qvr_path}/camera/snapshot/{guid}` |

---

### Recording

#### `get_recording(guid, *, channel_id=0, time_sec=None, time_ms=None, start_time=None, end_time=None, start=None, end=None, pre_period=10000, post_period=5000, uri_variant="recordingfile/0") -> Result`

Fetch recording for a time point or range. Specify one of: `(time_sec)`, `(time_ms)`, `(start_time, end_time)`, `(start, end)`.

| Params | `time_sec` / `time_ms` – center time (Unix sec or ms); `start_time`/`end_time` or `start`/`end` – range; `pre_period`/`post_period` – ms before/after center; `uri_variant` – `"recordingfile/0"`, `"recordingfile/1"`, `"recording/"` |
| Returns | `dict` with `resourceUris` / `url` or `bytes` (video) |
| QVR API | `GET .../camera/recordingfile/{guid}/{ch}` or `.../camera/recording/{guid}` (params vary by QVR product) |

**Param variants (QVR API adherence):**

- Time: `time` (sec), `time` (ms)
- Range: `start_time`/`end_time`, `start`/`end`

**URI variants:**

- `recordingfile/0` – channel 0
- `recordingfile/1` – channel 1
- `recording/` – candidate, may 404 on some products

#### `get_recording_all_variants(guid, time_sec, channel_id=0, pre_period=10000, post_period=5000) -> list[tuple[str, dict, Result]]`

Try all URI × param combinations. Returns `(variant_name, params, Result)` for each attempt. Useful for probing which variant a given NVR accepts.

---

### Camera List

#### `get_camera_list(guid: str | None = None) -> Result`

Get camera connection and recording status.

| Params | `guid=None` – all cameras; `guid="..."` – single camera |
| Returns | `cameraList` or `cameras` with `channel_id`, `rec_state`, etc. |
| QVR API | `GET {qvr_path}/camera/list` (optional `?guid=X`) |

---

### Camera Capability

#### `get_camera_capability(guid=None, ptz=0) -> Result`

Get camera capabilities. May fail per-camera (e.g. offline); that is expected.

| Params | `guid` – optional; `ptz` – 0=basic, 1=PTZ presets/features |
| Returns | Capability dict (varies by camera) |
| QVR API | `GET .../camera/capability?ptz=0|1` (optional `&guid=X`) |

#### `get_event_capability() -> Result`

Get IVA/alarm event types per camera (motion, line crossing, etc.).

| Returns | Event capability dict |
| QVR API | `GET .../camera/capability?act=get_event_capability` |

---

### Logs

#### `get_logs(log_type, *, max_results=20, start=0, sort_field="time", dir="DESC", global_channel_id=None, channel_id=None, start_time=None, end_time=None, level=None) -> Result`

Get QVR application logs. **Note:** These are **audit/operational logs**, not timeline events. For timeline, use recordings.

| Params | `log_type` – 1=System Events, 2=Connections, 3=Surveillance Events, 4/5=other; `global_channel_id`/`channel_id` – filter by channel; `start_time`/`end_time` – Unix sec |
| Returns | Log entries (structure varies by log_type) |
| QVR API | `GET {qvr_path}/logs/logs` |

**Log types:** 1 (System), 2 (Connections), 3 (Surveillance – use `global_channel_id` for channel scope), 4, 5.

---

### PTZ

#### `ptz_control(guid, action_id, direction=None) -> Result`

Invoke PTZ action. `direction` required for `start_move` / `stop_move`.

| Params | `guid`, `action_id`, optional `direction` |
| Returns | API response (often empty) |
| QVR API | `PUT .../ptz/v1/channel_list/{guid}/ptz/action_list/{action_id}/invoke` |

---

### Recording Control

#### `start_recording(guid: str) -> Result`

Start manual recording for a channel.

| QVR API | `PUT .../camera/mrec/{guid}/start` |

#### `stop_recording(guid: str) -> Result`

Stop manual recording for a channel.

| QVR API | `PUT .../camera/mrec/{guid}/stop` |

---

### Camera Search

#### `get_camera_search() -> Result`

Search for cameras on LAN via UPnP/UDP.

| Returns | Discovered devices |
| QVR API | `GET {qvr_path}/camera/search` |

---

### Candidate Endpoints (May 404)

These paths may not exist on all QVR products.

#### `get_recordingfile_noch(guid: str) -> Result`

`GET .../camera/recordingfile/{guid}` (no channel suffix).

#### `get_recording_list(guid: str) -> Result`

`GET .../camera/recording/{guid}` – list recordings by guid.

#### `get_events() -> Result`

`GET .../camera/events` – events endpoint.

#### `get_recordings() -> Result`

`GET .../camera/recordings` – list recordings.

---

## Standalone Use (e.g. tools/qvr_api_probe.py)

The library has its own minimal HTTP layer (no dependency on `custom_components`). From the project root:

```bash
cd c:\cards_development\qvr_surveillance
QVR_PASS=xxx python tools/qvr_api_probe.py
```

Or in Python:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qvr_api import QVRApi

api = QVRApi(host="10.0.0.1", user="admin", password=os.environ["QVR_PASS"])
res = api.get_channels()
```

---

## QVR API Adherence

This wrapper follows the QVR Pro API (Swagger: `qvr_pro_api_1.1.0.yaml`), `API_REFERENCES.md`, and `client.py` patterns. Param and path variants reflect real QVR behavior observed in Pro vs Elite vs Surveillance; some endpoints (e.g. `recording/`, `camera/events`) may 404 on certain products.
