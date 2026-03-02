# Konfiguracja kamer QVR w Advanced Camera Card

Pełna konfiguracja zapewniająca: stream na żywo, eventy na timeline, nagrania, przełącznik Main/Sub.

**Plan napraw i troubleshooting:** `docs/PLAN_QVR_ACC_FIXES.md`

---

## 0. Auto client_id (można pominąć)

ACC automatycznie pobiera `client_id` z atrybutu encji `qvr_client_id`. Jeśli integracja jest poprawnie skonfigurowana, **nie musisz** wpisywać `qvr_surveillance.client_id` w karcie – działa jak kamera ONVIF (wybierz encję i gotowe).

---

## 1. Konfiguracja integracji (configuration.yaml)

```yaml
qvr_surveillance:
  host: 10.100.200.10
  username: admin
  password: "hasło"
  port: 38080
  client_id: qvr_surveillance
  add_substream: true
  event_scan_interval: 15
```

---

## 2. Karta – minimalna (auto‑detekcja)

Karta wykrywa silnik QVR po `platform: qvr_surveillance` encji kamery.

```yaml
type: custom:advanced-camera-card
cameras:
  - camera_entity: camera.qvr_surveillance_wjazd
```

---

## 3. Karta – zalecana (pełna)

```yaml
type: custom:advanced-camera-card
cameras:
  # Kamera Main (pełna rozdzielczość)
  - camera_entity: camera.qvr_surveillance_wjazd
    engine: qvr_surveillance
    qvr_surveillance:
      client_id: qvr_surveillance
      # channel_guid: AECCAF1253E8   # opcjonalnie, auto z atrybutu
    live_provider: ha
    dependencies:
      cameras: [camera.qvr_surveillance_wjazd_sub]
    timeline:
      events_media_type: all
  # Sub (opcjonalnie jako osobna karta do przełącznika)
  - camera_entity: camera.qvr_surveillance_wjazd_sub
    engine: qvr_surveillance
    qvr_surveillance:
      client_id: qvr_surveillance
    live_provider: ha

# Timeline – eventy + nagrania
timeline:
  events_media_type: all
  show_recordings: true
  window_seconds: 3600
```

---

## 4. Kluczowe ustawienia

| Parametr | Wartość | Znaczenie |
|----------|---------|-----------|
| `engine` | `qvr_surveillance` | Silnik QVR (auto przy encji z platform qvr_surveillance) |
| `qvr_surveillance.client_id` | `qvr_surveillance` | Opcjonalnie – auto z atrybutu encji |
| `live_provider` | `ha` lub `auto` | Stream RTSP przez HA (nie `image` = snapshots) |
| `timeline.events_media_type` | `all` lub `snapshots` | Pokazuje eventy QVR na osi czasu |
| `dependencies.cameras` | `[camera.xxx_sub]` | Przycisk Main/Sub (tablica stringów!) |

### Błąd „cameras[0] → dependencies → cameras”

ACC wymaga, żeby `dependencies.cameras` było **tablicą** entity_id:
```yaml
dependencies:
  all_cameras: false
  cameras:
    - camera.qvr_surveillance_camera_001_sub
```
**Nie** pojedynczy string: `cameras: camera.xxx_sub` ❌

Jeśli błąd dalej występuje – **usuń** blok `dependencies` (stracisz przycisk Main/Sub, reszta działa).

---

## 5. Czego unikać

| Unikaj | Powód |
|--------|-------|
| `live_provider: image` | Tylko snapshots, brak streamu |
| `timeline.events_media_type: clips` | Eventy QVR to snapshoty – nie będą widoczne |
| Profil `low-performance` | Ustawia `live_provider: image` dla wszystkich kamer |
| Kamery Sub bez `dependencies` | Brak przycisku przełącznika Main/Sub |
| `client_id` inny niż w integracji | Timeline/recordings nie znajdą danych |

---

## 6. Weryfikacja

1. **DevTools → States** – encja kamery ma atrybuty `qvr_guid`, `qvr_client_id`
2. **Timeline** – po otwarciu widoku timeline pojawiają się eventy (jeśli IVA w QVR jest włączone)
3. **Stream** – płynny obraz, nie odświeżane snapshoty
4. **Logi** – `events/get ... raw_logs=N events=M` – N,M>0 przy eventach

---

## 7. HEVC / encoded 0 frames – użyj Sub

Main stream QVR często używa HEVC. go2rtc może zwracać `encoded 0 frames`. **Rozwiązanie:** W ACC użyj encji Sub zamiast Main: `camera_entity: camera.qvr_surveillance_camera_001_sub` (Sub zwykle H.264).

## 8. Minimalna konfiguracja (bez dependencies)

```yaml
type: custom:advanced-camera-card
cameras:
  - camera_entity: camera.qvr_surveillance_camera_001
    engine: qvr_surveillance
    live_provider: ha
timeline:
  events_media_type: all
  show_recordings: true
```

## 9. Przykład z kilkoma kamerami

```yaml
type: custom:advanced-camera-card
cameras:
  - camera_entity: camera.qvr_surveillance_wjazd
    engine: qvr_surveillance
    qvr_surveillance:
      client_id: qvr_surveillance
    live_provider: ha
    dependencies:
      cameras: [camera.qvr_surveillance_wjazd_sub]
  - camera_entity: camera.qvr_surveillance_garaz
    engine: qvr_surveillance
    qvr_surveillance:
      client_id: qvr_surveillance
    live_provider: ha
    dependencies:
      cameras: [camera.qvr_surveillance_garaz_sub]

timeline:
  events_media_type: all
  show_recordings: true
```
