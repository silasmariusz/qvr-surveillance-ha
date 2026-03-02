# Plan napraw QVR + Advanced Camera Card

## Zdiagnozowane problemy

| # | Problem | Przyczyna | Status |
|---|---------|-----------|--------|
| 1 | Błąd `cameras[0] → dependencies → cameras` | Nieprawidłowy format `dependencies.cameras` | Dokumentacja + workaround |
| 2 | HLS 404, encoded 0 frames, pixelacja/crash streamu | go2rtc nie otrzymuje klatek z RTSP QVR | Workaround + zalecenia |
| 3 | Brak eventów na timeline (raw_logs 50 vs 0) | Różne okna czasowe + `events_media_type` | events_media_type=all |
| 4 | Galeria: clips → error, snapshots/nagrania → puste | clips:false (QVR=snapshoty), możliwe filtrowanie | Weryfikacja |
| 5 | Auto `client_id` – czy można pominąć? | ACC już pobiera z atrybutu encji | ✓ Działa |
| 6 | `'NoneType' object is not subscriptable` | Prawdopodobnie go2rtc lub inna integracja | Traceback |
| 7 | „Podgląd widoku z kamery” wyłączony → brak dobrego obrazu | HA nie tworzy streamu wcześniej | Zalecenia |

---

## 1. Dependencies – błąd konfiguracji

**ACC wymaga:** `dependencies.cameras` = tablica stringów (entity_id), np.:
```yaml
dependencies:
  cameras:
    - camera.qvr_surveillance_camera_001_sub
```

**Typowe przyczyny błędu:**
- Wpisano pojedynczy string zamiast tablicy: `cameras: camera.xxx_sub` ❌
- Edytor UI zapisał inny format (np. obiekt zamiast tablicy)

**Rozwiązanie:** Jeśli błąd się pojawia – **usuń** `dependencies` z konfiguracji kamery (przycisk Main/Sub nie będzie działał, ale reszta tak). Albo użyj dokładnie:
```yaml
dependencies:
  all_cameras: false
  cameras:
    - camera.qvr_surveillance_camera_001_sub
```

Entity Sub musi istnieć (add_substream: true w integracji) i mieć nazwę np. `camera.qvr_surveillance_<nazwa>_sub`.

---

## 2. Stream (HLS 404, encoded 0 frames)

**Przyczyna HEVC:** QVR Main stream zwykle używa HEVC. go2rtc transkoduje na H.264 – w wielu instalacjach hardware HEVC zawodzi, stąd `encoded 0 frames` (znany problem Reolink/Axis/QNAP).

**Rekomendacja:** Ustaw kamerę IP w QVR na **H.264**, jeśli nie używasz go2rtc ani karty WebRTC – README integracji zawiera tę sugestię.

**Obserwacje:**
- `master_playlist.m3u8 404` – HA nie serwuje HLS
- `encoded 0 frames` – go2rtc nie dostaje klatek z RTSP
- `socket connect failed` – problemy z połączeniem go2rtc

**Workaround (kolejność):**
1. **Użyj Sub zamiast Main** – Sub zwykle H.264. W ACC: `camera_entity: camera.xxx_sub`.
2. **Typ streamu:** Kamera → HLS.
3. **Włącz „Podgląd widoku z kamery”** w HA: Ustawienia → Urządzenia i usługi → kamera → włącz przełącznik. Dzięki temu HA tworzy stream z wyprzedzeniem.
4. **go2rtc:** Sprawdź localhost:11984. Przy HEVC - wyłączenie HW acceleration w go2rtc. „Typ streamu” 
---

## 3. Timeline – eventy

**Logi:** `raw_logs=50 events=50` vs `raw_logs=0 events=0` – zależnie od okna czasowego.

**Konfiguracja karty:**
```yaml
timeline:
  events_media_type: all   # lub: snapshots (nie clips!)
```

QVR zwraca snapshoty zdarzeń, nie klipy wideo. Przy `events_media_type: clips` eventy się nie wyświetlają.

**Odświeżanie na żywo:** ACC (od zmiany w controller.ts) odświeża timeline co ~1 min, gdy widoczne okno obejmuje „teraz” (koniec w ciągu 2 min). Lista eventów uzupełnia się o bieżące nagrania bez interakcji użytkownika.

---

## 4. Galeria (snapshots, nagrania)

- **Clips:** QVR nie obsługuje klipów – `clips: false` w capabilities. Wybór „Clips” daje błąd – to oczekiwane.
- **Snapshots / Recordings:** Powinny działać, jeśli timeline zwraca eventy. Sprawdź `events_media_type: all` oraz filtr „Kiedy” (np. „Ostatni miesiąc”) – eventy muszą być w wybranym zakresie.

---

## 5. Auto client_id (ACC)

ACC automatycznie pobiera `client_id` z atrybutu encji `qvr_client_id`. **Nie musisz** wpisywać:
```yaml
qvr_surveillance:
  client_id: qvr_surveillance
```
jeśli encja ma ten atrybut (integracja qvr_surveillance go ustawia). Możesz go pominąć.

---

## 6. NoneType / traceback

Błąd `('NoneType' object is not subscriptable)` często pochodzi z go2rtc. Włącz pełny traceback:
```yaml
logger:
  default: warning
  homeassistant.components.go2rtc: debug
  custom_components.qvr_surveillance: debug
```

---

## 7. Minimalna konfiguracja karty (bez dependencies)

```yaml
type: custom:advanced-camera-card
cameras:
  - camera_entity: camera.qvr_surveillance_camera_001
    engine: qvr_surveillance
    live_provider: ha
    # dependencies pomijamy jeśli powoduje błąd
timeline:
  events_media_type: all
  show_recordings: true
```
