# QVR Surveillance

QVR Pro / QVR Elite / QVR Surveillance (QNAP) integration for Home Assistant. **Standalone** – no pyqvrpro dependency.

**Important:** QNAP QVR Surveillance requires a QVR server application compliant with **API 1.3.1 minimum**.

**Maintainer:** Mariusz Grzybacz, Silas ([[-__-][) qnapclub.pl, 2026.03.01

## Configuration

```yaml
qvr_surveillance:
  host: 10.100.200.10
  username: admin
  password: "your_password"
  use_ssl: false
  port: 8080
  client_id: qvr_surveillance
```

Default ports: 8080 (HTTP), 443 (HTTPS). If the custom port fails, the client falls back to these defaults.

## Services

| Service | Description |
|---------|-------------|
| `qvr_surveillance.start_recording` | Start recording on a channel (guid) |
| `qvr_surveillance.stop_recording` | Stop recording on a channel (guid) |
| `qvr_surveillance.ptz_control` | PTZ control (guid, action_id, direction) |

## WebSocket API

| Type | Description |
|------|-------------|
| `qvr_surveillance/recordings/summary` | Recording summary (instance_id, camera, timezone) |
| `qvr_surveillance/recordings/get` | Recording segments (instance_id, camera, after, before) |
| `qvr_surveillance/logs/get` | QVR Pro logs (log_type, level, start, max_results, sort_field, dir, etc.) |

## Advanced Camera Card

Set `engine: qvr_surveillance` in the camera configuration.
