"""Store-reading service tests: upsert per SPEC 2.2-2.3."""

import json
import pathlib

from sqlalchemy import func, select

from app.models import Node, Reading
from app.store import upsert_readings

# Sample batches loaded from contract
_WEATHER = json.loads(
    (
        pathlib.Path(__file__).resolve().parents[2] / "contract" / "samples" / "weather_valid.json"
    ).read_text()
)
_SOIL = json.loads(
    (
        pathlib.Path(__file__).resolve().parents[2] / "contract" / "samples" / "soil_valid.json"
    ).read_text()
)


def test_upsert_one_batch_stores_one_row_per_metric(db):
    """SPEC 2.2: a reading batch produces one row per metric value."""
    result = upsert_readings(db, [_WEATHER])

    assert result["accepted"] == 1
    assert result["rejected"] == []

    rows = db.execute(select(Reading).where(Reading.node_id == "weather-main")).scalars().all()
    assert len(rows) == 6  # 6 metrics in the weather sample

    metrics = {r.metric for r in rows}
    expected = {
        "temp_c",
        "humidity_pct",
        "pressure_hpa",
        "rain_mm",
        "wind_speed_ms",
        "wind_dir_deg",
    }
    assert metrics == expected

    # Verify a specific value was stored correctly
    temp = next(r for r in rows if r.metric == "temp_c")
    assert float(temp.value) == 14.2


def test_upsert_same_batch_no_duplicates(db):
    """SPEC 2.3: re-storing a batch with the same (node_id, ts) does not
    create duplicate metric rows."""
    upsert_readings(db, [_WEATHER])

    rows_before = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert rows_before == 6

    # Re-insert the exact same batch
    upsert_readings(db, [_WEATHER])

    rows_after = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert rows_after == 6  # no growth


def test_upsert_updates_value_on_conflict(db):
    """SPEC 2.3: re-inserting with a different value updates the row."""
    batch = dict(_WEATHER, metrics={"temp_c": 10.0, "humidity_pct": 50.0})
    upsert_readings(db, [batch])

    rows = db.execute(select(Reading).where(Reading.node_id == "weather-main")).scalars().all()
    temps = [r for r in rows if r.metric == "temp_c"]
    assert len(temps) == 1
    assert float(temps[0].value) == 10.0

    # Upsert with a different value
    batch2 = dict(_WEATHER, metrics={"temp_c": 25.0})
    upsert_readings(db, [batch2])

    rows2 = db.execute(select(Reading).where(Reading.node_id == "weather-main")).scalars().all()
    temps2 = [r for r in rows2 if r.metric == "temp_c"]
    assert len(temps2) == 1
    assert float(temps2[0].value) == 25.0

    # Other metrics from the first insert are still there
    humid = [r for r in rows2 if r.metric == "humidity_pct"]
    assert len(humid) == 1
    assert float(humid[0].value) == 50.0


def test_upsert_multiple_batches(db):
    """Multiple batches are all stored, each as one row per metric."""
    batches = [_WEATHER, _SOIL]
    result = upsert_readings(db, batches)

    assert result["accepted"] == 2

    weather_count = db.execute(
        select(func.count()).select_from(Reading).where(Reading.node_id == "weather-main")
    ).scalar()
    soil_count = db.execute(
        select(func.count()).select_from(Reading).where(Reading.node_id == "soil-bed-3")
    ).scalar()
    assert weather_count == 6
    assert soil_count == 2


def test_upsert_creates_node_row(db):
    """Inserting a batch creates/updates the node registry."""
    upsert_readings(db, [_WEATHER])

    node = db.get(Node, "weather-main")
    assert node is not None
    assert node.node_type == "weather"
    assert node.last_battery_v is None
    assert node.last_rssi_dbm == -61


def test_upsert_node_updated_values(db):
    """Updating a node's last_seen/battery/rssi on re-insert."""
    now_ts = "2026-05-01T12:34:56Z"
    batch1 = dict(_WEATHER, ts=now_ts, battery_v=3.5, rssi_dbm=-65)
    upsert_readings(db, [batch1])

    node = db.get(Node, "weather-main")
    assert float(node.last_battery_v) == 3.5
    assert node.last_rssi_dbm == -65

    # Re-insert with updated values
    batch2 = dict(_WEATHER, ts=now_ts, battery_v=3.2, rssi_dbm=-70)
    upsert_readings(db, [batch2])

    node = db.get(Node, "weather-main")
    assert float(node.last_battery_v) == 3.2
    assert node.last_rssi_dbm == -70


def test_upsert_mixed_accepted_rejected(db):
    """Batches that fail validation are rejected without affecting accepted ones."""
    bad_batch = {
        "node_id": "weather-main",
        "node_type": "weather",
        "ts": "bad-timestamp",
        "fw": "1.0",
        "metrics": {"temp_c": 20.0},
    }
    result = upsert_readings(db, [_WEATHER, bad_batch, _SOIL])

    assert result["accepted"] == 2
    assert result["rejected"] == [1]

    # Both valid batches should be in the DB
    total = db.execute(select(func.count()).select_from(Reading)).scalar()
    assert total == 8  # 6 weather + 2 soil


def test_upsert_empty_batches(db):
    """An empty batch list is a no-op."""
    result = upsert_readings(db, [])
    assert result["accepted"] == 0
    assert result["rejected"] == []


def test_upsert_soil_batch_stores_correct_metrics(db):
    """SPEC 2.2: a soil batch stores exactly soil metrics."""
    result = upsert_readings(db, [_SOIL])
    assert result["accepted"] == 1

    rows = db.execute(select(Reading).where(Reading.node_id == "soil-bed-3")).scalars().all()
    assert len(rows) == 2

    metrics = {r.metric for r in rows}
    assert metrics == {"soil_moisture_pct", "soil_temp_c"}

    moist = next(r for r in rows if r.metric == "soil_moisture_pct")
    assert float(moist.value) == 38.5

    temp = next(r for r in rows if r.metric == "soil_temp_c")
    assert float(temp.value) == 11.0


def test_upsert_partial_metrics_no_missing_metric_rows(db):
    """A batch with only some metrics only creates rows for present metrics."""
    partial = dict(_WEATHER, metrics={"temp_c": 20.0})
    result = upsert_readings(db, [partial])
    assert result["accepted"] == 1

    rows = db.execute(select(Reading).where(Reading.node_id == "weather-main")).scalars().all()
    assert len(rows) == 1
    assert rows[0].metric == "temp_c"
    assert float(rows[0].value) == 20.0


def test_upsert_counter_verify_no_duplicates(db):
    """Verify metric counts via Counter after multiple upserts."""
    batches = [_WEATHER] * 5
    result = upsert_readings(db, batches)
    assert result["accepted"] == 5  # all accepted

    counts = db.execute(
        select(Reading.node_id, Reading.metric, func.count()).group_by(
            Reading.node_id, Reading.metric
        )
    ).all()
    for _, metric, count in counts:
        assert count == 1, f"duplicate reading for metric {metric}: {count} rows"
