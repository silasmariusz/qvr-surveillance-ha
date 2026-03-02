# QVR Surveillance API – Reconnaissance Plan (Full)

## Critical: get_logs ≠ surveillance events

**`get_logs()`** returns **application/operational logs** for auditing QVR (settings, connections, system). NOT timeline events.

| log_type | Purpose (API schema) |
|----------|----------------------|
| 1 | Surveillance **Settings** (config changes) |
| 2 | Surveillance **Events** (app-level event log) |
| 3 | Surveillance **Connection** (connect/disconnect) |
| 4 | System **Events** |
| 5 | System **Connection** |

**Timeline source:** Browse **available recordings** – continuous or event-triggered (motion, IVA, line crossing). Recording start/end = segment on timeline.

---

## Objectives

1. **Full endpoint inventory** – all paths from client, spec, pyqvrpro
2. **Identify real timeline sources** – recording list, event API, metadata search
3. **Multi-step flows** – auth → channels → recording list → segment; some require chained calls
4. **Collect response material** – probe each endpoint, save raw JSON for analysis
5. **Infographic-ready reference** – how to obtain X, what you get, in what form

---

## Phase 1: Endpoint inventory (complete)

### 1.1 Streaming & channels

| Endpoint | Method | Params | Purpose |
|----------|--------|--------|---------|
| `/qvrentry` | GET | – | Discover API path (qvrpro/qvrelite/qvrsurveillance) |
| `/qshare/StreamingOutput/channels` | GET | sid | Channel list |
| `/qshare/StreamingOutput/channel/{guid}/streams` | GET | sid | Stream config (Main/Sub/Mobile) |
| `.../stream/{n}/liveStream` | POST | protocol (rtsp) | RTSP URL for live view |
| `/camera/snapshot/{guid}` | GET | sid | Live snapshot |

### 1.2 Recordings

| Endpoint | Method | Params | Purpose |
|----------|--------|--------|---------|
| `/camera/recordingfile/{guid}/{channel_id}` | GET | time, pre_period, post_period | Recording file (single time) |
| `/camera/recordingfile/{guid}/{channel_id}` | GET | start_time, end_time | Alternative params (Pro vs Surveillance) |
| `/camera/recording/{guid}` | GET | ? | **Probe:** list recordings by date? |
| `/camera/recordingfile/{guid}` | GET | ? | **Probe:** list segments? |
| `/camera/mrec/{guid}/start` | PUT | sid | Start manual record |
| `/camera/mrec/{guid}/stop` | PUT | sid | Stop manual record |

### 1.3 Camera & capability

| Endpoint | Method | Params | Purpose |
|----------|--------|--------|---------|
| `/camera/list` | GET | sid, guid? | Camera list, rec_state, status |
| `/camera/capability` | GET | sid, guid?, ptz? | PTZ, features |
| `/camera/capability` | GET | act=get_event_capability | IVA types per camera |
| `/camera/search` | GET | sid | LAN camera discovery (UPnP) |
| `/ptz/v1/channel_list/{guid}/ptz/action_list/{id}/invoke` | PUT | sid, direction? | PTZ control |

### 1.4 Logs (application audit – NOT events)

| Endpoint | Method | Params | Purpose |
|----------|--------|--------|---------|
| `/logs/logs` | GET | log_type, start, max_results, start_time, end_time, channel_id, global_channel_id | Application logs |

### 1.5 Candidate paths (to probe)

From QVR Developer: Open Event Platform, Metadata Platform.

| Path (candidate) | Probe |
|------------------|-------|
| `/camera/recordings` | List by date? |
| `/camera/events` | Event list? |
| `/event/` | Event subscription? |
| `/metadata/` | Metadata search? |
| `/camera/search` with date params | Search recordings? |
| `/qshare/` variants | Recording summary? |

---

## Phase 2: Multi-step flows

Some goals require chained calls. Probe and document:

### Flow A: Timeline segments from recordings

1. Auth → SID  
2. `GET /channels` → channel GUIDs  
3. **Missing:** API to list recordings by date for GUID  
4. If found: map to ACC `recordings/summary`, `recordings/get`  
5. Fallback: synthetic 24/7 (current)

### Flow B: Event-triggered recordings

1. `GET /camera/capability?act=get_event_capability` → IVA types  
2. **Probe:** Does `camera/list` include event metadata per hour?  
3. **Probe:** Does `recordingfile` with params return event-type info?

### Flow C: Recording playback

1. Auth → SID  
2. GUID, channel_id from channels/camera_list  
3. `GET /camera/recordingfile/{guid}/{ch}` with time params  
4. Response: `resourceUris`/`url` → fetch media  
5. Try: time (sec), time (ms), start_time/end_time, start/end

---

## Phase 3: Probe matrix

For each endpoint, try:

| Param set | Values |
|-----------|--------|
| recordingfile time | Unix sec, Unix ms |
| recordingfile range | start_time/end_time, start/end, time+pre/post |
| channel_id | 0, 1, from camera_list |
| log_type | 1, 2, 3, 4, 5 |
| logs filter | global_channel_id, start_time, end_time |
| camera/list | no params, guid=X |
| capability | ptz=0, ptz=1, act=get_event_capability |

---

## Phase 4: Output structure (probe_output/)

```
probe_output/
  meta.json                 # Run timestamp, host, qvr_path
  channels_*.json
  channel_streams_*.json
  camera_list_*.json
  camera_list_guid_*.json
  camera_capability_*.json
  camera_event_capability_*.json
  logs_type1_*.json ... logs_type5_*.json
  camera_search_*.json
  recordingfile_time_sec_*.json
  recordingfile_time_ms_*.json
  recordingfile_start_end_*.json
  recordingfile_start_end_alt_*.json
  camera_recording_*.json
  post_livestream_*.json
  candidate_*_*.json       # 404s documented
  summary.txt              # Quick overview: ok/fail per probe
```

---

## Phase 5: Analysis checklist

After running probes:

- [ ] Which recording params does QVR accept (Pro vs Surveillance)?
- [ ] Does `camera/recording` or `recordingfile` without time return list?
- [ ] Does `camera/list` contain per-hour/per-day recording info?
- [ ] Does `event_capability` map to recording metadata?
- [ ] Log types 1–5: structure of each, useful for anything?
- [ ] Any endpoint returns `[(start, end, camera), ...]` for timeline?

---

## Phase 6: Reference doc (infographic input)

Produce `QVR_API_REFERENCE.md` with:

1. **Endpoint table** – path, method, params, response shape (from probe)
2. **Flow: "How to obtain X"** – decision tree / table
3. **Input→Output** – for each goal (recordings, events, playback)
4. **Gaps vs ACC** – what exists, what's missing, workarounds
