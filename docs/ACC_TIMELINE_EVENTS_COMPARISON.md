# Timeline events: koncepcja ACC vs Frigate vs QVR Surveillance

## CRITICAL: get_logs ≠ surveillance events

**`get_logs()` returns application/operational LOGS**, NOT timeline events. Logs are for QVR app auditing:
- log_type 1: Surveillance **Settings** (config changes)
- 2: Surveillance **Events** (app-level event log)
- 3: Surveillance **Connection** (connect/disconnect)
- 4/5: System events/connection

**Real timeline source:** Browse **available recordings** – continuous or event-triggered (motion, IVA, line crossing). Recording start/end time = segment on timeline. `events/get` uses get_events() from API only; logs are for HA sensors, NOT timeline.

---

## 1. Koncepcja Advanced Camera Card – źródło eventów na timeline

### Architektura

ACC nigdy nie komunikuje się bezpośrednio z backendem (Frigate, QVR itd.). Cała komunikacja odbywa się przez **WebSocket Home Assistant** (`hass.callWS`).

```
[Advanced Camera Card]
    ↓ hass.callWS({ type: '…/events/get', ... })
[Home Assistant]
    ↓ integracja rejestruje handler WebSocket
[Integracja (Frigate / qvr_surveillance)]
    ↓ wywołuje backend
[Backend (Frigate / QVR Pro)]
```

### Interfejs engine’a – co musi dostarczyć timeline

Każdy **engine** (Frigate, QVRSurveillance, Generic, itd.) implementuje interfejs `CameraManagerEngine` i musi realizować m.in.:

| Metoda | Rola | Użycie na timeline |
|-------|------|--------------------|
| `generateDefaultEventQuery()` | Buduje zapytanie o eventy dla okna czasowego | Timeline określa `start`, `end`, filtr `hasClip`/`hasSnapshot` |
| `getEvents()` | Pobiera eventy z backendu | Wywoływane z oknem czasowym (np. ostatnie 2 h) |
| `generateMediaFromEvents()` | Zamienia surowe eventy na `ViewMedia[]` | Każdy event staje się elementem na timeline |

### Przepływ danych dla timeline

1. **TimelineDataSource** (w `source.ts`):
   - Określa widoczne okno timeline (start, end)
   - Buduje `EventQuery` przez `getTimelineEventQueries()` → `cameraManager.generateDefaultEventQueries()`
   - Wywołuje `cameraManager.executeMediaQueries(eventQueries)`
   - `executeMediaQueries` → `engine.getEvents()` → `engine.generateMediaFromEvents()`
   - Wynik to `ViewMedia[]` (EventViewMedia), mapowane na elementy timeline

2. **Recordings (słupki)** – osobny flow:
   - `getRecordingSegments()` – segmenty nagrań dla okna
   - `recordings/summary` – podsumowanie godzin z nagraniami
   - QVR: get_recording_list z API; [] gdy brak (API nie ma list-by-date)

3. **Odświeżanie**:
   - Przy zmianie okna (pan/zoom)
   - Okresowo co ~1 min, gdy okno obejmuje „teraz”
   - Cache eventów: 30 s (source), 60 s (QVR engine)

---

## 2. Frigate – jak dostarcza eventy do ACC

### API Frigate (poprzez integrację HA)

Integracja Frigate rejestruje handlery WebSocket, np.:

- `frigate/events/get` – lista eventów
- `frigate/events/summary` – metadane do filtrów (labels, zones, days)
- `frigate/recordings/summary` – godziny z nagraniami
- `frigate/recordings/get` – segmenty nagrań

### Struktura eventu Frigate (`FrigateEvent`)

```ts
{
  camera: string,
  id: string,
  start_time: number,    // Unix sekundy
  end_time: number | null,
  has_clip: boolean,
  has_snapshot: boolean,
  label: string,         // np. "person", "car" – AI
  sub_label: string | null,
  zones: string[],       // np. ["front_door"]
  top_score: number | null,
  retain_indefinitely?: boolean
}
```

### Charakterystyka

- Źródło: **Frigate** – NVR z detekcją AI (COCO labels, strefy)
- Eventy: **clips (mp4)** i **snapshots (jpg)** – każdy event ma `has_clip` / `has_snapshot`
- Zakres czasowy: backend obsługuje `after`, `before` (Unix sec)
- Filtrowanie: `labels`, `zones`, `has_clip`, `has_snapshot`, `favorites`
- Real-time: **FrigateEventWatcher** – subskrypcja MQTT (`frigate/events/subscribe`) → push nowych eventów
- Recordings: API zwraca rzeczywiste godziny z nagraniami; segmenty z backendu

---

