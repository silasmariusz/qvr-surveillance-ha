# Plan testów: LPR (tablice rejestracyjne) i eventy QVR

## 1. Kontekst

QVR Pro 2.4.0+ wprowadził **LPR (License Plate Recognition)** – rozpoznawanie tablic rejestracyjnych. Kamera z LPR może generować eventy z numerem tablicy. Pytanie: **czy te eventy spływają przez API do naszych sensorów/binary sensorów?**

Obecnie:
- `binary_sensor`: IVA/eventy z `log_type=3` (Surveillance) – parsujemy `metadata.event_name`, `type`, `event_type`
- `sensor`: alert text sensors – `log_type=1` (System), `log_type=3` (Surveillance) per kamera
- `events.py`: `EVENT_TYPES` – lista znanych typów (intrusion, crossline, motion, alarm_input, itd.)

**LPR nie ma w `EVENT_TYPES`** – nie wiemy jeszcze jak QVR nazywa ten typ ani w jakim formacie wysyła (np. `iva_lpr`, `lpr_plate`, `metadata.plate_number`).

---

## 2. Testy do wykonania

### 2.1 Event capability (get_event_capability)

**Cel:** Sprawdzić czy LPR pojawia się jako typ zdarzenia w API.

```bash
python test_iva_events.py
```

**Rozszerz test:** W sekcji 3 (Event capability) wyświetl **pełną odpowiedź JSON**. Jeśli QVR 2.4+ z LPR ma nowy klucz (np. `iva_lpr`, `lpr`, `license_plate`), będzie tam.

**Dodatkowy skrypt:** `test_lpr_capability.py` – wywołuje tylko `/camera/capability?act=get_event_capability` i dumpuje cały JSON do pliku.

---

### 2.2 Logi surveillance (log_type=3) – surowe wpisy

**Cel:** Zobaczyć czy wpisy LPR mają inną strukturę (metadata, message, dodatkowe pola).

**Kroki:**
1. Uruchom kamerę LPR lub symuluj przejazd / testową tablicę.
2. Uruchom `test_iva_events.py` – sekcje 4 i 5.
3. Dla każdego wpisu logu zapisz **pełny JSON** (nie tylko `event_name` / `message`).
4. Szukaj w `metadata` pól typu: `plate_number`, `license_plate`, `lpr`, `event_name` z wartością LPR.

**Rozszerzenie test_iva_events.py:**
- Nowy tryb `--dump-raw` – zapisuje surowe logi do `logs_raw_<timestamp>.json` dla analizy offline.

---

### 2.3 Inne log_type

API `get_logs` obsługuje:
- `log_type=1` – System Events
- `log_type=2` – Connections
- `log_type=3` – Surveillance Events

**Hipoteza:** LPR może mieć osobny `log_type` (np. 4) lub być w log_type=3 z innym `event_name`.

**Test:** Dla każdego `log_type` 1..5 (jeśli API akceptuje) pobierz ostatnie 50 wpisów i sprawdź:
- Czy są wpisy
- Struktura `metadata`, `message`, `type`
- Czy numer tablicy pojawia się w `message` lub `metadata`

---

### 2.4 Filtrowanie po czasie i kanale

**Cel:** Upewnić się, że `global_channel_id` i `start_time`/`end_time` poprawnie zwracają eventy LPR z kamery 3.

**Scenariusz:**
1. Kamera 3 = LPR.
2. `get_logs(log_type=3, global_channel_id=guid_kamery_3, start_time=..., max_results=100)`.
3. Porównaj z `get_logs(log_type=3)` bez filtra – czy liczba i zawartość się zgadzają.

---

### 2.5 Binary sensor / text sensor – spływ danych

**Cel:** Zweryfikować czy nasze sensory widzą eventy LPR po dodaniu typu do `EVENT_TYPES`.

**Po zidentyfikowaniu typu LPR:**
1. Dodaj np. `iva_lpr` lub `lpr_plate` do `const.EVENT_TYPES`.
2. Przeładuj integrację.
3. Sprawdź:
   - binary sensor `qvr_surveillance.iva_lpr` dla kamery 3 – czy zmienia stan
   - text sensor Alerts – czy `recent_messages` zawiera wpis z numerem tablicy

---

## 3. Skrypty diagnostyczne

### 3.1 `test_lpr_dump.py` (do utworzenia)

1. Auth + channels.
2. `get_event_capability` → zapisz do `event_capability_<ts>.json`.
3. Dla każdej kamery i `log_type` 1, 2, 3: `get_logs` → zapisz do `logs_type{N}_ch{idx}_<ts>.json`.
4. Opcjonalnie: `get_logs` bez filtra dla log_type 3, 4, 5 – sprawdzenie czy istnieją inne typy.

### 3.2 Rozszerzenie `test_iva_events.py`

- Flaga `--verbose` / `--dump` – pełny dump JSON zamiast skróconego podsumowania.
- Sekcja 6: "Sprawdzenie LPR" – wyszukanie w message/metadata słów: `plate`, `license`, `lpr`, `tablic`, `rejestr`.

---

## 4. Kolejność wykonania

| # | Zadanie | Warunek |
|---|---------|---------|
| 1 | Rozszerzyć test_iva_events o dump event_capability | Zawsze |
| 2 | Dodać --dump-raw dla logów | Zawsze |
| 3 | test_lpr_dump.py – pełny zrzut API | Zalecane przed analizą |
| 4 | Test na QVR 2.4+ z kamerą LPR | Potrzebny dostęp |
| 5 | Dodać LPR do EVENT_TYPES + binary/text sensor | Po zidentyfikowaniu formatu |

---

## 5. Odniesienia

- QVR Pro 2.4.0: LPR + video content analysis (QNAP Qutube)
- pyqvrpro fixtures (2019): brak LPR w event_capability – wersja sprzed 2.4.0
- API: `camera/capability?act=get_event_capability`, `logs/logs?log_type=...`
