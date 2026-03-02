# Porównanie streamu: pyqvrpro (QVR Pro) vs qvr_surveillance

## Odpowiedź: Tak, używamy tej samej metody

Obie integracje dostarczają stream **identycznie** – encja `Camera` z metodą `stream_source()` zwracającą URL RTSP z API QVR.

---

## HA 2025.06+ – wymagania dla streamu

Od Home Assistant 2025 integracja kamery **musi** zadeklarować `CameraEntityFeature.STREAM`, inaczej stream **nie zostanie utworzony** – kamera będzie działać tylko ze snapshotami (entity_picture, MJPEG ze zdjęć).

**Co robi HA:**
- Sprawdza `CameraEntityFeature.STREAM in camera.supported_features`
- Tylko wtedy wywołuje `async_create_stream()` → `stream_source()` → `create_stream(hass, source, options)`
- Stream component (PyAV) łączy się z RTSP, konwertuje do HLS (lub WebRTC przez go2rtc)

**qvr_surveillance:** Ustawia `_attr_supported_features = CameraEntityFeature.STREAM` – stream jest tworzony i działa.

**pyqvrpro:** Należy zweryfikować – stary kod mógł nie dodawać tej flagi (w starszych HA mogło działać inaczej).

**Deprecacje 2024.11–2025.6:** `frontend_stream_type`, `async_handle_web_rtc_offer` → `async_handle_async_webrtc_offer`, `async_register_rtsp_to_web_rtc_provider` → `async_register_webrtc_provider`. Integracje z natywnym RTSP (stream_source) nie muszą tego implementować – HA używa go2rtc jako provider WebRTC.

---

## API QVR – skąd bierze się RTSP

Endpoint: `POST /qvrpro/qshare/StreamingOutput/channel/{guid}/stream/{stream}/liveStream`

Body: `{"protocol": "rtsp"}` (lub `"hls"` – pyqvrpro domyślnie ma `hls`, ale HA QVR Pro jawnie ustawia `rtsp`)

Odpowiedź: `{"resourceUris": "rtsp://host:port/channel1", ...}`

URL RTSP ma ograniczony czas życia – sesje QVR wygasają.

---

## HA QVR Pro (pyqvrpro) – jak to robi

Źródło: `homeassistant/components/qvr_pro/camera.py`

```python
def get_stream_source(guid, client):
    resp = client.get_channel_live_stream(guid, protocol="rtsp")
    full_url = resp["resourceUris"]  # zakłada string, nie listę
    auth = f"{client.get_auth_string()}@"
    return f"{protocol}{auth}{url}"

# W stream_source():
async def stream_source(self):
    return self._stream_source   # ZAWSZE cache z setup – NIE odświeża!
```

- `get_stream_source()` wywoływane **raz** przy starcie integracji.
- `stream_source()` zwraca **statyczny** URL zapisany przy inicjalizacji.
- Brak obsługi `resourceUris` w formacie listy.
- Brak URL-encoding credentials (może się wysypać przy `:`, `@` w haśle).
- **Problem:** Gdy URL QVR wygaśnie, stream przestaje działać aż do restartu HA.

---

## qvr_surveillance – jak to robimy

```python
def _get_stream_source(guid, client, stream=0):
    resp = client.get_channel_live_stream(guid, stream=stream, protocol="rtsp")
    raw = resp.get("resourceUris") or resp.get("resourceUri")
    full_url = raw[0] if isinstance(raw, list) else raw  # obsługa listy
    auth = f"{client.get_auth_string_for_url()}@"  # URL-encoding
    return f"{protocol}{auth}{url}"

# W stream_source():
async def stream_source(self):
    new_src = await hass.async_add_executor_job(_get_stream_source, ...)
    if new_src:
        self._stream_source = new_src
    return self._stream_source   # Odświeża przy KAŻDYM żądaniu
```

- `stream_source()` przy każdym żądaniu **odświeża** URL z API.
- Obsługa `resourceUris` jako string lub lista.
- `get_auth_string_for_url()` – poprawne kodowanie credentials.
- **Efekt:** Działa również po wygaśnięciu sesji – kolejne odtworzenie pobiera nowy URL.

---

## Pipeline HA (2025+) – czy RTSP jest „mountowany” na FFmpeg?

**Tak.** Przepływ wygląda tak:

1. Frontend prosi o stream kamery (`camera/stream` websocket, lub odtworzenie live).
2. Backend sprawdza `CameraEntityFeature.STREAM in supported_features` – **bez tego stream nie startuje**.
3. Wywołuje `camera.async_create_stream()` → wewnętrznie `stream_source()` → dostaje URL RTSP.
4. `create_stream(hass, source, stream_options)` tworzy obiekt **Stream**.
5. Komponent **stream** uruchamia worker z **PyAV**, który:
   - łączy się z RTSP (domyślnie `rtsp_flags: prefer_tcp`, `stimeout: 5000000`),
   - dekoduje i pakuje do HLS (LL-HLS).
6. Przy włączonym **go2rtc** – dodatkowo WebRTC (mniejsza latencja).
7. Przeglądarka odtwarza HLS lub WebRTC (RTSP nie jest obsługiwany natywnie).

Źródło: `homeassistant/components/camera/__init__.py`, `homeassistant/components/stream/__init__.py`.

FFmpeg/PyAV **dostaje** nasz RTSP. Konwersja RTSP → HLS odbywa się wewnątrz HA i to ona może wpływać na jakość i opóźnienia. Zarówno pyqvrpro, jak i qvr_surveillance trafiają do tego samego pipeline’u.

---

## Różnice podsumowanie

| Aspekt | pyqvrpro (HA QVR Pro) | qvr_surveillance |
|--------|------------------------|------------------|
| API | `get_channel_live_stream(guid, protocol="rtsp")` | To samo |
| Źródło URL | `resourceUris` (string) | `resourceUris` / `resourceUri`, string lub lista |
| Odświeżanie URL | Nie – cache z setup | Tak – przy każdym `stream_source()` |
| Auth w URL | `user:password` (bez encoding) | `get_auth_string_for_url()` (z encoding) |
| `CameraEntityFeature.STREAM` | Do weryfikacji (stary kod) | ✅ Zawsze ustawione |
| Pipeline HA | Stream → PyAV → HLS (+ go2rtc WebRTC) | Identyczny |
| Jakość | Zależna od transkodowania HA | Identyczna |

---

## Wniosek

- **API QVR zwraca RTSP** – używamy go poprawnie.
- **Sposób działania jest taki sam** jak w oficjalnym QVR Pro (stream_source + pipeline HA).
- **Jakość zależy od transkodowania HA** (RTSP → HLS/WebRTC), nie od sposobu pobrania URL.
- **Nasz kod jest lepiej przygotowany** na wygasłe sesje i niestandardowe odpowiedzi API.

Lepsza jakość bez transkodowania HA wymaga obejścia – np. **Expose Camera Stream Source + go2rtc**, zamiast zmiany w samej integracji.
