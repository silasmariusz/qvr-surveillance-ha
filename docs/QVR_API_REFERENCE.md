# QVR Surveillance API – Reference (English)

*Populated from reconnaissance. See `QVR_API_RECONNAISSANCE_PLAN.md` and `tools/qvr_api_probe.py`.*

## Important: get_logs ≠ surveillance events

**`get_logs()`** returns **application/operational logs** for auditing the QVR server (settings changes, connection events, system events). These are NOT the source of timeline events.

**Timeline source (intended):** Browse **available recordings** – continuous or event-triggered (motion, IVA, line crossing). Recording start/end time defines the segment on the timeline.

---

## Endpoint summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/qshare/StreamingOutput/channels` | GET | Channel list |
| `/camera/snapshot/{guid}` | GET | Live snapshot |
| `/qshare/StreamingOutput/channel/{guid}/streams` | GET | Stream config |
| `.../stream/{n}/liveStream` | POST | RTSP URL |
| `/camera/recordingfile/{guid}/{channel_id}` | GET | Recording file (time range) |
| `/camera/mrec/{guid}/start` | PUT | Start manual record |
| `/camera/mrec/{guid}/stop` | PUT | Stop manual record |
| `/camera/list` | GET | Camera list, rec_state, status |
| `/camera/capability` | GET | PTZ; `act=get_event_capability` for IVA types |
| `/ptz/v1/.../invoke` | PUT | PTZ control |
| `/logs/logs` | GET | **Application logs** (NOT timeline events) |
| `/camera/search` | GET | LAN camera discovery |

---

## How to obtain timeline data

| Need | Current approach | Proper approach (TBD) |
|------|------------------|------------------------|
| Recording segments | Synthetic 24/7 × 7 days | Real API if exists: list recordings by date |
| Events on timeline | Workaround: get_logs → map | Recordings-based: segment = event; or dedicated event API |
| Recording playback | `get_recording(time, guid)` | Same – requires time from segment |

---

## Probe tool

Run: `QVR_PASS=xxx python tools/qvr_api_probe.py`

Saves raw responses to `probe_output/`. Use to discover response structure and identify recording/event endpoints.
