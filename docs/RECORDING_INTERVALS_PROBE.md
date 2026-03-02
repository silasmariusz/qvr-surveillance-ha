# Probe nagrań: ciągłe vs detekcja ruchu

Na timeline QVR Client (np. 2026-03-02):
- **Niebieski pasek** 00:00–04:30 = nagrywanie ciągłe (Normal Recording)
- **Czerwone linie** od ~12:00 = nagrywanie z detekcji ruchu (Event Recording)

## Uruchomienie

```bash
QVR_PASS=xxx python tools/probe_recording_intervals.py
QVR_PASS=xxx QVR_DATE=2026-03-02 python tools/probe_recording_intervals.py
```

## Co robi probe

1. **Przedział ciągły** (00:00–04:30) – wysyła zapytania z różnymi wariantami:
   - `time` + `pre_period`/`post_period`
   - `time` (środek) + pre/post
   - `start`/`end`
   - `start_time`/`end_time`

2. **Przedział motion** (12:00–14:00) – te same warianty

3. **URI** – `recordingfile/{guid}/0`, `/1`, `recording/{guid}`

4. **Parametry kandydackie** – `rec_type=continuous|motion`, `recording_type=0|1` (może 404)

## Wynik

- Konsola: status każdego zapytania (bytes, dict, err)
- `probe_intervals_output/summary_*.json` – podsumowanie

## API QVR

QVR nie udostępnia parametru filtra po typie nagrania w `/camera/recordingfile/`. Typ (ciągłe vs event) to ustawienie kamery; API zwraca nagrania dla zadanego przedziału bez rozróżnienia. Oba przedziały pobieramy tym samym zestawem parametrów – różnica jest w czasie (00:00 vs 12:00).
