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

Default ports: 8080 (HTTP), 443 (HTTPS). **QVR Surveillance** (standalone NVR) uses port **38080**.  
`stream_index` (optional): 0=Main (best quality, default), 1=Substream, 2=Mobile. Omit to use Main.

## Services

| Service | Description |
|---------|-------------|
| `qvr_surveillance.start_recording` | Start recording (guid, entity_id, or channel_index) |
| `qvr_surveillance.stop_recording` | Stop recording (guid, entity_id, or channel_index) |
| `qvr_surveillance.ptz_control` | PTZ (guid/entity_id/channel_index, action_id, direction) |
| `qvr_surveillance.reconnect` | Force reconnection (re-authenticate) |

## WebSocket API

| Type | Description |
|------|-------------|
| `qvr_surveillance/recordings/summary` | Recording summary (instance_id, camera, timezone) |
| `qvr_surveillance/recordings/get` | Recording segments (instance_id, camera, after, before) |
| `qvr_surveillance/events/get` | Surveillance events (camera, start, max_results, event_type) |
| `qvr_surveillance/events/summary` | Filter metadata (event_types, cameras) |
| `qvr_surveillance/logs/get` | QVR Pro logs (log_type, level, start, max_results, etc.) |

## Event types (IVA / Alarm)

Events support these QVR IVA and Alarm Input types (from logs/metadata):

- `alarm_input` – Alarm input trigger
- `iva_crossline_manual` – Cross-line (manual)
- `iva_audio_detected_manual` – Audio detection (manual)
- `iva_tampering_detected_manual` – Tampering detection (manual)
- `iva_intrusion_detected` – Intrusion detection
- `iva_intrusion_detected_manual` – Intrusion detection (manual)
- `iva_digital_autotrack_manual` – Digital autotrack (manual)

Event type is taken from `metadata.event_name`, `type`, `event_type`, or from the message content. Use `event_type` in `events/get` to filter.

## Przeglądanie nagrań / Browse recordings

### 1. Media app (Panel mediów)

1. Otwórz **Panel mediów** (Media) w Home Assistant
2. Wybierz **QVR Surveillance** jako źródło
3. Przeglądaj: Kamery → Dni (ostatnie 7) → Godziny (0–23)
4. Odtwórz wybraną godzinę

### 2. Advanced Camera Card (timeline)

1. Skonfiguruj kamerę z `engine: qvr_surveillance`
2. Włącz timeline w karcie
3. Timeline pokazuje syntetyczne segmenty (24/7) – odtwarzanie przez proxy
4. **Zdarzenia** (eventy z `qvr_surveillance/events/get`) są wyświetlane na osi czasu – miniatury używają snapshotu na żywo z kamery (jak w browse)

### 3. Konfiguracja

Brak dodatkowej konfiguracji – media source jest zarejestrowany automatycznie po dodaniu integracji. Nagrania są pobierane z QVR Pro przez proxy `/api/qvr_surveillance/{client_id}/recording/...`.

**Uwaga:** QVR Pro API nie udostępnia listy nagrań po dacie – browse zakłada typowy scenariusz 24/7 (ostatnie 7 dni). Miniatury: snapshot na żywo z kamery. **Odtwarzanie:** Endpoint `/camera/recordingfile/` może nie być wspierany przez QVR Surveillance (standalone NVR) – jeśli zwraca 404, odtwarzanie nagrań z Media nie będzie działać. QVR Pro na NAS zazwyczaj wspiera ten endpoint.

### Troubleshooting "Brak elementów"

Jeśli Media pokazuje pustą listę:
1. Upewnij się, że integracja ładuje się poprawnie (kamery QVR w HA).
2. Włącz debug: `logger: default: warning, custom_components.qvr_surveillance: debug`
3. Po otwarciu Media sprawdź logi – klucze odpowiedzi API pomogą zdiagnozować format QVR.

## Advanced Camera Card

Set `engine: qvr_surveillance` in the camera configuration.
