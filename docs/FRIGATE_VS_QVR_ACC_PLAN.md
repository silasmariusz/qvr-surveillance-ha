# Frigate vs QVR – Advanced Camera Card: Comparison & Plan

## What Frigate provides to ACC (WebSocket → Integration)

| Frigate WS | Params | Returns | Purpose |
|------------|--------|---------|---------|
| `frigate/events/get` | instance_id, cameras[], after, before, limit, has_clip, has_snapshot, labels, zones, favorites | `FrigateEvent[]` | Timeline events (AI detections) |
| `frigate/events/summary` | instance_id, timezone | `EventSummary[]` | Filter metadata (labels, zones, days) |
| `frigate/recordings/summary` | instance_id, camera, timezone | `RecordingSummary` (days → hours → events count) | Timeline segments (which hours have recordings) |
| `frigate/recordings/get` | instance_id, camera, after, before | `RecordingSegment[]` | Timeline segments (start_time, end_time, id) |
| `frigate/event/retain` | instance_id, event_id, retain | – | Favorite events |
| `frigate/ptz/info` | instance_id, camera | PTZ presets | PTZ UI |

### FrigateEvent structure

```
{ camera, id, start_time, end_time, has_clip, has_snapshot, label, zones, sub_label, top_score, retain_indefinitely }
```

### RecordingSummary structure

```
[{ day: Date, events: number, hours: [{ hour: 0-23, duration: sec, events: number }] }]
```

### RecordingSegment structure

```
[{ start_time: number, end_time: number, id: string }]
```

---

## What QVR API library provides

| QVR library method | Returns | ACC mapping |
|--------------------|---------|-------------|
| `get_channels()` | channelList with guid | Camera list |
| `get_snapshot(guid)` | JPEG bytes | Event thumbnail |
| `get_live_stream(guid, stream)` | resourceUris | Live view |
| `get_recording(guid, ...)` | resourceUris / bytes | Playback (single time) |
| **get_recording_list(guid)** | **May 404** | Could map to recordings/summary if exists |
| **get_events()** | **May 404** | Could map to events/get if exists |
| `get_camera_list(guid?)` | rec_state, channel_id | Status |
| `get_camera_capability(ptz=1)` | Presets, features | PTZ info |
| `get_event_capability()` | IVA types per camera | Filter metadata |
| `get_logs(log_type=3, ...)` | **App logs (NOT events)** | Workaround only |
| `ptz_control()` | – | PTZ actions |
| `start/stop_recording()` | – | Manual record |

---

## Gap analysis

| ACC need | Frigate | QVR library | Status |
|----------|---------|--------------|--------|
| **Events** (timeline dots) | getEvents(after, before) → FrigateEvent[] | get_events() 404; get_logs workaround | No real events API. Workaround: get_logs→map |
| **Recordings summary** (days/hours) | getRecordingsSummary(camera) → day/hour/events | None. get_recording_list(guid) may 404 | Synthetic 24/7 (current) |
| **Recording segments** (timeline bars) | getRecordingSegments(after, before) | get_recording(time) – single point, no list | Synthetic hourly segments |
| **Event retain** | retainEvent(id, true/false) | None | Not supported |
| **PTZ info** | getPTZInfo | get_camera_capability(ptz=1) | Mapped via service |
| **Snapshots** | Event thumbnails from Frigate | get_snapshot(guid) | Works (live snapshot) |
| **Clips** | has_clip=true | QVR has no clips | clips: false |

---

## Implementation plan

### Phase 1: Use qvr_api in integration (DONE via client)

Integration uses `QVRClient` (client.py). qvr_api is a parallel wrapper for tools/probing. Option: integrate uses client, tools use qvr_api. No change required if client covers all.

### Phase 2: WebSocket handlers – ACC format compliance

| Handler | Current | Plan |
|---------|---------|------|
| `events/get` | get_logs(log_type=3)→_map_logs_to_events | Keep. Document as workaround. If get_events() exists, prefer it |
| `recordings/summary` | Synthetic 24/7 | Keep. Probe get_recording_list; if returns list, map to ACC format |
| `recordings/get` | Synthetic hourly | Keep. QVR has no segment list API |
| `events/summary` | event_types, cameras, event_capability | Use get_event_capability() from lib |

### Phase 3: Probe and document

- Run `tools/qvr_api_probe.py --use-library` against live QVR
- Document which endpoints 200 vs 404
- If get_recording_list or get_events returns data, add converter to ACC format

### Phase 4: Converters (qvr_api → ACC)

Add `qvr_api/converters.py`:

- `logs_to_acc_events(raw_logs, camera_guid)` → `[{id, time, message, type}]`
- `camera_list_to_acc_recordings_summary(...)` – if camera_list has per-hour info (unlikely)
- `synthetic_recordings_summary(days, timezone)` – current 24/7
- `synthetic_recording_segments(after, before, guid)` – hourly segments

### Phase 5: Checklist

- [x] qvr_api library with all endpoints
- [x] qvr_api README doc
- [x] Frigate vs QVR comparison
- [x] qvr_api/converters.py (logs_to_acc_events, synthetic_recordings_summary, synthetic_recording_segments)
- [x] ws_api uses qvr_api.converters
- [x] qvr_api moved into custom_components/qvr_surveillance/ for HACS install
- [x] Camera capability: all variants (ptz, act, per-guid), get_capability_act, get_capability_all_variants
- [x] docs/CAMERA_CAPABILITIES.md – każde zapytanie capability
- [x] Probe: all capability variants (act=…), per-guid
- [x] docs/QVR_API_FULL_REFERENCE.md – każda funkcja krótko
- [x] Probe: event/, metadata/, qshare/RecordingOutput, livestream×protocol×stream, mrec start/stop, logs level
- [ ] Probe with --use-library against live QVR, document 200 vs 404 (optional, user runs locally)
