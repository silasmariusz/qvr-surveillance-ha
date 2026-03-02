# QVR Camera Capabilities – Pełna Referencja

Dokument opisuje **każde zapytanie** do endpointu `/camera/capability` QVR API. Biblioteka `qvr_api` oraz `tools/qvr_api_probe.py` testują wszystkie warianty. Część może zwracać 404 – normalne, nie wszystkie produkty QVR wspierają wszystko.

**Zasada:** QVR API to my się do niego stosujemy, nie on do nas.

---

## Endpoint bazowy

```
GET {qvr_path}/camera/capability
```

Parametry: `sid` (wymagany), `ver` (wymagany), oraz opcjonalne poniżej.

---

## Warianty zapytań (pełna macierz)

### 1. Bez `act` – capability podstawowe / PTZ

| Funkcja | Parametry | Opis | Zwraca | Uwagi |
|---------|-----------|------|--------|-------|
| `get_camera_capability(guid=None, ptz=0)` | ptz=0 | Capability podstawowe (domyślne) | Dict z możliwościami kamery | QVR Pro/Elite |
| `get_camera_capability(guid=None, ptz=1)` | ptz=1 | Presety PTZ, lista punktów | PTZ presets, action_list | Wymagane dla ACC PTZ info |
| `get_camera_capability(guid=X, ptz=0)` | guid, ptz=0 | Capability dla jednej kamery | Jak wyżej, per kamera | Może 404 gdy kamera offline |
| `get_camera_capability(guid=X, ptz=1)` | guid, ptz=1 | PTZ dla jednej kamery | Presety per kamera | |

### 2. Z `act` – explicite typ capability

| Funkcja | Parametry | Opis | Zwraca | Uwagi |
|---------|-----------|------|--------|-------|
| `get_event_capability()` | act=get_event_capability | Typy IVA/Alarm per kamera | camera_motion, iva_*, alarm_* | Używane w ACC events/summary |
| `get_capability_act("get_camera_capability")` | act=get_camera_capability | To samo co ptz=0 (pyqvrpro) | Dict capability | Równoważne z ptz=0 na wielu NVR |
| `get_event_capability(guid=X)` | act=get_event_capability, guid | Event types dla jednej kamery | IVA types per camera | Opcjonalne filtrowanie |

### 3. Warianty kandydackie (może 404)

| Funkcja | Parametry | Opis | Zwraca | Uwagi |
|---------|-----------|------|--------|-------|
| `get_capability_act("list")` | act=list | Lista capability? | Nieznane | Probowane |
| `get_capability_act("get_features")` | act=get_features | Features? | Nieznane | Probowane |
| `get_capability_act("get_ptz")` | act=get_ptz | PTZ explicite? | Nieznane | Probowane |

---

## Mapowanie QVR → ACC / Frigate

| ACC potrzeba | Frigate | QVR | Funkcja |
|--------------|---------|-----|---------|
| PTZ info (presety) | getPTZInfo | ptz=1 lub act=get_camera_capability | `get_camera_capability(ptz=1)` |
| Event types (filtry) | events/summary | act=get_event_capability | `get_event_capability()` |
| Clips | has_clip | Brak | – |
| Snapshots | Event thumbnail | get_snapshot | `get_snapshot(guid)` |

---

## Użycie w bibliotece

```python
from qvr_api import QVRApi

api = QVRApi(host="10.0.0.1", user="admin", password="...")

# Podstawowe
res = api.get_camera_capability()
res = api.get_camera_capability(ptz=1)  # PTZ
res = api.get_event_capability()

# Per kamera
res = api.get_camera_capability(guid="channel-guid", ptz=1)
res = api.get_event_capability(guid="channel-guid")

# Explicite act (pyqvrpro style)
res = api.get_capability_act("get_camera_capability")
res = api.get_capability_act("get_event_capability", guid="...")

# Probowanie wszystkich wariantów
for name, params, result in api.get_capability_all_variants(guid):
    print(f"{name}: ok={result.ok}")
```

---

## Probe

```bash
QVR_PASS=xxx python tools/qvr_api_probe.py --use-library
```

Zapisuje do `probe_output/`:
- `camera_capability_*.json` – default
- `camera_capability_ptz_*.json` – ptz=1
- `camera_event_capability_*.json` – act=get_event_capability
- `camera_capability_act_*_*.json` – pozostałe act
- `capability_per_guid_*_*.json` – każdy wariant z guid (per kamera)

`summary.txt` – ok/fail per probe.
