# QVR Metadata Platform – Czym są metadane, do czego służą

## Źródło: QVR API i dokumentacja QNAP

QVR Pro udostępnia **Metadata Platform** (Open Metadata Platform) jako część QVR Developer. Odniesienia:
- QVR Developer: Open Video I/O, Open Event I/O, **Metadata Platform**
- Metadata Vault (GUI QVR Pro) – zarządzanie źródłami metadanych
- QNAP docs: Metadata Vault – dodawanie Data Sources, parowanie z kamerą, OSD

---

## Czym są metadane w QVR?

### 1. Metadata Vault (GUI)
- **Data Source** – zewnętrzne urządzenie (np. LPR, IVA, inne NVR) wysyłające metadane do QVR
- **Metadata URL** – QVR może odbierać metadane od urządzeń przez URL/webhook
- **Camera Pairing** – przypisanie źródła metadanych do kamery
- **OSD** – wyświetlanie metadanych na nagraniu (np. numer tablicy rejestracyjnej na ekranie)

### 2. Metadata w nagraniach (Metadata Search)
- QNAP FAQ: możliwość **search metadata in recordings** – wyszukiwanie po słowach kluczowych, operatorach (spacje, cudzysłowy, plus)
- Filtrowanie po: czas, kamera, typ źródła danych, źródło
- Metadane są **osadzane w plikach nagrań** – nie osobny endpoint REST

### 3. API `/metadata` (endpoint HTTP)
- Ścieżka: `{qvr_path}/metadata` lub `{qvr_path}/metadata/{subpath}`
- **Status:** Często **404** na typowych instalacjach QVR
- **Powód 404:** Metadata Vault to opcjonalna funkcja. Wymaga:
  1. Konfiguracji Data Source w QVR
  2. Parowania z kamerą
  3. Aktywnego wysyłania metadanych
- Gdy brak źródeł – endpoint nie istnieje lub nie jest udostępniany przez API 1.1.0

---

## Do czego służą metadane?

| Cel | Opis |
|-----|------|
| **LPR** | Numer tablicy rejestracyjnej – zapisywany przy wykryciu, można wyszukiwać |
| **IVA / AI** | Wykrycia (intruz, przekroczenie linii) – dodatkowe pola od urządzenia |
| **Oznaczenia** | Dane OSD – np. temperatura, identyfikator strefy |
| **Wyszukiwanie** | Metadata Search w QVR Client – po słowach kluczowych w nagraniach |

---

## Dlaczego nie są wykorzystane w integracji?

1. **Endpoint `/metadata` zwraca 404** na większości instalacji – brak skonfigurowanych Data Sources
2. **Nie ma oficjalnej dokumentacji API** – QVR API 1.1.0 (Swagger) nie opisuje `/metadata`
3. **Metadata Search** – to funkcja GUI QVR Client, nie udokumentowany endpoint REST
4. **Brak danych** – bez Data Source nie ma metadanych do pobrania

**Strategia:** Probe testuje `/metadata` i subpathy (search, list). Jeśli 200 – można dodać konwerter i integrację. Póki 404 – pomijamy.

---

## Mapowanie na ACC / Frigate

| ACC / Frigate | Metadata Platform | Status |
|---------------|-------------------|--------|
| Event labels | metadata.event_name, LPR | Gdy get_events zwraca metadata – już przekazujemy (`metadata` w ACC event) |
| Search by label | metadata search | Brak API – 404 |
| Clips | – | QVR nie ma clips |
| Recordings | resourceUris | Z get_recording, nie z metadata |

**Podsumowanie:** Metadane z `get_events()` / `get_logs()` (pole `metadata` w wpisie) – **już wykorzystywane** w converters (passthrough do ACC). Endpoint `/metadata` – opcjonalny, gdy dostępny.
