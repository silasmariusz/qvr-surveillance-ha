# Plan weryfikacji i napraw

## 1) Diagnoza błędu RTSP 400 Bad Request

### Błąd
```
Error from stream worker: Bad Request Error opening stream (Server returned 400 Bad Request, rtsp://****:****@10.100.200.10:10273/channel3)
```
- Rejestrator: `camera.qvr_surveillance_camera_003`
- Źródło: `homeassistant/components/stream/__init__.py:491` (worker PyAV)

### Możliwe przyczyny 400 Bad Request

| # | Hipoteza | Jak zweryfikować | Naprawa |
|---|----------|------------------|---------|
| 1 | **Auth w URL** – QVR RTSP może oczekiwać innego formatu (Digest, token zamiast user:pass) | Sprawdzić czy QVR zwraca URL z creds w query; logować (redacted) pełny URL przed przekazaniem do stream | Próba: credentials w query `?user=&password=` albo bez auth w URL (session) |
| 2 | **URL-encoding** – `quote(..., safe='')` może przekształcać znaki tak, że QVR odrzuca | Porównać `get_auth_string` (bez encoding) vs `get_auth_string_for_url` | Tymczasowo użyć `get_auth_string()` jak pyqvrpro – test A/B |
| 3 | **Format ścieżki** – QVR zwraca `/channel3` (1-based), a serwer oczekuje np. `/channel/3` lub innej konwencji | Dump odpowiedzi `get_channel_live_stream` (resourceUris) dla kilku kamer | Brak – URL pochodzi z API QVR; jeśli 400, możliwy bug po stronie QVR lub inna wersja API |
| 4 | **Port / sesja** – 10273 to dynamiczny port RTSP QVR; sesja wygasa; przy retry worker używa starego URL | ✅ **Naprawione v1.12.2:** callback przy `stream.available=False` → refresh URL → `update_source()` → fast restart z nowym URL |
| 5 | **Concurrent streams** – QVR limituje połączenia RTSP | Sprawdzić liczbę równoczesnych streamów (Main+Sub × kamery) | Ograniczyć substream, preload_stream wyłączony |
| 6 | **Tylko kamera 3** – jeśli inne działają, problem specyficzny dla tego kanału | Test streamu dla camera_001, camera_002 vs 003 | Konfiguracja QVR dla kanału 3, stan kamery |

### Kroki diagnostyczne

1. **Włącz debug integracji**
   ```yaml
   logger:
     default: warning
     custom_components.qvr_surveillance: debug
     homeassistant.components.stream: debug
   ```

2. **Logować URL (redacted) w `_get_stream_source`**
   - Dodać `_LOGGER.debug("Stream URL (redacted): rtsp://****@%s", url.split("@")[-1] if "@" in url else url)`
   - Sprawdzić czy ścieżka to `/channel3`, `/channel/3` itd.

3. **Ręczny test RTSP**
   - Pobierz URL: `curl -H "Authorization: Bearer $TOKEN" http://ha:8123/api/camera_stream_source/camera.qvr_surveillance_camera_003`
   - Odtwórz w VLC: `vlc "rtsp://user:pass@10.100.200.10:10273/channel3"`
   - Jeśli VLC działa a PyAV nie – problem po stronie klienta (np. auth)

4. **Test bez URL-encoding**
   - Tymczasowa zmiana w `camera.py`: `auth = f"{client.get_auth_string()}@"` zamiast `get_auth_string_for_url()` – jeśli 400 zniknie, problem w encoding.

5. **Dump surowej odpowiedzi API**
   - W `get_channel_live_stream` zalogować `resp` (bez haseł) – sprawdzić pełną strukturę, czy jest `auth`/`token` w odpowiedzi.

### Błędy poboczne (nie blokują streamu)

- **SourceBuffer removed** – błąd frontendu (Edge/Chrome) przy zamknięciu streamu; znany w HA/webrtc.
- **KeyError w go2rtc** – `close_webrtc_session` wywołany dla nieistniejącej sesji; race przy zamykaniu karty. Do zgłoszenia upstream (HA/go2rtc).

---

## 2) Events / timeline – Advanced Camera Card

### Wymagania karty

Karta z `engine: qvr_surveillance` wywołuje WebSocket:
- `qvr_surveillance/events/get`: `instance_id`, `camera` (guid), `start_time`, `end_time`, `event_type`
- `qvr_surveillance/events/summary`: `instance_id`

### Mapowanie camera → guid

- Karta bierze `qvr_guid` i `qvr_client_id` z atrybutów encji kamery.
- `instance_id` = `qvr_client_id` (np. `qvr_surveillance`)
- `camera` = `qvr_guid` (GUID kanału z QVR)

### Możliwe przyczyny braku eventów na timeline

