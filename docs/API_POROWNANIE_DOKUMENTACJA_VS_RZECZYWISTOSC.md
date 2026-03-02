# Porównanie: Nasza dokumentacja API vs rzeczywiste QVR API

**Zasada:** QVR API to my się do niego stosujemy, nie on do nas.

---

## Źródła „prawdziwego” API

1. **pyqvrpro** (oblogic7) – fixtures z 2019, VCR cassettes – to co testowali
2. **QVR Developer Portal** (QNAP) – Open Video I/O, Event I/O, Metadata Platform – ogólne, bez specyfikacji endpointów
3. **QVR API ver 1.1.0** – parametr `ver` w zapytaniach; brak oficjalnego Swagger
4. **Reverse engineering** – probe (`tools/qvr_api_probe.py`) – testuje wszystkie możliwości

---

## Co pokrywa nasza dokumentacja vs rzeczywistość

### Endpointy z pyqvrpro (zweryfikowane)

| Endpoint | pyqvrpro | qvr_api | Uwagi |
|---------|----------|---------|-------|
| auth | ✅ | ✅ | authLogin.cgi, sid |
| qvrentry | – | ✅ | Discovery path |
| channels | ✅ | ✅ | qshare/StreamingOutput/channels |
| channel streams | ✅ | ✅ | channel/{guid}/streams |
| liveStream | ✅ | ✅ | POST, protocol |
| camera/list | ✅ | ✅ | guid opcjonalny |
| camera/capability | act=get_camera_capability | ✅ | ptz=0/1, act=* |
| camera/capability | act=get_event_capability | ✅ | IVA types |
| camera/snapshot | ✅ | ✅ | JPEG |
| mrec start/stop | ✅ | ✅ | PUT |
| logs/logs | ❌ | ✅ | My dodaliśmy |

### Endpointy z naszego probe (kandydaci)

| Endpoint | Opis | 200 vs 404 |
|----------|------|------------|
| camera/recording/{guid} | Lista nagrań | Zależy od produktu |
| camera/recordings | Lista wszystkich | Często 404 |
| camera/events | Eventy | Często 404 |
| event | Open Event Platform | Często 404 |
| metadata | Metadata Platform | Często 404 |
| metadata/search | Wyszukiwanie metadanych | Nieznane |
| metadata/list | Lista metadanych | Nieznane |
| qshare/RecordingOutput | Alternatywa recording | Często 404 |

### Parametry – nasza vs QVR

| Funkcja | Nasza dokumentacja | Rzeczywistość |
|---------|-------------------|---------------|
| get_recording | time, time_ms, start_time/end_time | ✅ Zgodne |
| get_recording_list | guid | + start_time, end_time (obsługujemy) |
| get_logs | log_type 1–5, level, global_channel_id | ✅ Zgodne z probe |
| capability | ptz, act | act=list, get_features, get_ptz – może 404 |

---

## Metadane – rozbieżność

- **QVR Metadata Platform** (dokumentacja) – Data Sources, Metadata Vault, wyszukiwanie w nagraniach
- **API `/metadata`** – nie udokumentowany w QVR API 1.1.0, często 404
- **metadata w logach/eventach** – pole `metadata` w wpisie (np. `event_name`, LPR) – **to używamy** w converters

Szczegóły: `docs/METADATA_PLATFORM.md`

---

## Podsumowanie

- Wszystkie endpointy z pyqvrpro – obsługiwane, plus logi.
- Probe testuje wszystkie warianty – capability, recording, event, metadata – część 404 to norma.
- Dokumentacja nie przeczy QVR – odzwierciedla reverse engineering i oficjalne opisy QNAP.
- Gdy endpoint 404 – nie używamy. Gdy 200 – konwerter mapuje na ACC.
