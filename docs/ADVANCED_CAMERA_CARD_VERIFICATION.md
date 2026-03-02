# Weryfikacja: Advanced Camera Card vs QVR Surveillance

## Jak karta widzi nasz silnik

### 1. Wykrywanie engine (auto)

Karta sprawdza `entity.platform` w rejestrze encji:
- `platform === 'qvr_surveillance'` → engine = `Engine.QVRSurveillance` ✅
- Nasza integracja tworzy kamery z platformą `qvr_surveillance` – wykrywanie działa poprawnie

Ręczne ustawienie: `engine: qvr_surveillance` w konfiguracji kamery.

---

### 2. Live provider – stream vs snapshot

**To jest kluczowe.** Karta ma parametr `live_provider`:

| live_provider | Co pokazuje | Jakość |
|---------------|-------------|--------|
| `auto` (domyślnie) + `camera_entity` | **`ha`** – stream HLS/WebRTC z HA | Pełna (RTSP→HLS) |
| `ha` | Stream z `stream_source` (RTSP) | Pełna |
| `image` | **Snapshots** – odświeżane zdjęcia z `camera_image` | Niska, wygląda jak „slajdy” |

Przy `live_provider: auto` i encji kamery → karta używa `ha` = **stream RTSP (przez HLS)**.  
Jeśli widzisz „snapshoty” – prawdopodobnie `live_provider` ustawiony jest na `image`.

---

### 3. Nadpisanie przez profile

Profil **low-performance** ustawia:
```yaml
cameras_global:
  live_provider: image  # Wszystkie kamery na snapshots!
```

Jeśli ten profil jest włączony, wszystkie kamery (w tym QVR) przechodzą na `image` = **snapshots zamiast streamu**.

---

### 4. Podczas ładowania streamu

Gdy `show_image_during_load: true` (domyślnie), karta pokazuje snapshot jako placeholder **do momentu załadowania streamu**. Jeśli stream nie ładuje się (np. wygasła sesja RTSP), obraz pozostaje na snapshotcie.

---

## Zalecenia dla QVR

1. **Sprawdź `live_provider`** – w edytorze Advanced Camera Card: Camera → Live provider
   - Powinno być: `Auto` albo `ha`
   - Unikaj `image` – daje tylko snapshots i niską jakość

2. **Sprawdź profile** – przy `low-performance` wszystkie kamery używają `image`.  
   Albo wyłącz ten profil, albo nadpisz per kamera: `live_provider: ha`.

3. **go2rtc** – dla najlepszej jakości i niskiego opóźnienia:
   ```yaml
   live_provider: go2rtc
   go2rtc:
     url: http://ha-ip:1984  # gdzie działa go2rtc
     stream: camera.qvr_surveillance_1  # lub nazwa streamu w go2rtc
   ```
   Wymaga dodania kamery RTSP do go2rtc.

4. **Encja Main, nie Sub** – używaj `camera.qvr_surveillance_1` (Main), nie `..._sub` (substream).

---

## Podsumowanie

| Problem | Przyczyna |
|---------|-----------|
| Wygląda jak snapshoty | `live_provider: image` (np. profil low-performance) |
| Fatalna jakość | Sub stream zamiast Main, lub snapshot z API QVR |
| Nie ładuje się | Stream RTSP (sesja wygasła), karta zostaje na snapshotcie placeholder |
| Silnik niewidoczny | Sprawdź, czy encja ma `platform: qvr_surveillance` w rejestrze |

Karta poprawnie wykrywa engine QVR i domyślnie używa streamu (`ha`). Trzeba pilnować, żeby `live_provider` nie był wymuszony na `image` przez profile lub ręczną konfigurację.
