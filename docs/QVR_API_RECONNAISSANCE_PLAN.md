# QVR Surveillance API – Reconnaissance Plan

## Critical: get_logs ≠ surveillance events

**`get_logs()` returns application/operational logs**, NOT timeline events.

| log_type | Purpose (API schema) |
|----------|----------------------|
| 1 | Surveillance **Settings** |
| 2 | Surveillance **Events** (app log) |
| 3 | Surveillance **Connection** |
| 4 | System **Events** |
| 5 | System **Connection** |

These are audit logs for QVR (NAS, connections). **Timeline** should come from **recordings** – browse available recordings (continuous or event-triggered: motion, IVA, line crossing). Recording time = segment on timeline.

---

## Objectives

1. Discover all QVR API endpoints
2. Identify real sources for timeline (recording list, event API)
3. Map API → ACC format
4. Produce English reference doc (infographic input)

---

## Phase 1: Endpoint inventory

From client.py: channels, snapshot, streams, liveStream, recordingfile, mrec start/stop, camera/list, capability, event_capability, ptz, logs, camera/search.

**To probe:** recording list by date, event/subscription endpoints, metadata search.

---

## Phase 2: Test platform

`tools/qvr_api_probe.py` – auth, probe each endpoint, save to `probe_output/`.

---

## Phase 3: Reference doc (EN)

`docs/QVR_API_REFERENCE.md` – endpoint table, how to get recordings/events, gaps vs ACC.