## 3. QVR Surveillance – stan obecny

### API QVR (WebSocket qvr_surveillance)

- `qvr_surveillance/events/get` – get_events() z API; logi dla sensorów HA, nie timeline
- `qvr_surveillance/recordings/summary` – get_recording_list z API; [] gdy brak
- `qvr_surveillance/recordings/get` – get_recording_list z czasem; [] gdy brak

### Źródło eventów

QVR: `get_events()` z API (może 404). Logi (`get_logs`) są dla sensorów HA, nie dla timeline. Źródło timeline: recordings – czas nagrania = segment.

### Struktura eventu QVR (po mapowaniu)

```python
{
  "id": str,
  "time": int,      # Unix sekundy
  "message": str,
  "type": str       # np. "alarm_pir", "surveillance", z EVENT_TYPES
}
```

Brak: `end_time`, `has_clip`, `has_snapshot` – QVR zwraca głównie snapshoty zdarzeń, nie klipy wideo.

### Ograniczenia QVR API

1. **Brak „events by date range”** – `get_events() może 404; logi dla sensorów, nie timeline 2. **Brak listy nagrań po dacie** – get_recording_list może 404; zwracamy [].
3. **Clips: false** – QVR zwraca snapshoty, nie klipy wideo; `events_media_type: clips` daje pustą listę.
4. **Event = punkt w czasie** – brak `end_time`, ACC traktuje jako punkt (np. `getUsableEndTime()` → start).

---

## 4. Porównanie: Frigate vs QVR (założenia)

| Aspekt | Frigate | QVR Surveillance |
|--------|---------|------------------|
| Źródło eventów | Frigate API (eventy AI) | Workaround: get_logs (LOGS!). Właściwie: recordings |
| Zakres czasowy | Backend obsługuje `after`/`before` | Często ignorowane przez QVR |
| Clip vs Snapshot | Oba (`has_clip`, `has_snapshot`) | Tylko snapshots |
| Struktura eventu | `start_time`, `end_time`, label, zones | `time` (punkt), `message`, `type` |
| Recordings | Rzeczywiste z Frigate | Syntetyczne 24/7 |
| Real-time push | MQTT (FrigateEventWatcher) | Brak – tylko polling |
| Filtr `events_media_type` | `all` / `clips` / `snapshots` | `all` lub `snapshots` (clips nie działa) |

---

## 5. Czy to może działać?

### Tak – przy ograniczeniach

1. **Timeline eventy**:
   - ACC wymaga: `id`, `time` (Unix sec), opcjonalnie `message`, `type`.
   - QVR dostarcza to przez mapowanie logów → eventów.
   - `events_media_type: all` lub `snapshots` – eventy się wyświetlają (50/50 w logach).
   - `events_media_type: clips` – puste, bo QVR nie ma klipów.

2. **Okno czasowe**:
   - Jeśli QVR respektuje `start_time`/`end_time` – działa poprawnie.
   - Jeśli nie – logi pokazują retry bez filtra; wtedy eventy z całego zakresu, ale timeline nadal je pokazuje.

3. **Recordings (słupki)**:
   - Syntetyczne 24/7 – timeline zakłada nagrania ciągłe.
   - Rzeczywiste przerwy w nagrywaniu nie są widoczne.

4. **Odświeżanie**:
   - Polling co ~1 min (gdy okno „live”) – nowe logi pojawią się na timeline.
   - Brak push (jak MQTT w Frigate) – opóźnienie do ~1 min.

5. **Thumbnails eventów**:
   - QVR: `getEventSnapshotContentID` → `media-source://qvr_surveillance/snapshot/...` lub proxy.
   - Działa, jeśli media_source i proxy są poprawnie skonfigurowane.

### Ryzyka

- QVR może zwracać logi bez filtra czasu → większy transfer, wolniejsze zapytania.
- Brak `end_time` → eventy jako punkty; seek w recording może być mniej precyzyjny.
- Brak klipów → galeria „Clips” nie działa (oczekiwane).

---

## 6. Podsumowanie

| Pytanie | Odpowiedź |
|---------|-----------|
| Co jest źródłem eventów w ACC? | Engine wywołuje `getEvents()` → integracja → WebSocket (`…/events/get`) → backend |
| Skąd Frigate ma eventy? | Frigate API – AI (COCO), clipy + snapshoty, `after`/`before` |
| Skąd QVR ma eventy? | get_events() z API; logi dla sensorów. Timeline z recordings |
| Czy może działać? | Tak – z `events_media_type: all` lub `snapshots`, polling co 1 min dla live |
| Główne różnice | Frigate: AI, clipy, push. QVR: logi IVA, snapshoty, brak push |
