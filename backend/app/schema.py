"""JSON schema validation helpers for reading batches."""

import json
import pathlib

from jsonschema import Draft202012Validator

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_VALIDATOR = Draft202012Validator(
    json.loads((_ROOT / "contract" / "reading.schema.json").read_text())
)

ALLOWED_METRICS: dict[str, set[str]] = {
    "weather": {
        "temp_c",
        "humidity_pct",
        "pressure_hpa",
        "rain_mm",
        "wind_speed_ms",
        "wind_dir_deg",
    },
    "soil": {"soil_moisture_pct", "soil_temp_c"},
}
