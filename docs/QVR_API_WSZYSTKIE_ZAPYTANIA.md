# QVR API – Wszystkie zapytania (pełna lista)

Kompletna lista wszystkich zapytań oferowanych przez QVR API. Probe (`tools/qvr_api_probe.py`) testuje każdy wariant. Część może zwrócić 404 – normalne.

---

## 1. Discovery

| Zapytanie | Path | Method | Params | Zwraca |
|-----------|------|--------|--------|--------|
| qvrentry | `/qvrentry` | GET | – | fw_web_ui_prefix, is_qvp |

---

## 2. Channels & Streams

| Zapytanie | Path | Method | Params | Zwraca |
|-----------|------|--------|--------|--------|
| channels | `{qvr}/qshare/StreamingOutput/channels` | GET | sid, ver | channelList[] |
| channel_streams | `{qvr}/qshare/StreamingOutput/channel/{guid}/streams` | GET | sid, ver | streams[] |
| livestream | `{qvr}/qshare/.../channel/{guid}/stream/{n}/liveStream` | POST | sid, ver, body: {protocol} | resourceUris |

**Warianty livestream:** stream n=0,1,2 × protocol=rtsp, rtmp, onvif, hls

---

## 3. Snapshot

| Zapytanie | Path | Method | Params | Zwraca |
|-----------|------|--------|--------|--------|
| snapshot | `{qvr}/camera/snapshot/{guid}` | GET | sid, ver | JPEG bytes |

---

## 4. Recording

| Zapytanie | Path | Method | Params | Zwraca |
|-----------|------|--------|--------|--------|
| recordingfile/0 time_sec | `{qvr}/camera/recordingfile/{guid}/0` | GET | time, pre_period, post_period | resourceUris / bytes |
| recordingfile/0 time_ms | j.w. | GET | time (ms), pre_period, post_period | j.w. |
| recordingfile/0 start_end | j.w. | GET | start_time, end_time | j.w. |
| recordingfile/0 start_end_alt | j.w. | GET | start, end | j.w. |
| recordingfile/1 | `{qvr}/camera/recordingfile/{guid}/1` | GET | time, pre_period, post_period | j.w. |
| recordingfile/2 | `{qvr}/camera/recordingfile/{guid}/2` | GET | j.w. | j.w. |
| recordingfile_noch | `{qvr}/camera/recordingfile/{guid}` | GET | sid | może 404 |
| recording_list | `{qvr}/camera/recording/{guid}` | GET | sid, start_time?, end_time? | może 404, lista segmentów |
| recordings | `{qvr}/camera/recordings` | GET | sid | może 404 |

---

## 5. Camera List

| Zapytanie | Path | Method | Params | Zwraca |
|-----------|------|--------|--------|--------|
| camera_list | `{qvr}/camera/list` | GET | sid | cameraList[] |
| camera_list_guid | j.w. | GET | sid, guid | jedna kamera |

---

## 6. Camera Capability (każdy wariant)

| Zapytanie | Path | Method | Params | Zwraca |
|-----------|------|--------|--------|--------|
| capability default | `{qvr}/camera/capability` | GET | sid | capability |
| capability ptz=0 | j.w. | GET | sid, ptz=0 | j.w. |
| capability ptz=1 | j.w. | GET | sid, ptz=1 | PTZ presety |
| capability act=get_camera_capability | j.w. | GET | sid, act=get_camera_capability | j.w. |
| capability act=get_event_capability | j.w. | GET | sid, act=get_event_capability | IVA types per kamera |
| capability act=list | j.w. | GET | sid, act=list | może 404 |
| capability act=get_features | j.w. | GET | sid, act=get_features | może 404 |
| capability act=get_ptz | j.w. | GET | sid, act=get_ptz | może 404 |
| capability per guid | j.w. | GET | sid, guid, (ptz|act) | per-kamera |

---

## 7. Logs

| Zapytanie | Path | Method | Params | Zwraca |
|-----------|------|--------|--------|--------|
| logs type=1 | `{qvr}/logs/logs` | GET | log_type=1, max_results | System |
| logs type=2 | j.w. | GET | log_type=2 | Connections |
| logs type=3 | j.w. | GET | log_type=3, global_channel_id? | Surveillance |
| logs type=4 | j.w. | GET | log_type=4 | – |
| logs type=5 | j.w. | GET | log_type=5 | – |
| logs type=3 time | j.w. | GET | log_type=3, start_time, end_time | z filtrem czasu |
| logs type=3 level | j.w. | GET | log_type=3, level=info | z poziomem |

---

## 8. PTZ

| Zapytanie | Path | Method | Params | Zwraca |
|-----------|------|--------|--------|--------|
| ptz invoke | `{qvr}/ptz/v1/channel_list/{guid}/ptz/action_list/{id}/invoke` | PUT | sid, direction? | – |

---

## 9. Recording Control (PUT)

| Zapytanie | Path | Method | Params | Zwraca |
|-----------|------|--------|--------|--------|
| mrec start | `{qvr}/camera/mrec/{guid}/start` | PUT | sid | – |
| mrec stop | `{qvr}/camera/mrec/{guid}/stop` | PUT | sid | – |

---

## 10. Camera Search

| Zapytanie | Path | Method | Params | Zwraca |
|-----------|------|--------|--------|--------|
| camera_search | `{qvr}/camera/search` | GET | sid | Discovered devices |
| camera_search_time | j.w. | GET | sid, start_time, end_time | probe – może rozszerzyć |

---

## 11. Candidate (często 404)

| Zapytanie | Path | Method | Zwraca |
|-----------|------|--------|--------|
| event | `{qvr}/event` | GET | może 404 |
| metadata | `{qvr}/metadata` | GET | może 404 |
| qshare RecordingOutput | `{qvr}/qshare/RecordingOutput` | GET | może 404 |
| qshare RecordingOutput/channels | `{qvr}/qshare/RecordingOutput/channels` | GET | może 404 |
| camera_events | `{qvr}/camera/events` | GET | może 404 |

---

## Legenda

- `{qvr}` = qvr_path z qvrentry (/qvrpro, /qvrelite, …)
- sid, ver – wymagane przy każdym zapytaniu
- Zwraca 404 – endpoint nie istnieje na danym produkcie QVR
