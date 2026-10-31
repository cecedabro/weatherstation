# Data contract (human-owned — do not edit)

This is the single source of truth for what a reading is and how the parts talk.
Firmware, gateway and backend must all agree with it. It is deliberately small.

## The reading batch
One MQTT message and one item in a POST body is a **reading batch**: all metrics
from one node at one instant. Schema: `reading.schema.json`. Validate against it.

Example (weather node):
```json
{
  "node_id": "weather-main",
  "node_type": "weather",
  "ts": "2026-05-01T12:34:56Z",
  "fw": "1.0.0",
  "battery_v": null,
  "rssi_dbm": -61,
  "metrics": {
    "temp_c": 14.2, "humidity_pct": 71, "pressure_hpa": 1013.4,
    "rain_mm": 0.2, "wind_speed_ms": 3.1, "wind_dir_deg": 225
  }
}
```
Example (soil node, battery powered):
```json
{
  "node_id": "soil-bed-3", "node_type": "soil", "ts": "2026-05-01T12:35:10Z",
  "fw": "1.0.0", "battery_v": 3.92, "rssi_dbm": -78,
  "metrics": { "soil_moisture_pct": 38.5, "soil_temp_c": 11.0 }
}
```

## Metrics by node type
| node_type | allowed metrics |
| --- | --- |
| `weather` | `temp_c`, `humidity_pct`, `pressure_hpa`, `rain_mm`, `wind_speed_ms`, `wind_dir_deg` |
| `soil` | `soil_moisture_pct`, `soil_temp_c` |

A node need not send every metric (a sensor may be absent), but every metric it
sends must be in its type's list and within the schema's range. `rain_mm` is the
amount since the previous reading, not a running total.

## Units (SI, fixed)
°C, % relative humidity, hPa, mm, m/s, degrees (0–360, clockwise from north),
% volumetric soil moisture, volts, dBm. Storage and all code use UTC.

## MQTT
- Broker: Mosquitto on the Pi, plaintext, LAN only.
- Topic: `garden/<node_id>/reading`. Payload: one reading batch as JSON (UTF-8).
- QoS 1. Nodes may set a retained last-will on `garden/<node_id>/status` = `offline`.

## Backend ingest API (the gateway is the only writer)
- `POST /api/v1/readings` — body: `{"readings": [<batch>, ...]}` (1–500 items).
  - Auth: `Authorization: Bearer <INGEST_TOKEN>`.
  - Each batch validated against the schema. Response `207`-style summary:
    `{"accepted": <n>, "rejected": [{"index": i, "error": "..."}]}` with HTTP 200
    if at least one accepted, 400 if the body is malformed, 401 if the token is wrong.
  - Ingest is idempotent on (`node_id`, `ts`, metric): re-POSTing the same reading
    must not create duplicates.

## Read API (the website uses these)
- `GET /api/v1/current` → latest reading per node.
- `GET /api/v1/series?node=&metric=&from=&to=&step=` → downsampled points for charts.
  `step` is one of `raw|5m|1h|1d`; `from`/`to` are RFC3339 UTC.
- `GET /api/v1/nodes` → one row per known node: `node_id`, `node_type`,
  `last_seen`, `last_battery_v`, `last_rssi_dbm`, `online` (seen within 15 min).

The exact response JSON beyond these required fields is the backend's choice, but
these field names and the endpoints above are fixed.

## Contract tests
`contract/tests/` holds the human-owned tests that pin this contract (schema
validity, a valid and an invalid sample, the endpoint field names). The agent
must not edit them. They run as part of `make check`.
