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
| **Events** (timeline dots) | getEvents(after, before) → FrigateEvent[] | get_events() only; [] when 404. Logs for HA sensors, NOT timeline | API only |
| **Recordings summary** (days/hours) | getRecordingsSummary(camera) → day/hour/events | get_recording_list lub probe get_recording/dzień | ✅ |
| **Recording segments** (timeline bars) | getRecordingSegments(after, before) | get_recording_list lub probe get_recording/godzinę | ✅ |
| **Event retain** | retainEvent(id, true/false) | None | Not supported |
| **PTZ info** | getPTZInfo | get_camera_capability(ptz=1) | Mapped via service |
| **Snapshots** | Event thumbnails from Frigate | get_snapshot(guid) | Works (live snapshot) |
| **Clips** | has_clip=true | QVR has no clips | clips: false |

---

## Implementation plan

### Phase 1: Use qvr_api in integration (DONE via client)

Integration uses `QVRClient` (client.py). qvr_api is a parallel wrapper for tools/probing. Option: integrate uses client, tools use qvr_api. No change required if client covers all.

### Phase 2: WebSocket handlers – ACC format compliance (DONE)

| Handler | Current | Status |
|---------|---------|--------|
| `events/get` | get_events() only. Logs are for HA sensors, NOT timeline | API only |
| `recordings/summary` | get_recording_list → else probe get_recording per day | ✅ |
| `recordings/get` | get_recording_list → else probe get_recording per hour | ✅ |
| `events/summary` | event_types from const + event_capability; cameras; event_capability | Dynamic from API |

### Phase 3: Probe and document

- Run `tools/qvr_api_probe.py --use-library` against live QVR
- Document which endpoints 200 vs 404
- If get_recording_list or get_events returns data, add converter to ACC format

### Phase 4: Converters (qvr_api → ACC)

Add `qvr_api/converters.py`:

- `events_response_to_acc_events(raw, camera_guid)` – map get_events() to ACC
- `recording_list_to_acc_summary(raw, guid, tz)` – map get_recording_list when format matches
- `recording_list_to_acc_segments(raw, guid, after, before)` – map get_recording_list segments
- No synthetic/fallback: API only. Returns [] when no data.

### Phase 5: Checklist

- [x] qvr_api library with all endpoints
- [x] qvr_api README doc
- [x] Frigate vs QVR comparison
- [x] qvr_api/converters.py (events_response_to_acc_events, recording_list_to_acc_*; API only, no synthetic)
- [x] ws_api uses qvr_api.converters
- [x] qvr_api moved into custom_components/qvr_surveillance/ for HACS install
- [x] Camera capability: all variants (ptz, act, per-guid), get_capability_act, get_capability_all_variants
- [x] docs/CAMERA_CAPABILITIES.md – każde zapytanie capability
- [x] Probe: all capability variants (act=…), per-guid
- [x] docs/QVR_API_FULL_REFERENCE.md – każda funkcja krótko
- [x] Probe: event/, metadata/, qshare/RecordingOutput, livestream×protocol×stream, mrec start/stop, logs level
- [x] docs/QVR_API_INFOGRAFIKA.md – Mermaid schematy, przepływy
- [x] docs/QVR_API_WSZYSTKIE_ZAPYTANIA.md – każdy endpoint, każdy wariant
- [ ] Probe with --use-library against live QVR, document 200 vs 404 (user runs locally)
