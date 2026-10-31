# Firmware (ESP32 sensor nodes)

Arduino framework in C++, built with PlatformIO. One source tree, one build
environment per node type, plus a `native` environment that unit-tests the pure
logic on your PC (no board needed). The small model struggles with hardware it
can't test, so the rule is: **all testable logic is pure and host-tested; the
hardware glue is thin and only compiled, not unit-tested.**

## Node types
- `weather` (mains or solar, in the garden): BME280 (temp/humidity/pressure),
  tipping-bucket rain gauge (interrupt-counted), anemometer (pulse-counted),
  wind vane (ADC). Publishes every 60 s. Light sleep between.
- `soil` (battery, in the volkstuin beds): capacitive soil moisture (ADC) +
  DS18B20 soil temperature. Publishes every 15 min, then **deep sleep**.

## Layout (inside `firmware/`)
```
firmware/
  platformio.ini         # [env:weather] [env:soil] [env:native]
  lib/
    reading/             # PURE, no Arduino headers:
      reading.h/.cpp     #   struct Reading; std::string encode(const Reading&)
      calib.h/.cpp       #   raw ADC → soil_moisture_pct, pulses → wind_speed_ms, etc.
  src/
    main_weather.cpp     # thin: read sensors → fill Reading → encode → MQTT publish
    main_soil.cpp        # thin: same, then esp_deep_sleep
    net.h/.cpp           # wifi + MQTT connect (thin)
  test/
    test_reading/        # Unity tests for encode() and calib, run on native
```
Select the source per env in `platformio.ini` with `build_src_filter`.

## Allowed libraries
PubSubClient (MQTT), ArduinoJson, Adafruit BME280 + Adafruit Unified Sensor,
OneWire + DallasTemperature (DS18B20). For `native`: the Unity framework PlatformIO
ships. Keep ArduinoJson usage inside `lib/reading` so `encode()` is host-buildable.

## §encode (T21, the heart of it)
- `encode(const Reading&)` returns the exact JSON batch from the contract
  (`contract/reading.schema.json`). It is pure: no Wi-Fi, no `Serial`, no `millis`.
- Host test: build sample `Reading` structs, call `encode`, parse the JSON, and
  assert the fields and ranges match the contract. The weather and soil encodings
  must validate against the schema (ship a copy of the expected keys in the test).
- `calib` functions (ADC→%, pulses→m/s) are pure and unit-tested with known inputs.

## §runtime (T22–T23, compile-only)
- `net` connects Wi-Fi then MQTT (broker IP, topic `garden/<node_id>/reading`,
  credentials) from compile-time config in `platformio.ini` `build_flags`
  (`-D NODE_ID=\"weather-main\"` etc.) — never hardcode secrets in source; read
  Wi-Fi creds from `build_flags` supplied by a local `.env`-style include that is
  gitignored. Document the flags in `firmware/README.md`.
- Weather node: light sleep 60 s loop. Soil node: publish then
  `esp_deep_sleep(15*60*1e6)`; on wake it re-reads and re-publishes.
- Set the MQTT last-will on `garden/<node_id>/status` = `offline` (retained).
- T22–T23 only need `pio run -e <env>` (compile) to pass; they are not host-tested.

## Clock / timestamps
Every node syncs time via NTP after connecting to Wi-Fi and stamps `ts` itself
(UTC, RFC3339). If NTP fails, skip that publish and retry on the next wake rather
than sending a wrong time. Note the choice in PROGRESS.md.
