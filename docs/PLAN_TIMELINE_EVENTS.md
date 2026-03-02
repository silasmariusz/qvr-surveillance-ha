# Plan wdrożenia eventów na timeline

## Status

- [x] Integracja zwraca eventy (ws_get_events → get_logs log_type=3)
- [x] Format zgodny z ACC: id, time (Unix sec), message, type
- [ ] **Eventy widoczne na osi czasu** – wymaga konfiguracji karty

## Dlaczego 50 eventów nie widać na timeline

Advanced Camera Card filtruje eventy według `events_media_type`:

| Wartość       | Znaczenie                         | QVR eventy (snapshots) |
|---------------|-----------------------------------|--------------------------|
| `clips`       | Tylko klipy wideo                 | ❌ Nie pokazuje          |
| `snapshots`   | Tylko snapshoty (thumbnails)     | ✅ Pokazuje              |
| `all`         | Oba                               | ✅ Pokazuje              |

**QVR eventy to snapshots** (QVREventViewMedia, ViewMediaType.Snapshot). Przy `events_media_type: clips` karta nie renderuje naszych eventów.

### Konfiguracja w karcie

1. Edytor konfiguracji karty → Timeline (lub Live controls)
2. **Typ mediów na osi czasu** / **Events media type** = `Wszystkie` lub `Snapshoty`
3. Nie ustawiaj tylko `Klipy`

Ścieżki w YAML:
- `timeline.events_media_type: all` lub `snapshots`
- `live.controls.timeline.events_media_type: all` / `snapshots`

## Testy

### 1. Test formatu eventów
```bash
QVR_PASS=xxx python test_timeline_events.py
QVR_PASS=xxx python test_timeline_events.py --camera AECCAF1253E8 --dump-events
```

### 2. Test pełnej ścieżki (HA + WebSocket)
- Włącz debug: `logger: custom_components.qvr_surveillance: debug`
- Otwórz timeline dla kamery QVR
- Sprawdź logi: `events/get ... raw_logs=N events=M`
- Jeśli events>0 i nadal brak na timeline → sprawdź events_media_type

### 3. Weryfikacja w DevTools
Wyślij WebSocket:
```json
{"id": 1, "type": "qvr_surveillance/events/get", "instance_id": "qvr_surveillance", "camera": "AECCAF1253E8", "max_results": 50}
```
Odpowiedź powinna zawierać tablicę eventów z id, time, message, type.

## Checklist wdrożenia

1. [x] get_logs(log_type=3, global_channel_id) zwraca eventy
2. [x] _map_logs_to_events – format ACC
3. [x] time w Unix seconds (ms→s normalizacja)
4. [x] ws_get_events fallback bez start_time/end_time
5. [ ] **Dokumentacja** – events_media_type w README / TROUBLESHOOTING
6. [ ] **Karta ACC** – domyślne `snapshots` dla QVR (opcjonalnie)
7. [ ] Test E2E – timeline z eventami widocznymi (manual)
