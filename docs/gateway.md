# Gateway (Raspberry Pi)

A small Python service on the Pi. Subscribes to the Mosquitto broker, validates
each message against the contract, batches them, and POSTs them to the backend over
HTTPS (`BACKEND_URL`). It must never lose readings across a crash or a network
outage, and never crash on a bad message.

## Layout (inside `gateway/`)
```
gateway/
  pyproject.toml         # uv project
  gateway/
    __init__.py
    main.py              # wire everything, run loop
    config.py            # env: MQTT_HOST, MQTT_PORT, BACKEND_URL, INGEST_TOKEN, BUFFER_DIR, BATCH_*, 
    validate.py          # schema validation (loads ../contract/reading.schema.json)
    buffer.py            # durable on-disk queue
    sender.py            # batching + POST with retry
  tests/
  gateway.env.example
  systemd/weather-gateway.service   # runs it on the Pi
```

## Allowed dependencies
paho-mqtt, httpx, jsonschema, pydantic, pytest, ruff, mypy.

## Behaviour (SPEC 7)
- Subscribe `garden/+/reading`, QoS 1.
- On message: parse JSON, validate against the schema. Invalid → increment a
  `dropped` counter, log at warning, continue. Never raise out of the callback.
- Valid readings go to the durable buffer (one JSON line per reading in a file
  under `BUFFER_DIR`, fsync'd). The sender pulls up to `BATCH_MAX` (default 200)
  or every `BATCH_SECONDS` (default 10), POSTs `{"readings": [...]}` to
  `BACKEND_URL/api/v1/readings` with the bearer token.
- On 2xx: drop those lines from the buffer. On failure (network, 5xx): keep them
  and retry with backoff. A restart re-reads the buffer and continues — no loss.
- Per-item `rejected` entries in a 200 response, or a 400: log and drop those
  items (they will never succeed); keep the accepted accounting straight.

## Testing
- Durability: write readings to the buffer, simulate a crash (new buffer instance
  on the same dir), assert nothing is lost and nothing double-sent after a flush.
- Bad message: feed invalid JSON and a schema-violating message to the handler,
  assert it is counted and dropped and the service keeps running.
- Sender: use a fake backend (httpx MockTransport) to assert batching, retry on
  5xx, and buffer drain on 200.
Run the broker-less parts as plain unit tests; don't require a real MQTT broker.
