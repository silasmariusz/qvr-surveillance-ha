# QVR Surveillance

<img src="docs/images/qvr-surveillance-ha-eye.png" alt="QVR Surveillance: Your Home Assistant's Eye - Total Control, Perfect Integration" width="600">

QVR Pro / QVR Elite / QVR Surveillance (QNAP) integration for Home Assistant. **Standalone** – no pyqvrpro dependency.

**Important:** QNAP QVR Surveillance requires a QVR server application compliant with **API 1.3.1 minimum**.

**Maintainer:** Mariusz Grzybacz, Silas ([[-__-][) qnapclub.pl, 2026.03.01

## Installation (HACS)

1. In HACS: **Settings** → **Integrations** → **Add** (➕) → **Custom repositories**
2. Add: `https://github.com/silasmariusz/qvr-surveillance-ha` | Category: **Integration**
3. Click **Add**
4. Go to **Integrations**, search for **QVR Surveillance**, install
5. Restart Home Assistant

Or use [this My Home Assistant link](https://my.home-assistant.io/redirect/hacs_repository/?owner=silasmariusz&repository=qvr-surveillance-ha&category=integration) (requires [My Home Assistant](https://my.home-assistant.io/)).

**Manual install:** Copy the `custom_components/qvr_surveillance` folder to your Home Assistant `custom_components` directory.

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
| `qvr_surveillance.reconnect` | Force reconnection (re-authenticate) |

## WebSocket API

| Type | Description |
|------|-------------|
| `qvr_surveillance/recordings/summary` | Recording summary (instance_id, camera, timezone) |
| `qvr_surveillance/recordings/get` | Recording segments (instance_id, camera, after, before) |
| `qvr_surveillance/logs/get` | QVR Pro logs (log_type, level, start, max_results, sort_field, dir, etc.) |

## Advanced Camera Card

Set `engine: qvr_surveillance` in the camera configuration.
