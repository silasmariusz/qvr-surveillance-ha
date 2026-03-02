# Jakość streamu i problemy z ładowaniem

## Tak – to stream RTSP

Integracja QVR Surveillance dostarcza **RTSP** jako `stream_source`. Home Assistant pobiera URL z `get_channel_live_stream(guid, stream=0, protocol="rtsp")` i przekazuje go do komponentu stream (go2rtc / FFmpeg).

- **Main (0)** – pełna rozdzielczość
- **Sub (1)** – niższa rozdzielczość (substream)
- **Mobile (2)** – najniższa jakość

---

## Możliwe przyczyny fatalnej jakości

### 1. Karta używa **snapshot** zamiast streamu

Karty typu „Podgląd obrazu” / Picture z **Encją kamery** mogą korzystać z `camera_image` (snapshot) zamiast live streamu. Snapshot z API QVR (`/camera/snapshot/{guid}`) często jest:
- niskiej rozdzielczości (domyślna z kamery/QVR),
- bez parametrów `width`/`height` – API może nie obsługiwać ich lub zwracać mały obraz.

**Sprawdzenie:** Jeśli obraz odświeża się co kilka sekund zamiast płynnego streamu – prawdopodobnie używany jest snapshot.

### 2. Sub stream zamiast Main

Jeśli wybrana encja to np. **QVR Surveillance Camera 001 Sub** – to substream (niższa jakość). Użyj encji bez „Sub” w nazwie dla lepszej jakości.

### 3. Transkodowanie po stronie Home Assistant

HA używa go2rtc/FFmpeg do RTSP → HLS/WebRTC dla przeglądarki. Może to:
- obniżać jakość (kompresja),
- powodować opóźnienia,
- zwiększać obciążenie CPU.

### 4. Ustawienia kamery w QVR

W QVR Pro: ustawienia Main stream (rozdzielczość, bitrate, codec) wpływają na jakość. Sprawdź konfigurację kanału w QVR.

### 5. Sieć i wydajność

- Wolna sieć między HA a QVR,
- Ograniczona przepustowość WiFi,
- Słaby NAS/QVR (CPU przy wielu streamach).

---

## Możliwe przyczyny problemów z ładowaniem

### 1. Wygasające sesje RTSP

QVR generuje URL RTSP z ograniczonym czasem życia. Integracja odświeża URL przy każdym `stream_source()`, ale:
- przy błędzie odświeżania używany jest stary URL,
- przy opóźnieniach po stronie HA stary URL może być już nieważny.

### 2. `resourceUris` jako lista

API QVR może zwracać `resourceUris` jako tablicę. Jeśli parser oczekuje stringa, zwracany jest `None` → stream się nie ładuje.

### 3. Autoryzacja RTSP

URL zawiera `user:password@`. Hasła ze znakami `:`, `@` mogą być niepoprawnie wstrzykiwane do URL. Należy używać URL-encoding.

### 4. Brak go2rtc / problemy z FFmpeg

Bez go2rtc HA używa FFmpeg. Sprawdź, czy go2rtc jest zainstalowany (Add-on) i czy kamery są tam widoczne.

### 5. Limit połączeń QVR

QVR może limitować równoczesne połączenia RTSP. Zbyt wiele kart/kamer na raz może powodować timeouty.

---

## Zalecenia

1. **Używaj karty, która pokazuje live stream** – np. Picture Entity z widokiem „live” lub WebRTC Camera Card (HA 2024.11+).
2. **Main zamiast Sub** – wybieraj encję bez „Sub”.
3. **go2rtc** – rozważ dodatek go2rtc dla lepszej jakości i mniejszego opóźnienia (WebRTC).
4. **Sprawdź ustawienia QVR** – rozdzielczość i bitrate Main stream.

---

## Wprowadzone poprawki (v1.12+)

- [x] Obsługa `resourceUris` w formacie tablicy (pierwszy element) oraz `resourceUri`
- [x] URL-encoding credentials (`get_auth_string_for_url`) – hasła z `:`, `@` nie łamią URL

## Planowane poprawki

- [ ] Opcjonalne parametry `width`/`height` dla snapshot (jeśli API QVR je obsługuje)
- [ ] Retry przy wygasłej sesji streamu
- [ ] Opcja `frontend_stream_type` dla WebRTC (HA 2024.11+)