| # | Hipoteza | Weryfikacja | Naprawa |
|---|----------|-------------|----------|
| 1 | Karta wysyła `entity_id` zamiast `guid` | Debug WebSocket – logować `msg["camera"]` w `ws_get_events` | Upewnić się, że karta używa `qvr_guid` |
| 2 | `get_logs` zwraca pustą listę | `test_iva_events.py` – czy są eventy dla danej kamery | QVR: log_type=3, IVA włączone, sprawdzić `global_channel_id` |
| 3 | Format odpowiedzi niezgody z oczekiwaniami karty | Porównać strukturę `_map_logs_to_events` z dokumentacją ACC | Dodać brakujące pola (`thumbnail_url`, `start_time`, `end_time`?) |
| 4 | Timestamps – różne strefy/formaty | Log `events[0]` – czy `time` w sec, ms? | Normalizacja do Unix sec |
| 5 | Konfiguracja karty – brak `engine` / `qvr_surveillance` | Sprawdzić YAML karty | Dodać `engine: qvr_surveillance` i `qvr_surveillance.client_id` |

### Kroki diagnostyczne

1. **Test `ws_get_events` bezpośrednio**
   - W DevTools → WebSocket: wysłać
   ```json
   {"id": 1, "type": "qvr_surveillance/events/get", "instance_id": "qvr_surveillance", "camera": "<GUID_KAMERY>", "start_time": 1738300000, "end_time": 1738400000}
   ```
   - Sprawdzić czy zwracana jest niepusta lista eventów.

2. **Pobranie GUID**
   - DevTools → States → `camera.qvr_surveillance_camera_003` → atrybut `qvr_guid`.

3. **`test_iva_events.py`**
   ```bash
   QVR_PASS=xxx python test_iva_events.py --dump-raw
   ```
   - Sprawdzić czy są wpisy log_type=3 dla `global_channel_id` = GUID kamery 3.

4. **Sprawdzenie kodu ACC**
   - Repo: `dermotduffy/advanced-camera-card` – plik engine dla `qvr_surveillance` / `Engine.QVRSurveillance`.
   - Zweryfikować dokładny schemat: nazwy pól (`camera` vs `camera_entity`), format `time`, wymagane pola.

### Testy naprawcze

- [ ] Dodać debug log w `ws_get_events`: `msg`, liczba `raw_logs`, liczba `events`.
- [ ] Zweryfikować w ACC, czy oczekiwane są pola `start_time`, `end_time` na evencie.
- [ ] Sprawdzić czy `instance_id` musi być ścisłe powiązane z konfiguracją (np. wielu instancji QVR).

---

## 3) Sensory logów i binary – dokumentacja i dynamika

### Obecny stan

**Text sensors (sensor.py):**
- `QVRSurveillanceAlertSensor` – per kamera, log_type=3 (surveillance)
- `QVRRecordingStatusSensor` – per kamera (status nagrywania)
- `QVRSystemAlertSensor` – jeden, log_type=1 (system)
- `QVRConnectionAlertSensor` – jeden, log_type=2 (connection)

**Binary sensors (binary_sensor.py):**
- Per kamera × per `EVENT_TYPES` (intrusion, crossline, alarm_input, motion, itd.)
- Lista z góry: `EVENT_TYPES` w `const.py`, nie z `get_event_capability`
- Wszystkie typy tworzone dla każdej kamery; `off` gdy brak eventu

### Log types (log_type)

| log_type | Znaczenie | Sensor |
|----------|-----------|--------|
| 1 | System alerts | QVRSystemAlertSensor |
| 2 | Connection events | QVRConnectionAlertSensor |
| 3 | Surveillance (IVA, motion, alarm) | QVRSurveillanceAlertSensor, binary_sensor |

### Co dodać / zmienić

1. **Dokumentacja sensorów**
   - Nowy plik: `docs/SENSORS_AND_LOGS.md` z:
     - Tabelą sensorów (nazwa, log_type, opisy)
     - Jak odczytywać alerty (atrybuty, `recent_messages`)
     - Jak działają binary sensory (okno czasowe, `event_scan_interval`)

2. **Opcjonalnie: sensory per capability**
   - `get_event_capability` zwraca typy IVA per kamera
   - Obecnie: sensory dla wszystkich `EVENT_TYPES` zawsze
   - Opcja: tworzyć binary_sensor tylko dla typów wspieranych przez daną kamerę (mniej encji, mniej zapytań API)

3. **README**
   - Krótka sekcja „Sensory” z linkiem do `docs/SENSORS_AND_LOGS.md`

### Zadania

- [ ] Dodać `docs/SENSORS_AND_LOGS.md`
- [ ] Uzupełnić README o link do tej dokumentacji
- [ ] (Opcjonalnie) Rozważyć filtrowanie binary_sensor przez `get_event_capability` – osobny task.

---

## Kolejność realizacji

1. **RTSP 400** – diagnostyka (logi, test auth, test VLC), potem poprawki.
2. **Timeline** – debug WebSocket, `test_iva_events`, porównanie z ACC.
3. **Sensory** – dokumentacja `SENSORS_AND_LOGS.md`, ewentualnie ulepszenie README.
