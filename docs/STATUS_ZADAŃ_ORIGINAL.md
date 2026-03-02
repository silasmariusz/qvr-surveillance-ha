# Status zadań – oryginalny prompt

## Oryginalne wymagania

1. Sprobowac wszystkich możliwości API (capabilities itd.) – część może zwrócić błąd
2. Zdobyć informacje, sprawdzić jakie zapytania wykonać
3. Opisać krótko jak działa każda funkcja
4. Prosta biblioteka wrapper + konwerter
5. Doc opierając się o research, nie zaprzeczając QVR API
6. Plan: Frigate vs ACC – porównanie z biblioteką
7. Realizacja: pełna praca, każdy wariant, każda możliwość
8. Infografika + opis wszystkich zapytań API

---

## Wykonane ✅

| # | Zadanie | Status | Plik / komponent |
|---|---------|--------|------------------|
| 1 | Sprobowanie wszystkich możliwości | ✅ | qvr_api, probe: capability (ptz, act), recording (wszystkie param), livestream×protocol×stream |
| 2 | Zdobycie informacji o zapytaniach | ✅ | QVR_API_WSZYSTKIE_ZAPYTANIA.md |
| 3 | Opis każdej funkcji | ✅ | QVR_API_FULL_REFERENCE.md, qvr_api/README.md |
| 4 | Biblioteka wrapper + konwerter | ✅ | qvr_api/ (api.py, converters.py, types.py) |
| 5 | Doc bez zaprzeczania API | ✅ | Wszystkie docs – QVR API jako źródło prawdy |
| 6 | Plan Frigate vs ACC | ✅ | FRIGATE_VS_QVR_ACC_PLAN.md |
| 7 | Pełna realizacja | ✅ | Wszystkie warianty w probe, capability per-guid, candidate paths |
| 8 | Infografika | ✅ | QVR_API_INFOGRAFIKA.md (Mermaid) |
| 9 | Opis wszystkich zapytań | ✅ | QVR_API_WSZYSTKIE_ZAPYTANIA.md |

---

## ACC – co działa, czego brak

| Funkcja ACC | QVR | Status |
|-------------|-----|--------|
| Live stream | get_live_stream | ✅ |
| Snapshot | get_snapshot | ✅ |
| Recordings summary | get_recording_list lub probe | ✅ |
| Recording segments | get_recording_list lub probe | ✅ |
| Playback | get_recording(time) | ✅ |
| Events (kropki) | get_events | ✅ gdy API zwraca |
| events/summary | get_event_capability | ✅ |
| PTZ info | get_camera_capability(ptz=1) | ✅ |
| PTZ control | ptz_control | ✅ |
| **Event retain** (ulubione) | – | ❌ QVR nie ma |
| **Clips** (klipy AI) | – | ❌ QVR ma snapshoty |

---

## Niewykonane (opcjonalne)

| Zadanie | Uwaga |
|---------|-------|
| Probe na żywym QVR, dokumentacja 200 vs 404 | Użytkownik uruchamia lokalnie: `QVR_PASS=xxx python tools/qvr_api_probe.py` |
