# QVR Surveillance API – Reference (English)

*Infographic-ready. Populated from reconnaissance. Run `tools/qvr_api_probe.py` to collect real responses.*

**Zobacz także:** `QVR_API_INFOGRAFIKA.md` (schematy Mermaid), `QVR_API_WSZYSTKIE_ZAPYTANIA.md` (pełna lista zapytań).

## Critical: get_logs ≠ surveillance events

**`get_logs()`** returns **application/operational logs** (audit: settings, connections, system). **NOT** timeline events.

**Timeline source (intended):** Browse **available recordings** – continuous or event-triggered (motion, IVA, line crossing). Recording start/end = segment on timeline.

---

## 1. How to obtain X (flow table)

| Goal | API path | Params | Input | Output | Notes |
|------|----------|--------|-------|--------|-------|
| **Channel list** | GET `/qshare/StreamingOutput/channels` | sid | – | channelList[] with guid | First step for all channel-based calls |
| **Live snapshot** | GET `/camera/snapshot/{guid}` | sid | guid | JPEG bytes | Thumbnail for events |
| **Live stream URL** | POST `.../channel/{guid}/stream/{n}/liveStream` | sid | protocol: rtsp | resourceUris / url | n=0 Main, 1 Sub |
| **Recording file** | GET `/camera/recordingfile/{guid}/{ch}` | time, pre_period, post_period | Unix sec or ms | resourceUris → fetch | Pro vs Surveillance may differ |
| **Recording file (range)** | GET `/camera/recordingfile/{guid}/{ch}` | start_time, end_time | Unix sec | resourceUris | Alternative params |
| **Camera list** | GET `/camera/list` | sid, guid? | – | cameraList, rec_state | Status, channel_id |
| **IVA types** | GET `/camera/capability` | act=get_event_capability | – | Per-camera IVA support | Motion, line crossing, etc. |
| **PTZ** | GET `/camera/capability` | ptz=1 | – | Presets, features | |
| **PTZ control** | PUT `/ptz/v1/.../invoke` | direction | action_id, direction | – | start_move, stop_move |
| **App logs** | GET `/logs/logs` | log_type, max_results, … | 1–5, channel | Log entries | **NOT events** |
| **LAN cameras** | GET `/camera/search` | sid | – | Discovered devices | UPnP |

---

## 2. Recording flow (multi-step)

```
1. Auth → SID
2. GET /channels → GUIDs
3. GET /camera/list?guid=X → rec_state, channel_id
4. GET /camera/recordingfile/{guid}/{ch}?time=T&pre_period=P&post_period=Q
   → resourceUris → fetch media URL
```

**Gap:** No API to **list recordings by date** (Frigate has recordings/summary). Returns [] when get_recording_list 404s. API only.

---

## 3. Timeline data flow (desired vs current)

| Need | Desired | Current |
|------|---------|---------|
| Recording segments | API: list by date → [(start, end)] | Synthetic 24/7 |
| Events on timeline | Recordings (event-triggered) or event API | Workaround: get_logs mapped |
| Playback | get_recording(time, guid) | Same |

---

## 4. Endpoint reference

| Endpoint | Method | Params | Response |
|----------|--------|--------|----------|
| `/qvrentry` | GET | – | fw_web_ui_prefix, is_qvp → API path |
| `/qshare/StreamingOutput/channels` | GET | sid, ver | channelList |
| `/qshare/StreamingOutput/channel/{guid}/streams` | GET | sid | streams[] |
| `.../stream/{n}/liveStream` | POST | sid, protocol | resourceUris |
| `/camera/snapshot/{guid}` | GET | sid | image bytes |
| `/camera/recordingfile/{guid}/{ch}` | GET | time, pre_period, post_period | resourceUris / JSON error |
| `/camera/recordingfile/{guid}/{ch}` | GET | start_time, end_time | (probe) |
| `/camera/recording/{guid}` | GET | sid | (probe – may 404) |
| `/camera/mrec/{guid}/start` | PUT | sid | – |
| `/camera/mrec/{guid}/stop` | PUT | sid | – |
| `/camera/list` | GET | sid, guid? | cameraList, rec_state |
| `/camera/capability` | GET | sid, ptz?, act? | capability / event_capability |
| `/camera/search` | GET | sid | devices |
| `/ptz/v1/.../invoke` | PUT | sid, direction | – |
| `/logs/logs` | GET | log_type, start, max_results, … | Log items (app audit) |

---

## 5. Probe tool output

```
probe_output/
  meta.json           # timestamp, host, qvr_path
  channels_*.json
  camera_list_*.json
  camera_event_capability_*.json
  recordingfile_*_*.json  # variants
  post_livestream_*.json
  logs_type*.json
  camera_recording_*.json
  camera_recordings_*.json  # candidate (may 404)
  camera_events_*.json     # candidate (may 404)
  summary.txt
```

Run: `QVR_PASS=xxx python tools/qvr_api_probe.py --output probe_output`
