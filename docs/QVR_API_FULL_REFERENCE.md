# QVR API – Pełna Referencja Funkcji (qvr_api)

Każda funkcja biblioteki `qvr_api` – krótki opis. QVR API to my się do niego stosujemy, nie on do nas.

---

## Result

Wszystkie metody zwracają `Result(ok, data, error)`. Nie rzucają wyjątków.

---

## Discovery / Entry

| Funkcja | Opis | QVR |
|---------|------|-----|
| `get_qvrentry()` | Odkrywa ścieżkę API (qvrpro/qvrelite). Zwraca fw_web_ui_prefix, is_qvp. | GET /qvrentry |
| `ensure_qvr_path()` | Pobiera qvrentry i ustawia wewnętrzny qvr_path. Opcjonalne przed innymi wywołaniami. | GET /qvrentry |

---

## Channels & Streams

| Funkcja | Opis | QVR |
|---------|------|-----|
| `get_channels()` | Lista kanałów. Zwraca channelList/channels z guid. | GET .../qshare/StreamingOutput/channels |
| `get_channel_streams(guid)` | Profile streamów kanału (Main=0, Sub=1, Mobile=2). | GET .../channel/{guid}/streams |
| `get_live_stream(guid, stream=0, protocol="rtsp")` | URL streamu na żywo. stream: 0/1/2, protocol: rtsp, rtmp, onvif, hls. | POST .../stream/{n}/liveStream |
| `get_live_stream_protocol(guid, protocol, stream=0)` | Alias dla get_live_stream z danym protokołem. | j.w. |

---

## Snapshot

| Funkcja | Opis | QVR |
|---------|------|-----|
| `get_snapshot(guid)` | Migawka kamery (JPEG bytes). | GET .../camera/snapshot/{guid} |

---

## Recording

| Funkcja | Opis | QVR |
|---------|------|-----|
| `get_recording(guid, ...)` | Nagranie: time_sec, time_ms, start_time/end_time, start/end. uri_variant: recordingfile/0, 1, recording/. | GET .../camera/recordingfile/{guid}/{ch} |
| `get_recording_all_variants(guid, time_sec, ...)` | Próbuje wszystkie kombinacje URI × param. Zwraca listę (nazwa, params, Result). | wiele GET |

---

## Camera List

| Funkcja | Opis | QVR |
|---------|------|-----|
| `get_camera_list(guid=None)` | Lista kamer, rec_state, channel_id. guid=None: wszystkie, guid=X: jedna. | GET .../camera/list |

---

## Camera Capability

| Funkcja | Opis | QVR |
|---------|------|-----|
| `get_camera_capability(guid=None, ptz=0)` | Capability podstawowe (ptz=0) lub PTZ presety (ptz=1). | GET .../camera/capability?ptz= |
| `get_event_capability(guid=None)` | Typy IVA/Alarm per kamera (act=get_event_capability). | GET .../camera/capability?act=get_event_capability |
| `get_capability_act(act, guid=None)` | Explicite act: get_camera_capability, get_event_capability, list, get_features, get_ptz. | GET .../camera/capability?act= |
| `get_capability_raw(guid=None, **params)` | Dowolne parametry capability. Do probowania. | GET .../camera/capability |
| `get_capability_all_variants(guid=None)` | Próbuje wszystkie znane warianty (default, ptz_0, ptz_1, act=...). | wiele GET |

---

## Logs

| Funkcja | Opis | QVR |
|---------|------|-----|
| `get_logs(log_type, ...)` | Logi aplikacyjne (audit). log_type: 1–5. global_channel_id, start_time, end_time, level. **Nie** timeline events. | GET .../logs/logs |

---

## PTZ

| Funkcja | Opis | QVR |
|---------|------|-----|
| `ptz_control(guid, action_id, direction=None)` | Wywołanie akcji PTZ. direction dla start_move/stop_move. | PUT .../ptz/.../invoke |

---

## Recording Control

| Funkcja | Opis | QVR |
|---------|------|-----|
| `start_recording(guid)` | Start ręcznego nagrywania. | PUT .../camera/mrec/{guid}/start |
| `stop_recording(guid)` | Stop ręcznego nagrywania. | PUT .../camera/mrec/{guid}/stop |

---

## Camera Search

| Funkcja | Opis | QVR |
|---------|------|-----|
| `get_camera_search()` | Szukanie kamer w LAN (UPnP/UDP). | GET .../camera/search |
| `get_camera_search_params(start_time, end_time, guid, **kwargs)` | Camera search z dodatkowymi parametrami (probe – recording search?). | GET .../camera/search |

---

## Candidate Endpoints (may 404)

| Funkcja | Opis | QVR |
|---------|------|-----|
| `get_recordingfile_noch(guid)` | recordingfile bez sufiksu kanału. | GET .../camera/recordingfile/{guid} |
| `get_recording_list(guid)` | Lista nagrań po guid. | GET .../camera/recording/{guid} |
| `get_events()` | Endpoint events. | GET .../camera/events |
| `get_recordings()` | Endpoint recordings. | GET .../camera/recordings |

---

## Generic / Probe

| Funkcja | Opis | QVR |
|---------|------|-----|
| `get_path(path, params, timeout)` | Dowolna ścieżka GET. Do probowania. | GET {path} |
| `get_event_path(subpath, params)` | Candidate /event/ (Open Event Platform). | GET .../event/... |
| `get_metadata_path(subpath, params)` | Candidate /metadata/ (Metadata Platform). | GET .../metadata/... |
| `get_qshare_path(subpath, params)` | Generyczna ścieżka qshare (np. RecordingOutput). | GET .../qshare/{subpath} |

---

## Konwertery (converters.py)

| Funkcja | Opis |
|---------|------|
| `logs_to_acc_events(raw_logs, camera_guid)` | Mapuje logi QVR na format ACC events (id, time, message, type). |
| `synthetic_recordings_summary(guid, timezone, days)` | Syntetyczne podsumowanie nagrań 24/7 (gdy brak API). |
| `synthetic_recording_segments(guid, after, before)` | Syntetyczne segmenty godzinowe (gdy brak API). |

---

## Mapowanie ACC / Frigate

| ACC | Frigate | qvr_api |
|-----|---------|---------|
| PTZ info | getPTZInfo | get_camera_capability(ptz=1) |
| Event types | events/summary | get_event_capability() |
| Events (timeline) | getEvents | get_logs workaround |
| Recordings summary | getRecordingsSummary | synthetic_recordings_summary |
| Recording segments | getRecordingSegments | synthetic_recording_segments |
| Snapshots | Event thumbnail | get_snapshot(guid) |
| Clips | has_clip | Brak (clips: false) |
| Event retain | retainEvent | Brak |
