"""Human-owned contract tests. The agent must not edit this file.

Pins: the schema is valid, the samples validate as expected, and the backend
exposes the field names the website depends on. Backend-dependent tests skip
until the app exists, then must pass.
"""
import json
import pathlib

import jsonschema
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "reading.schema.json").read_text())
SAMPLES = ROOT / "samples"


def test_schema_is_valid():
    jsonschema.Draft202012Validator.check_schema(SCHEMA)


@pytest.mark.parametrize("name", ["weather_valid.json", "soil_valid.json"])
def test_valid_samples_pass(name):
    data = json.loads((SAMPLES / name).read_text())
    jsonschema.validate(data, SCHEMA)


def test_wrong_metric_for_type_is_structurally_valid_but_semantically_rejected():
    # The JSON schema allows temp_c structurally; node_type/metric agreement is a
    # backend rule. This documents that the backend — not the schema — enforces it.
    data = json.loads((SAMPLES / "invalid_bad_metric.json").read_text())
    jsonschema.validate(data, SCHEMA)  # passes schema
    assert data["node_type"] == "soil" and "temp_c" in data["metrics"]


REQUIRED_NODE_FIELDS = {"node_id", "node_type", "last_seen", "online"}


def test_backend_nodes_contract():
    app_main = ROOT.parent / "backend" / "app" / "main.py"
    if not app_main.exists():
        pytest.skip("backend not built yet")
    from fastapi.testclient import TestClient  # noqa: WPS433

    from app.main import app  # type: ignore

    client = TestClient(app)
    resp = client.get("/api/v1/nodes")
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    for row in rows:
        assert REQUIRED_NODE_FIELDS <= set(row), f"missing contract fields: {REQUIRED_NODE_FIELDS - set(row)}"
