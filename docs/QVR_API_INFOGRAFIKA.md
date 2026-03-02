# QVR API – Infografika (schematy, przepływy)

Input do infografiki. Mermaid – renderuj w GitHub/Markdown viewer.

---

## 1. Przepływ: Od czego zacząć

```mermaid
flowchart TD
    A[Auth: authLogin.cgi] --> B[SID]
    B --> C[GET /qvrentry]
    C --> D{qvp?}
    D -->|yes| E[qvr_path = /qvrpro]
    D -->|no| F[qvr_path = /qvrelite]
    E --> G[Wszystkie kolejne wywołania]
    F --> G
```

---

## 2. Przepływ: Timeline dla ACC

```mermaid
flowchart LR
    ACC[Advanced Camera Card] --> WS[WebSocket]
    WS --> |recordings/summary| R1[get_recording_list]
    WS --> |recordings/get| R2[get_recording_list]
    WS --> |events/get| E1[get_events]
    
    R1 --> |404/empty| P1[Probe get_recording per day]
    R2 --> |404/empty| P2[Probe get_recording per hour]
    
    R1 --> |ok| C1[recording_list_to_acc_summary]
    R2 --> |ok| C2[recording_list_to_acc_segments]
    E1 --> |ok| C3[events_response_to_acc_events]
    
    P1 --> S1[Summary day/hour]
    P2 --> S2[Segments start/end]
    
    C1 --> OUT[ACC timeline]
    C2 --> OUT
    C3 --> OUT
    S1 --> OUT
    S2 --> OUT
```

---

## 3. Drzewo endpointów

```mermaid
flowchart TB
    ROOT[QVR API]
    ROOT --> QVRE[/qvrentry]
    ROOT --> QVR["{qvr_path}"]
    
    QVR --> QSHARE["/qshare"]
    QVR --> CAM["/camera"]
    QVR --> LOGS["/logs"]
    QVR --> PTZ["/ptz"]
    
    QSHARE --> CH["StreamingOutput/channels"]
    QSHARE --> STR["channel/{guid}/streams"]
    QSHARE --> LIVE["stream/{n}/liveStream POST"]
    
    CAM --> SNAP["snapshot/{guid}"]
    CAM --> REC["recordingfile/{guid}/{ch}"]
    CAM --> RECLIST["recording/{guid}"]
    CAM --> LIST["list"]
    CAM --> CAP["capability"]
    CAM --> SEARCH["search"]
    CAM --> EV["events"]
    CAM --> MREC["mrec/{guid}/start|stop PUT"]
    
    CAP --> |ptz=0,1| CAP_PTZ
    CAP --> |act=get_event_capability| CAP_EV
    CAP --> |act=get_camera_capability| CAP_CAM
    
    LOGS --> LOGS_T["logs?log_type=1..5"]
```

---

## 4. Co ACC potrzebuje vs co QVR daje

```mermaid
flowchart TB
    subgraph ACC["ACC (Frigate)"]
        A1[events/get]
        A2[recordings/summary]
        A3[recordings/get]
        A4[events/summary]
        A5[ptz/info]
        A6[event/retain]
    end
    
    subgraph QVR["QVR API"]
        Q1[get_events]
        Q2[get_recording_list]
        Q3[get_recording time probe]
        Q4[get_event_capability]
        Q5[get_camera_capability ptz=1]
        Q6[brak]
    end
    
    A1 --> Q1
    A2 --> Q2
    A2 --> Q3
    A3 --> Q2
    A3 --> Q3
    A4 --> Q4
    A5 --> Q5
    A6 --> Q6
```

---

## 5. Tabela: Cel → Zapytanie

| Cel | Pierwsze zapytanie | Fallback (gdy 404) |
|-----|-------------------|---------------------|
| Lista kanałów | get_channels | – |
| Stream na żywo | get_live_stream | – |
| Migawka | get_snapshot | – |
| Nagranie (playback) | get_recording(time) | – |
| Segmenty timeline | get_recording_list(guid, start, end) | Probe get_recording co 1h |
| Summary timeline | get_recording_list(guid) | Probe get_recording raz/dzień |
| Eventy timeline | get_events | – ([] gdy 404) |
| PTZ presety | get_camera_capability(ptz=1) | – |
| Typy IVA | get_event_capability | – |
| Logi (sensory HA) | get_logs | – |
