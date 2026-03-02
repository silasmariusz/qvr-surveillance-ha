# Porównanie: pyqvrpro vs qvr_surveillance (nasza integracja)

## Dlaczego pyqvrpro ma więcej w YAML?

Fixtures w `pyqvrpro` (repo oblogic7) to **VCR cassettes** – nagrania odpowiedzi API z testów. Zawierają:

| Fixture | Endpoint | Nasza obsługa |
|---------|----------|---------------|
| `camera_list.yaml` | `camera/list` | ✅ `get_camera_list()` |
| `camera_capability.yaml` | `camera/capability?act=get_camera_capability` | ✅ `get_camera_capability()` |
| `event_capability.yaml` | `camera/capability?act=get_event_capability` | ✅ `get_event_capability()` |
| `camera_snapshot.yaml` | snapshot | ✅ `get_snapshot()` |
| `channel_list.yaml` | `qshare/StreamingOutput/channels` | ✅ `get_channels()` |
| `channel_streams.yaml` | streams | ✅ używane przy RTSP |
| `channel_live_stream_rtsp.yaml` | live RTSP URL | ✅ `get_channel_live_stream_rtsp()` |
| `login.yaml` | auth | ✅ `_do_auth()` |
| `invalid_auth.yaml` | auth fail | ✅ `QVRAuthError` |
| `start_recording.yaml` | start record | ✅ `start_recording()` |
| `stop_recording.yaml` | stop record | ✅ `stop_recording()` |

**Brak w fixtures pyqvrpro:**
- `logs/logs` – **my mamy** `get_logs()`
- LPR – fixtures z 2019, przed QVR 2.4.0

Czyli: pyqvrpro **nie** ma więcej endpointów niż my – ma mniej (brak logów). Fixtures to po prostu lista tego, co testowali w 2019. My dodaliśmy logi, event capability, binary/text sensory.

---

## Typy eventów: pyqvrpro vs my

Z `event_capability.yaml` (pyqvrpro):

- `camera_motion`, `motion_manual`
- `alarm_input`, `alarm_input_manual`
- `alarm_pir`, `alarm_pir_manual`, `alarm_output`
- `iva_crossline_manual`, `iva_audio_detected_manual`, `iva_tampering_detected_manual`
- `iva_intrusion_detected`, `iva_intrusion_detected_manual`
- `iva_digital_autotrack_manual`

**Nasze `EVENT_TYPES` (const.py):**
- Mamy: alarm_input, iva_*, camera_motion, motion_manual
- **Brakuje:** `alarm_pir`, `alarm_pir_manual`, `alarm_output`, `alarm_input_manual`

Mogliśmy dodać te brakujące – prawdopodobnie QVR zwraca je w logach. Warto rozszerzyć `EVENT_TYPES` o nie (jeśli pojawią się w realnych danych).

---

## Co jeszcze możemy zbierać?

### 1. Z API które już używamy

| Źródło | Dane | Status |
|--------|------|--------|
| `get_event_capability` | Lista IVA/Alarm per kamera | ✅ używane w binary_sensor |
| `get_logs(log_type=1)` | System alerts | ✅ text sensor |
| `get_logs(log_type=2)` | Connection events | ❌ nie zbieramy |
| `get_logs(log_type=3)` | Surveillance (IVA, motion, LPR?) | ✅ binary + text |
| `get_camera_list` | Status kamer (online/offline, recording) | częściowo w `camera/list` |
| `get_camera_capability` | PTZ, preset points | ✅ używane przy PTZ |

### 2. Endpointy z dokumentacji QVR (do zbadania)

Na podstawie typowych API NVR/QNAP:

- `camera/search` – ✅ mamy `get_camera_search()` (szukanie kamer w sieci)
- `logs/logs` z `level` – filtrowanie po poziomie (info/warning/error)
- Inne `log_type` – warto przetestować 4, 5, ... czy API zwraca
- Ewentualne endpointy LPR (jeśli QVR ma osobny) – brak publicznej dokumentacji

### 3. Propozycje rozszerzeń

1. **Rozszerzyć EVENT_TYPES** – dodać `alarm_pir`, `alarm_pir_manual`, `alarm_output`, `alarm_input_manual`
2. **Text sensor dla log_type=2** – Connection events (połączenia/rozłączenia klientów)
3. **LPR** – po zidentyfikowaniu formatu (patrz TEST_PLAN_LPR.md) dodać `iva_lpr` / `lpr_plate` + sensor z atrybutem `plate_number`
4. **Sensor „ostatni event per typ”** – np. ostatni motion, ostatni intrusion – można wyciągnąć z `parse_recent_events_per_channel_and_type`, eksponować jako atrybut
5. **get_camera_list** – status „recording” per kamera – potencjalnie nowy sensor lub atrybut na istniejącej encji

---

## Aktualizacja – HA 2025+

pyqvrpro ma 7 lat; implementacje w oficjalnym HA QVR Pro mogły się zmienić. W HA 2025.06+ kamery **muszą** ustawiać `CameraEntityFeature.STREAM`, inaczej stream nie startuje (tylko snapshoty). Szczegóły: `docs/PYQVRPRO_STREAM_COMPARISON.md`.

---

## Podsumowanie

- **pyqvrpro ma mniej** – brak logów. Fixtures to tylko to, co testowali.
- **My zbieramy już więcej** – logi, event capability, binary/text sensory.
- **Możemy zbierać jeszcze:** alarm_pir*, alarm_output, log_type=2, LPR (gdy format znany), status recording z camera/list.
