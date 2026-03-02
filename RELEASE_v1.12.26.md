## v1.12.26

### Naprawy

- **Blocking calls w event loop** – retry setup uruchamiany w executorze (requests, time.sleep nie blokują już event loop)
- **Blokada serwera 10 min** – mniej agresywne retry: RECONNECT_INTERVAL 60 s, RETRY_DELAY 30 s, 2 próby na port (mniej requestów → mniejsze ryzyko blokady)
- **Recording 404** – wyciszone logi przy oczekiwanych 404, fallback na /qvrpro/ gdy /qvrsurveillance zwraca 404
