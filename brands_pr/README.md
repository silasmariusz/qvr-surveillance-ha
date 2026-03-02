# Ikona QVR Surveillance dla Media Browsera

Ikona w przeglądarce mediów („icon not available”) pochodzi z repozytorium [home-assistant/brands](https://github.com/home-assistant/brands).

## Jak dodać ikonę

1. Skopiuj folder `qvr_surveillance/` do swojego forka `home-assistant/brands`:
   ```
   home-assistant/brands/custom_integrations/qvr_surveillance/
   ```

2. **Opcja A – użyj logo.png z tego folderu** (placeholder 128×128)

3. **Opcja B – przekonwertuj icon.svg na PNG** (lepsza jakość):
   - Użyj np. [cloudconvert.com/svg-to-png](https://cloudconvert.com/svg-to-png) lub Inkscape
   - Rozmiar: 256×256 lub 128×128 px
   - Zapisz jako `logo.png` i `icon.png`

4. Otwórz PR na https://github.com/home-assistant/brands:
   - Dodaj pliki w `custom_integrations/qvr_surveillance/`
   - Tytuł np.: „Add qvr_surveillance”

5. Po mergu ikona pojawi się w Media Browserze (może być potrzebny restart HA).
