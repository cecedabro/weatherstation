"""Tests for GET /api/v1/export.csv per SPEC 10.7.

SPEC 10.7: `GET /api/v1/export.csv?node=&metric=&from=&to=` downloads raw
readings as CSV with the header `ts,node_id,metric,value`. Same date
validation as `/series` (bad dates -> 400).
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Node, Reading


def _now() -> datetime:
    return datetime.now(UTC)


def _make_batch(
    db: Session,
    node_id: str,
    node_type: str,
    ts: datetime,
    metrics: dict[str, float],
    battery_v: float | None = None,
    rssi_dbm: int | None = None,
) -> Node:
    """Insert a node and its metric readings into the database."""
    node = db.execute(select(Node).where(Node.node_id == node_id)).scalar_one_or_none()
    if node is None:
        node = Node(
            node_id=node_id,
            node_type=node_type,
            first_seen=ts,
            last_seen=ts,
            last_battery_v=battery_v,
            last_rssi_dbm=rssi_dbm,
        )
        db.add(node)
        db.flush()
    node.last_seen = ts
    node.last_battery_v = battery_v
    node.last_rssi_dbm = rssi_dbm
    for metric, value in metrics.items():
        reading = db.execute(
            select(Reading).where(
                (Reading.node_id == node_id)
                & (Reading.metric == metric)
                & (Reading.ts == ts)
            )
        ).scalar_one_or_none()
        if reading is None:
            reading = Reading(node_id=node_id, metric=metric, ts=ts, value=value)
            db.add(reading)
    db.flush()
    return node


@pytest.fixture()
def export_data(db: Session) -> Iterator[Session]:
    """Populate the database with data for export CSV tests."""
    base = _now() - timedelta(hours=2)

    # Weather node with readings at different times
    for i in range(5):
        ts = base + timedelta(minutes=10 * i)
        _make_batch(
            db,
            "export-weather",
            "weather",
            ts,
            {"temp_c": 15.0 + i, "humidity_pct": 60.0 + i},
            battery_v=3.8,
            rssi_dbm=-55,
        )

    # Soil node
    for i in range(3):
        ts = base + timedelta(minutes=20 * i)
        _make_batch(
            db,
            "export-soil",
            "soil",
            ts,
            {"soil_moisture_pct": 30.0 + i * 5, "soil_temp_c": 12.0 + i},
            battery_v=3.9,
            rssi_dbm=-70,
        )

    yield db


# ---------------------------------------------------------------------------
# Content type and header
# ---------------------------------------------------------------------------


def test_export_csv_content_type(client):
    """SPEC 10.7: response is text/csv."""
    resp = client.get("/api/v1/export.csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]


def test_export_csv_content_disposition(client):
    """SPEC 10.7: Content-Disposition header is attachment."""
    resp = client.get("/api/v1/export.csv")
    assert resp.status_code == 200
    cd = resp.headers["content-disposition"]
    assert "attachment" in cd


def test_export_csv_header_row(client):
    """SPEC 10.7: CSV has the header `ts,node_id,metric,value`."""
    resp = client.get("/api/v1/export.csv")
    assert resp.status_code == 200
    body = resp.text
    lines = body.strip().split("\n")
    assert lines[0] == "ts,node_id,metric,value"


# ---------------------------------------------------------------------------
# Data rows
# ---------------------------------------------------------------------------


def test_export_csv_body_has_data(client, db: Session, export_data):
    """SPEC 10.7: body contains rows with ts, node_id, metric, value."""
    resp = client.get("/api/v1/export.csv")
    assert resp.status_code == 200
    body = resp.text
    lines = body.strip().split("\n")
    # Skip header row
    assert len(lines) > 1


def test_export_csv_iso8601_timestamps(client, db: Session, export_data):
    """SPEC 10.7: timestamps are ISO-8601 UTC."""
    resp = client.get("/api/v1/export.csv")
    assert resp.status_code == 200
    body = resp.text
    lines = body.strip().split("\n")
    for line in lines[1:]:
        parts = line.split(",", 3)
        ts = parts[0]
        # Must be parseable as ISO-8601
        datetime.fromisoformat(ts.replace("Z", "+00:00"))


def test_export_csv_time_ordered(client, db: Session, export_data):
    """SPEC 10.7: rows are time-ordered by timestamp."""
    resp = client.get("/api/v1/export.csv")
    assert resp.status_code == 200
    body = resp.text
    lines = body.strip().split("\n")
    timestamps = []
    for line in lines[1:]:
        ts = line.split(",")[0]
        timestamps.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
    for i in range(1, len(timestamps)):
        assert timestamps[i] >= timestamps[i - 1]


def test_export_csv_includes_all_metrics(client, db: Session, export_data):
    """SPEC 10.7: without metric filter, all metrics appear."""
    resp = client.get("/api/v1/export.csv")
    assert resp.status_code == 200
    body = resp.text
    lines = body.strip().split("\n")
    metrics_found: set[str] = set()
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) >= 3:
            metrics_found.add(parts[2])
    assert "temp_c" in metrics_found
    assert "humidity_pct" in metrics_found
    assert "soil_moisture_pct" in metrics_found
    assert "soil_temp_c" in metrics_found


def test_export_csv_node_id_in_rows(client, db: Session, export_data):
    """SPEC 10.7: each row contains the correct node_id."""
    resp = client.get("/api/v1/export.csv")
    assert resp.status_code == 200
    body = resp.text
    lines = body.strip().split("\n")
    node_ids: set[str] = set()
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) >= 2:
            node_ids.add(parts[1])
    assert "export-weather" in node_ids
    assert "export-soil" in node_ids


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def test_export_csv_filter_by_node(client, db: Session, export_data):
    """SPEC 10.7: ?node= filters to only that node."""
    resp = client.get("/api/v1/export.csv?node=export-weather")
    assert resp.status_code == 200
    body = resp.text
    lines = body.strip().split("\n")
    node_ids: set[str] = set()
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) >= 2:
            node_ids.add(parts[1])
    assert node_ids == {"export-weather"}


def test_export_csv_filter_by_metric(client, db: Session, export_data):
    """SPEC 10.7: ?metric= filters to only that metric."""
    resp = client.get("/api/v1/export.csv?metric=temp_c")
    assert resp.status_code == 200
    body = resp.text
    lines = body.strip().split("\n")
    metrics_found: set[str] = set()
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) >= 3:
            metrics_found.add(parts[2])
    assert metrics_found == {"temp_c"}


def test_export_csv_filter_by_node_and_metric(client, db: Session, export_data):
    """SPEC 10.7: ?node= and ?metric= together filter correctly."""
    resp = client.get("/api/v1/export.csv?node=export-soil&metric=soil_moisture_pct")
    assert resp.status_code == 200
    body = resp.text
    lines = body.strip().split("\n")
    for line in lines[1:]:
        parts = line.split(",")
        assert parts[1] == "export-soil"
        assert parts[2] == "soil_moisture_pct"


def test_export_csv_empty_when_no_match(client, db: Session, export_data):
    """SPEC 10.7: unknown node returns just the header."""
    resp = client.get("/api/v1/export.csv?node=nonexistent")
    assert resp.status_code == 200
    body = resp.text
    lines = body.strip().split("\n")
    assert len(lines) == 1
    assert lines[0] == "ts,node_id,metric,value"


def test_export_csv_empty_when_metric_not_found(client, db: Session, export_data):
    """SPEC 10.7: unknown metric returns just the header."""
    resp = client.get("/api/v1/export.csv?metric=nonexistent_metric")
    assert resp.status_code == 200
    body = resp.text
    lines = body.strip().split("\n")
    assert len(lines) == 1
    assert lines[0] == "ts,node_id,metric,value"


# ---------------------------------------------------------------------------
# Date validation (same as /series)
# ---------------------------------------------------------------------------


def test_export_csv_bad_from_returns_400(client):
    """SPEC 10.7: non-RFC3339 from date returns 400."""
    resp = client.get("/api/v1/export.csv?from=not-a-date")
    assert resp.status_code == 400


def test_export_csv_bad_to_returns_400(client):
    """SPEC 10.7: non-RFC3339 to date returns 400."""
    resp = client.get("/api/v1/export.csv?to=gibberish")
    assert resp.status_code == 400


def test_export_csv_valid_date_range(client, db: Session, export_data):
    """SPEC 10.7: valid from/to dates filter the data."""
    now = _now()
    base = now - timedelta(hours=2)
    from_str = (base + timedelta(minutes=20)).isoformat()
    to_str = (base + timedelta(minutes=40)).isoformat()
    resp = client.get(
        f"/api/v1/export.csv?from={from_str}&to={to_str}"
    )
    assert resp.status_code == 200
    body = resp.text
    lines = body.strip().split("\n")
    timestamps = []
    for line in lines[1:]:
        ts = line.split(",")[0]
        timestamps.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
    for ts in timestamps:
        assert base + timedelta(minutes=20) <= ts <= base + timedelta(minutes=40)


def test_export_csv_combined_filters(client, db: Session, export_data):
    """SPEC 10.7: node, metric, from, and to all work together."""
    now = _now()
    base = now - timedelta(hours=2)
    from_str = (base + timedelta(minutes=10)).isoformat()
    to_str = (base + timedelta(minutes=30)).isoformat()
    resp = client.get(
        f"/api/v1/export.csv?node=export-weather&metric=temp_c&from={from_str}&to={to_str}"
    )
    assert resp.status_code == 200
    body = resp.text
    lines = body.strip().split("\n")
    for line in lines[1:]:
        parts = line.split(",")
        assert parts[1] == "export-weather"
        assert parts[2] == "temp_c"
        ts = datetime.fromisoformat(parts[0].replace("Z", "+00:00"))
        assert ts >= datetime.fromisoformat(from_str.replace("Z", "+00:00"))
        assert ts <= datetime.fromisoformat(to_str.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# Row count verification
# ---------------------------------------------------------------------------


def test_export_csv_row_count_matches_db(client, db: Session, export_data):
    """SPEC 10.7: the number of data rows matches what the DB would return."""
    resp = client.get("/api/v1/export.csv")
    assert resp.status_code == 200
    body = resp.text
    lines = body.strip().split("\n")
    csv_rows = len(lines) - 1  # subtract header

    # Count rows in the database
    all_readings = db.execute(select(Reading)).scalars().all()
    assert csv_rows == len(all_readings)


def test_export_csv_value_precision(client, db: Session, export_data):
    """SPEC 10.7: numeric values are present and parseable as floats."""
    resp = client.get("/api/v1/export.csv")
    assert resp.status_code == 200
    body = resp.text
    lines = body.strip().split("\n")
    for line in lines[1:]:
        parts = line.split(",")
        assert len(parts) == 4, f"Expected 4 columns, got {len(parts)}: {line}"
        # value should be parseable as float
        float(parts[3])
