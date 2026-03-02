# Jakość streamu i problemy z ładowaniem

## Tak – to stream RTSP (ta sama metoda co pyqvrpro)

Integracja QVR Surveillance dostarcza **RTSP** jako `stream_source` – dokładnie tak samo jak oficjalna integracja QVR Pro (pyqvrpro). API QVR zwraca link RTSP, HA przekazuje go do FFmpeg/stream component, który konwertuje RTSP → HLS (lub WebRTC przez go2rtc). Porównanie z pyqvrpro: `docs/PYQVRPRO_STREAM_COMPARISON.md`.

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

**Diagnostyka RTSP 400:** 1) Pobierz URL: `curl -H "Authorization: Bearer $TOKEN" http://supervisor/core/api/camera_stream_source/camera.xxx` (TOKEN z Supervisor). 2) Test w VLC: Otwórz sieć → URL. 3) Jeśli VLC działa a HA nie – problem w stream component (FFmpeg/go2rtc). 4) QVR: sprawdź limity połączeń w ustawieniach.

### 6. „Podgląd widoku z kamery” (preload stream) – obraz 1–2 s, potem błąd

W ustawieniach encji kamery w HA (Ustawienia → Urządzenia i usługi → Kamery → kamera → opcje) włączona jest opcja **„Podgląd widoku z kamery”** – powoduje ciągłą transmisję streamu w tle dla szybszego dostępu. **To znacząco obciąża urządzenie.**

Przy wielu kamerach QVR: **preload × liczba kamer (Main+Sub)** = równoczesne połączenia RTSP.
- HA uruchamia równolegle wiele workerów PyAV (RTSP → HLS)
- QVR może ograniczać równoczesne połączenia RTSP
- Efekt: stream startuje na 1–2 s, potem 400 Bad Request lub timeout

**Zalecenie:** Wyłącz „Podgląd widoku z kamery” dla kamer QVR. Obraz załaduje się dopiero po otwarciu karty – dłużej, ale stabilniej.

**Jak wyłączyć:** Ustawienia → Urządzenia i usługi → [urządzenie QVR] → [encja kamery] → Konfiguracja encji → „Podgląd widoku z kamery" = Wyłączone.

---

## Advanced Camera Card – live_provider

Karta Advanced Camera Card ma parametr `live_provider`:
- **`ha`** (domyślne przy `camera_entity`) = stream RTSP→HLS ✅
- **`image`** = odświeżane snapshots – niska jakość, wygląda jak „slajdy” ❌

**Profil low-performance** ustawia `cameras_global.live_provider: image` – wtedy **wszystkie** kamery (w tym QVR) pokazują snapshots zamiast streamu.

Sprawdź w edytorze karty: Camera → Live provider = `Auto` lub `ha`, nie `image`.  
Szczegóły: `docs/ADVANCED_CAMERA_CARD_VERIFICATION.md`.

## Dlaczego stream HA (HLS/WebRTC) jest gorszy od RTSP

**Strumień HA transkoduje RTSP → HLS** (lub WebRTC przez go2rtc). To powoduje:
- Gorszą jakość niż bezpośredni RTSP z kamery,
- Opóźnienia (5–15 s),
- Problemy z odtwarzaniem na wszystkich kamerach.

Nie rozwiązuje tego wybór „Video stream Home Assistant”, WebRTC ani „Automatyczny” – wszystkie idą przez pipeline HA.

---

## Rozwiązanie: RTSP → go2rtc (omijając transkodowanie HA)

Aby uzyskać jakość zbliżoną do bezpośredniego RTSP:

### 1. Zainstaluj Expose Camera Stream Source (HACS)

Integracja [hass-expose-camera-stream-source](https://github.com/felipecrs/hass-expose-camera-stream-source) udostępnia API z URL RTSP z encji. go2rtc może z niego korzystać i przy każdym połączeniu pobierać świeży URL (ważne, bo adresy QVR wygasają).

### 2. Dodaj kamery QVR do go2rtc

W konfiguracji go2rtc (np. `config/go2rtc.yaml` lub w UI dodatku):

```yaml
streams:
  qvr_1:
    - 'echo:curl -fsSL http://supervisor/core/api/camera_stream_source/camera.qvr_surveillance_1 -H "Authorization: Bearer ${SUPERVISOR_TOKEN}"'
  qvr_2:
    - 'echo:curl -fsSL http://supervisor/core/api/camera_stream_source/camera.qvr_surveillance_2 -H "Authorization: Bearer ${SUPERVISOR_TOKEN}"'
```

Zamień `camera.qvr_surveillance_1` na faktyczny `entity_id` (bez „ Sub” – Main stream).

### 3. Użyj go2rtc w karcie

W Advanced Camera Card:

```yaml
cameras:
  - camera_entity: camera.qvr_surveillance_1
    live_provider: go2rtc
    go2rtc:
      stream: qvr_1   # nazwa z streams w go2rtc
```

### 4. Weryfikacja

Przed konfiguracją go2rtc sprawdź, czy API zwraca RTSP:

```bash
curl -fsSL http://supervisor/core/api/camera_stream_source/camera.qvr_surveillance_1 -H "Authorization: Bearer ${SUPERVISOR_TOKEN}"
```

Powinna pojawić się odpowiedź typu `rtsp://...`. Jeśli brak – integracja Expose Camera Stream Source musi być włączona i działać dla tej encji.

---

## Zalecenia

1. **RTSP → go2rtc** – najlepsza jakość i niskie opóźnienie, omija transkodowanie HA.
2. **Main zamiast Sub** – encja bez „Sub” w nazwie.
3. **Sprawdź ustawienia QVR** – rozdzielczość i bitrate Main stream.

---

## Wprowadzone poprawki (v1.12.2+)

- [x] Obsługa `resourceUris` w formacie tablicy (pierwszy element) oraz `resourceUri`
- [x] URL-encoding credentials (`get_auth_string_for_url`) – hasła z `:`, `@` nie łamią URL
- [x] `CameraEntityFeature.STREAM` – wymagane w HA 2025+; bez tego stream nie startuje (tylko snapshoty)
- [x] **Odświeżanie RTSP przy błędzie** – gdy stream.available=False, pobieramy nowy URL i update_source(); worker restartuje z aktualną sesją QVR (naprawa: 1–2 s dobrej jakości → błąd)

## Planowane poprawki

- [ ] Opcjonalne parametry `width`/`height` dla snapshot (jeśli API QVR je obsługuje)
- [ ] Retry przy wygasłej sesji streamu
- [ ] Opcja `frontend_stream_type` dla WebRTC (HA 2024.11+)
