# Format eventów dla Advanced Camera Card (timeline)

## Wymagania ACC (engine QVRSurveillance)

Karta oczekuje tablicy obiektów ze schematu:

```typescript
{
  id: string;      // wymagane
  time: number;    // Unix seconds (nie ms!)
  message?: string;
  type?: string;
}
// + passthrough dla level, channel_id, metadata
```

## Nasza odpowiedź (ws_get_events → _map_logs_to_events)

| Pole | Źródło | Uwagi |
|------|--------|-------|
| `id` | `entry.id` / `log_id` / `{guid}_{i}_{ts}` | Wymagane |
| `time` | `entry.time` / `timestamp` / `UTC_time` | **Unix seconds** – jeśli >1e12, dzielimy przez 1000 (ms→s) |
| `message` | `entry.message` / `content` | |
| `type` | `metadata.event_name` / `type` / `event_type` | |
| `level` | `entry.level` | Opcjonalne |
| `channel_id` | `channel_id` / `global_channel_id` | |
| `metadata` | `entry.metadata` | |

## ACC użycie

- `getStartTime()` = `new Date(event.time * 1000)` – więc `time` musi być w **sekundach**
- `getThumbnail()` = `/api/qvr_surveillance/{clientId}/snapshot/{channelGuid}`
- Karta pobiera `channelGuid` z atrybutu `qvr_guid` encji kamery

## Diagnostyka timeline

1. Włącz debug: `logger: custom_components.qvr_surveillance: debug`
2. Szukaj w logach: `events/get instance_id=... camera=... raw_logs=N events=M`
3. Jeśli `raw_logs=0` – QVR nie zwraca logów dla tego kanału (sprawdź IVA, log_type=3)
4. Jeśli `events=0` ale `raw_logs>0` – problem z parsowaniem (sprawdź strukturę wpisu)
5. Test: `python test_iva_events.py` – weryfikacja czy API zwraca eventy
