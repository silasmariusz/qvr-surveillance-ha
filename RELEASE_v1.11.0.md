## v1.11.0

### New features
- **Recording status sensor** – per camera: state recording/idle, attributes status, rec_state, rec_state_err_code (from camera/list)
- **Unknown event types** – metadata.event_name (e.g. LPR) now passed through to text sensors even when not in EVENT_TYPES

### Improvements
- Better support for future LPR – unknown types show correctly in recent_messages
- camera/list parsing supports single-camera response when filtered by guid
