# Lista zadań – QVR Surveillance

## Priorytet 1: Naprawy krytyczne (stream, jakość)

### 1.1 Diagnoza i naprawa RTSP 400 Bad Request
- [x] Debug log w `_get_stream_source` – URL (redacted) – v1.12.2
- [ ] Test A/B: `get_auth_string()` vs `get_auth_string_for_url()` – czy 400 znika
- [x] Debug: get_channel_live_stream loguje keys przy logger=debug
- [x] Instrukcja testu RTSP w VLC – STREAM_QUALITY (curl + VLC)
- [ ] Sprawdzić limit równoczesnych połączeń RTSP w QVR (dokumentacja / ustawienia)

### 1.2 Problem: Podgląd na żywo (preload) – obraz 1–2 s, potem błąd
**Kontekst:** Włączona opcja „Podgląd widoku z kamery” w ustawieniach encji kamery powoduje ciągłą transmisję streamu. Obraz odtwarza się 1–2 s, po czym problem wraca.

- [x] **Naprawione v1.12.2:** callback przy stream.available=False → refresh URL → update_source()
- [x] Preload × liczba kamer – opis w STREAM_QUALITY
- [x] Zalecenie wyłączenia preload – już w STREAM_QUALITY_TROUBLESHOOTING (sekcja 6)
- [x] Preload – HA oferuje toggle w UI; instrukcja wyłączenia w STREAM_QUALITY
- [ ] Rozważyć: domyślne wyłączanie preload dla QVR (workaround, wymaga sprawdzenia API kamery)

---

## Priorytet 2: Events / timeline – Advanced Camera Card

- [x] Debug w `ws_get_events`: logować instance_id, camera, raw_logs, events (count)
- [x] Instrukcja testu WebSocket w TIMELINE_EVENTS_FORMAT (DevTools, events/get)
- [x] test_iva_events.py – opis w TIMELINE_EVENTS_FORMAT
- [x] Format eventów – zweryfikowano z ACC (id, time w sec, message, type); normalizacja ms→sec
- [x] time w Unix sec (ACC: getStartTime = time*1000); `docs/TIMELINE_EVENTS_FORMAT.md`
- [x] test_timeline_events.py; PLAN_TIMELINE_EVENTS; events_media_type=all/snapshots

---

## Priorytet 3: Sensory binarnych – czas rzeczywisty i alerty

### 3.1 Czas rzeczywisty dla binary sensors IVA/Alarm
**Cel:** Binary sensory reagują na eventy prawie od razu (bez opóźnienia 60 s).

- [x] Skrócono `DEFAULT_EVENT_SCAN_INTERVAL` na 15 s (konfiguracja 15–300)
- [ ] Rozważyć WebSocket/push z QVR (jeśli API wspiera subskrypcję eventów)
- [x] `event_scan_interval` – domyślnie 15 s, dokumentacja (SENSORS_AND_LOGS: tabela reakcja/obciążenie)
- [x] Uwaga w SENSORS_AND_LOGS: krótszy interval = ryzyko limitów QVR

### 3.2 Binary sensory alertów z logów (warning/error) – latch
**Cel:** Gdy w logach (log_type 1, 2, 3) pojawi się wpis z poziomem `warning` lub `error`:
- Binary sensor **przechodzi na 1**
- Użytkownik **ręcznie** resetuje do 0 (przycisk, automatyzacja, service)

- [x] `QVRAlertLatchBinarySensor` – system (log 1+2) + per kamera (log 3)
- [x] `get_logs(level="warning")` – jeśli QVR filtruje po stronie serwera
- [x] Semantyka: on = wykryto; off = po service call
- [x] Service `qvr_surveillance.reset_alert` + RestoreEntity
- [x] Opcja (zrobione): jeden sensor „System alerts” (log 1+2) + per-kamera „Surveillance alerts” (log 3)
- [x] RestoreEntity – stan latched przetrwa restart HA

---

## Priorytet 4: Implementacja pełnego API QVR

