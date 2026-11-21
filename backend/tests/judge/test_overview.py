"""Overview page and its live partial (SPEC 5.1, 5.3, 10.10, 10.13, 10.14)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.models import Node, Reading


def add(db, node_id, node_type, metrics, age_min=1):
    ts = datetime.now(UTC) - timedelta(minutes=age_min)
    db.add(Node(node_id=node_id, node_type=node_type, first_seen=ts, last_seen=ts))
    db.flush()
    for m, v in metrics.items():
        db.add(Reading(node_id=node_id, metric=m, ts=ts, value=v))
    db.flush()


def test_empty_state(client, db):
    t = client.get("/").text
    assert "No readings yet" in t
    assert 'id="now"' in t and 'hx-get="/partials/current"' in t and 'hx-trigger="every 60s"' in t


def test_weather_and_soil(client, db):
    add(
        db,
        "weather-main",
        "weather",
        {"temp_c": 12.3, "humidity_pct": 80, "wind_speed_ms": 3, "wind_dir_deg": 90},
    )
    add(db, "soil-bed-1", "soil", {"soil_moisture_pct": 18, "soil_temp_c": 9.5})
    t = client.get("/").text
    assert "weather-main" in t and "12.3" in t and "°C" in t
    assert "soil-bed-1" in t and "18 %" in t and "needs water" in t
    assert " E " in t or ">E " in t or "E 90" in t  # compass point next to degrees
    assert "Water needed" in t
    assert "data-chart" in t and "/static/js/charts.js" in t


def test_frost_and_offline(client, db):
    add(db, "weather-main", "weather", {"temp_c": 1.0}, age_min=40)
    t = client.get("/").text
    assert "Frost warning" in t
    assert "Offline since" in t


def test_partial_is_fragment(client, db):
    add(db, "weather-main", "weather", {"temp_c": 20.0})
    t = client.get("/partials/current").text
    assert "<html" not in t and "<nav" not in t
    assert 'id="now"' in t and "weather-main" in t


@pytest.mark.parametrize("path", ["/garden", "/seeds", "/tasks", "/species"])
def test_placeholders_exist_for_signed_in(client, path):
    from app.config import Settings

    s = Settings()
    assert client.get(path, auth=(s.ADMIN_USER, s.ADMIN_PASSWORD)).status_code == 200
