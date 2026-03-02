# Rozwiązywanie problemów: Timeline (eventy) + crash kamery

## 0. Eventy są (raw_logs=50, events=50) ale nie widać na timeline

**Przyczyna:** Karta Advanced Camera Card ma ustawienie **„Typ mediów na osi czasu”** = `Klipy` (clips). Eventy QVR to snapshoty – przy samych klipach nie są wyświetlane.

**Rozwiązanie:** W konfiguracji karty (edytor) → Timeline → **Typ mediów** / Events media type = `Wszystkie` lub `Snapshoty`.  
Szczegóły: `docs/PLAN_TIMELINE_EVENTS.md`.

---

## 1. Brak eventów na osi czasu (raw_logs=0)

**Log:** `events/get camera=AECCAF1253E8 raw_logs=0 events=0`

**Znaczenie:** API QVR zwraca 0 wpisów dla `get_logs(log_type=3, global_channel_id=GUID)`. Eventy na timeline pochodzą z logów surveillance (IVA, alarm, motion).

### Kroki

1. **Sprawdź IVA w QVR**  
   W panelu QVR: kamera → IVA / Intelligent Video Analytics – czy wykrywanie ruchu/alarmów jest włączone. Bez IVA QVR nie generuje log_type=3.

2. **Uruchom test skrypt:**
   ```bash
   QVR_PASS=xxx QVR_HOST=10.100.200.10 QVR_PORT=38080 python test_iva_events.py
   ```
   Jeśli `raw_logs=0` dla kanału – QVR nie ma eventów surveillance.

3. **Bez logów** – timeline pozostanie pusty. Eventy pojawią się dopiero po konfiguracji IVA i wystąpieniu zdarzeń.

---

## 2. Kamera się pojawia i zaraz znika (SourceBuffer, KeyError go2rtc)

**Błędy w logach:**
- `InvalidStateError: This SourceBuffer has been removed from the parent media source` (frontend)
- `KeyError: '01KJQ...'` w `close_webrtc_session` (HA/go2rtc)
- `socket connect failed`, `encoded 0 frames` (go2rtc)

**Przyczyna:** WebRTC przez go2rtc – błąd po stronie HA/go2rtc (znany, upstream). **HEVC:** QVR Main stream zwykle HEVC – go2rtc transkoduje na H.264; w wielu instalacjach HW HEVC zawodzi → `encoded 0 frames`. **Rozwiązanie:** Użyj Sub (H.264) zamiast Main.

### Workaround

1. **Wyłącz WebRTC** – w ustawieniach kamery w HA: „Typ streamu” = **HLS** zamiast WebRTC/Auto.  
   HLS omija go2rtc WebRTC i zwykle jest stabilniejszy.

2. **Preload wyłączony** – w ustawieniach kamery: „Podgląd widoku z kamery” = Wyłączone (ogranicza liczbę równoczesnych połączeń).

3. **Stream bezpośrednio z HA** – nie używaj go2rtc dla tej kamery; nie dodawaj jej do go2rtc w konfiguracji.

---

## 3. `('NoneType' object is not subscriptable)`

Skrócony traceback – możliwe źródła:
- go2rtc / webrtc (najczęściej)
- inna integracja

Jeśli błąd się powtarza, włącz pełny traceback:
```yaml
logger:
  default: warning
  homeassistant.components.websocket_api: debug
  homeassistant.components.go2rtc: debug
```

---

## Podsumowanie

| Problem           | Przyczyna                    | Rozwiązanie                              |
|------------------|------------------------------|------------------------------------------|
| Eventy są, nie widać | events_media_type=clips | Ustaw „Wszystkie" lub „Snapshoty"       |
| Pusty timeline   | QVR raw_logs=0, brak IVA     | Włącz IVA w QVR, test_iva_events.py     |
| Crash kamery     | WebRTC/go2rtc, SourceBuffer | Przełącz na HLS, wyłącz preload         |
| KeyError go2rtc  | Błąd upstream HA/go2rtc     | Użyj HLS zamiast WebRTC                 |