### 4.1 Endpointy już zaimplementowane (client.py)
| Metoda | Endpoint | Status |
|--------|----------|--------|
| get_channel_list | qshare/StreamingOutput/channels | ✅ |
| get_snapshot | camera/snapshot/{guid} | ✅ |
| get_channel_streams | channel/{guid}/streams | ✅ |
| get_channel_live_stream | channel/{guid}/stream/{n}/liveStream | ✅ |
| get_recording | camera/recordingfile/... | ✅ |
| start/stop_recording | camera/mrec/{guid}/start\|stop | ✅ |
| get_camera_list | camera/list | ✅ |
| get_camera_capability | camera/capability | ✅ |
| get_event_capability | camera/capability?act=get_event_capability | ✅ |
| ptz_control | ptz/v1/.../invoke | ✅ |
| get_logs | logs/logs | ✅ |
| get_camera_search | camera/search | ✅ |

### 4.2 Endpointy do zbadania i dodania
- [x] `get_logs(level="warning")` w alert latch – client.py obsługuje
- [x] Log types 4, 5 – test_lpr_dump.py; wpis w SENSORS_AND_LOGS
- [ ] PTZ: `get_camera_capability(ptz=True)` – lista preset points, dodać select/buttons
- [x] `camera/list` – QVRRecordingStatusSensor (rec_state, status)
- [ ] Event URL / Action URL (QVR Open Event Platform) – jeśli dostępne w API
- [ ] Metadata URL – jeśli dostępne
- [x] QVR Developer: qnap.com/solution/qvr-developer, Swagger qvr_pro_api_1.1.0.yaml

### 4.3 Propozycje z PYQVRPRO_COMPARISON
- [x] EVENT_TYPES – już zawiera alarm_pir, alarm_pir_manual, alarm_output, alarm_input_manual
- [x] Atrybuty last_event „ostatni event per typ” – last_event_type, last_event_time, last_message
- [ ] LPR – po identyfikacji formatu: iva_lpr, atrybut plate_number
- [ ] Binary_sensor tylko per capability – tworzyć encje tylko dla typów wspieranych przez kamerę (opcjonalnie)

---

## Priorytet 5: Dokumentacja i sensory tekstowe

### 5.1 Docs
- [x] `docs/SENSORS_AND_LOGS.md` – tabela sensorów, log_type, jak odczytywać
- [x] README – sekcja „Sensory” z linkiem do SENSORS_AND_LOGS.md
- [x] `docs/STREAM_QUALITY_TROUBLESHOOTING.md` – sekcja o preload, zalecenie wyłączenia

### 5.2 Opisy sensorów
- [x] Tabela encji w SENSORS_AND_LOGS: device_class, ikona, znaczenie
- [x] device_class motion/problem, ikony przy sensorach

---

## Priorytet 6: Pozostałe (niski priorytet)

- [ ] KeyError w go2rtc `close_webrtc_session` – issue upstream (HA/go2rtc)
- [ ] SourceBuffer removed – znany błąd frontendu, brak działania po stronie integracji
- [x] **HEVC / encoded 0 frames** – dokumentacja: użyć Sub (H.264) zamiast Main; PLAN_QVR_ACC_FIXES, TROUBLESHOOTING
- [ ] Opcja `frontend_stream_type` / WebRTC – jeśli HA 2024.11+ wymaga zmian

---

## Kolejność realizacji (proponowana)

1. **1.1** – RTSP 400 (diagnostyka + poprawka auth jeśli to przyczyna)
2. **1.2** – Preload – dokumentacja, ewentualny workaround
3. **3.2** – Binary alerty latch (warning/error → 1, reset ręczny)
4. **2** – Timeline – debug i naprawa eventów
5. **3.1** – Krótszy event_scan_interval, opcje konfiguracji
6. **5** – Dokumentacja SENSORS_AND_LOGS, README
7. **4** – Pełne API – brakujące endpointy, LPR, PTZ presets
8. **6** – Pozostałe

---

## Notatki

- **Preload:** UI HA ostrzega, że „Ta funkcja znacznie obciąża urządzenie” – przy wielu kamerach QVR może to powodować 400 / przeciążenie.
- **Alert latch:** Wymaga service `reset_alert` – nowy service w `__init__.py`.
- **Real-time binary:** QVR API jest pull (REST), nie push – rzeczywisty real-time wymagałby WebSocket po stronie QVR (nieznane czy istnieje).
