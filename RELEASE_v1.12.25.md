## v1.12.25

### Odporność na restart i blokadę QVR

- **Retry setup** – przy błędzie połączenia lub auth ponowna próba co 10 s
- **Pętla reconnect** – podczas działania integracji, gdy QVR się zrestartuje lub zablokuje, automatyczne próby ponownego połączenia co 10 s
- **Klient** – 6 prób na port co 10 s, fallback na porty 8080/443/38080
