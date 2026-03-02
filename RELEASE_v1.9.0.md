## v1.9.0

### New features
- Per-type IVA binary sensors – separate sensor per event type (intrusion, crossline, alarm_input, etc.)
- Alert text sensors – camera alerts + system alerts (log_type 1, 3)
- get_event_capability – available IVA types per camera
- test_iva_events.py – diagnostic script for events/IVA

### Improvements
- Extended event parsing, assumed_guid for filtered API responses
- Cache per camera per type, fallback fetch without global_channel_id
