# Sensory i logi QVR

## Czas reakcji (event_scan_interval)

Sensory binarnych (IVA, alarm latch) **odpytują** API QVR (`get_logs`). QVR nie ma push/WebSocket – wykrywanie eventów jest **nieciągłe** (co N sekund).

| Interwał | Reakcja na alarm | Obciążenie QVR |
|----------|------------------|----------------|
| 15 s (domyślne) | do ~15 s opóźnienia | umiarkowane |
| 30 s | do ~30 s | niższe |

**Konfiguracja:** `event_scan_interval` 15–300 s (domyślnie 15). Przy wielu kamerach rozważyć 30 s.

---

## Typy logów (log_type)

| log_type | Znaczenie | Źródło |
|----------|-----------|--------|
| **1** | System Events | Alerty QVR (storage, uprawnienia, błędy systemu) |
| **2** | Connection Events | Połączenia/rozłączenia klientów, kamer |
| **3** | Surveillance Events | IVA (intrusion, crossline, motion), Alarm input, LPR |

---

## Text sensors (sensor)

### QVRSurveillanceAlertSensor (per kamera)
- **Log type:** 3 (Surveillance)
- **Nazwa:** „QVR Surveillance {nazwa} Alerts"
- **Wartość:** ostatni komunikat alertu (max 255 znaków)
- **Atrybuty:**
  - `recent_messages` – lista `{time, type, message}` (ostatnie 20)
  - `count` – liczba pobranych wpisów
- **Interwał:** 60 s

### QVRRecordingStatusSensor (per kamera)
- **Źródło:** `get_camera_list` / status nagrywania
- **Nazwa:** „QVR Surveillance {nazwa} Recording"
- **Wartość:** stan nagrywania (np. recording/idle)

### QVRSystemAlertSensor
- **Log type:** 1 (System)
- **Nazwa:** „QVR Surveillance System Alerts"
- **Wartość:** ostatni alert systemowy
- **Atrybuty:** `recent_messages`, `count`
- **Interwał:** 120 s

### QVRConnectionAlertSensor
- **Log type:** 2 (Connection)
- **Nazwa:** „QVR Surveillance Connection Alerts"
- **Wartość:** ostatni event połączenia
- **Atrybuty:** `recent_messages`, `count`
- **Interwał:** 120 s

---

## Binary sensors (binary_sensor)

### QVRSurveillanceBinarySensor (per kamera × per typ eventu)
- **Źródło:** `get_logs(log_type=3)` z `global_channel_id`
- **Typy:** `EVENT_TYPES` – alarm_input, iva_intrusion_detected, camera_motion, itd.
- **Nazwa:** „QVR Surveillance {nazwa} {typ}" (np. „Intrusion Detected")
- **Stan:** `on` – event w ostatnich N sekundach; `off` – brak
- **Okno czasowe:** `event_scan_interval` (domyślnie 15 s)
- **Atrybuty:** `last_event_type`, `last_event_time`, `last_message`

**Konfiguracja:** `event_scan_interval` w `configuration.yaml` (15–300 s, default 15).

### QVRAlertLatchBinarySensor (alert latch – warning/error)

- **Źródło:** `get_logs` (log 1+2 system/connection, lub log 3 per kamera)
- **Filtrowanie:** wpisy z `level` = warning lub error
- **Nazwa:** „QVR Surveillance Alert Latch" (system) lub „QVR Surveillance {kamera} Alert Latch" (per kamera)
- **Stan:** `on` = wykryto warning/error; **zostaje on aż użytkownik zresetuje**
- **Reset:** `qvr_surveillance.reset_alert` z `entity_id` sensora
- **Atrybut:** `last_message` – treść ostatniego alertu

```yaml
qvr_surveillance:
  host: 10.0.0.1
  event_scan_interval: 15   # domyślne; 30 s przy wielu kamerach
```

---

## Jak odczytywać sensory

### Text sensor – ostatnie alerty
1. DevTools → States → `sensor.qvr_surveillance_..._alerts`
2. Wartość = ostatni komunikat
3. Atrybut `recent_messages` = pełna historia (time w Unix sec)

### Binary sensor – detekcja IVA
1. Stan `on` = wykryto event danego typu w oknie `event_scan_interval`
2. `last_event_time` = timestamp ostatniego eventu
3. `last_message` = treść z logu

### Automatyzacje
```yaml
- trigger:
    - platform: state
      entity_id:
        - binary_sensor.qvr_surveillance_camera_1_intrusion_detected
      to: "on"
  action: ...
```

---

## Diagnostyka

- **Brak eventów:** Uruchom `python test_iva_events.py` – sprawdza log_type=3 per kamera.
- **Debug:** `logger: custom_components.qvr_surveillance: debug` – logi w `ws_get_events` (raw_logs, events).
