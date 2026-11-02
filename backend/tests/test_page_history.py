"""Tests for GET /history page (T35).

SPEC 10.5: The history page shows a table of daily summaries for the last 30
days of the first weather node. Columns: date, min/max/avg °C, rain mm, humidity
%. Table rows are newest first. When multiple nodes exist a node picker is
shown (select with ?node=). An empty state is shown when no data is available.
"""

from datetime import timedelta

from sqlalchemy.orm import Session

from conftest import _make_daily, _now

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEG = "&#x00B0;"

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_history_page_loads(client):
    """GET /history returns 200."""
    resp = client.get("/history")
    assert resp.status_code == 200


def test_history_page_content_type(client):
    """GET /history returns HTML."""
    resp = client.get("/history")
    assert "text/html" in resp.headers["content-type"]


def test_history_page_shows_section_header(client, history_data):
    """The page has a Daily History section header."""
    resp = client.get("/history")
    assert "Daily History" in resp.text


def test_history_page_empty_state(client):
    """An empty state is shown when no history data is available."""
    resp = client.get("/history")
    assert "No History Yet" in resp.text
    assert "Waiting for the weather node" in resp.text


def test_history_page_shows_table_dates(client, history_data):
    """Daily dates appear in the table."""
    resp = client.get("/history")
    # Dates from the last 10 days should appear (day_offset=0 = today, 9 = 9 days ago)
    now = _now()
    for i in range(10):
        day = (now - timedelta(days=i)).strftime("%-d %b %Y")
        assert day in resp.text, f"Expected date {day} not found in response"


def test_history_page_newest_first(client, history_data):
    """Table rows are ordered newest first."""
    resp = client.get("/history")
    # Count table rows and verify ordering using string operations (no bs4)
    tbody_start = resp.text.find("<tbody>")
    tbody_end = resp.text.find("</tbody>") + len("</tbody>")
    tbody = resp.text[tbody_start:tbody_end]
    rows = tbody.split("<tr>")
    # Remove header/empty first element
    rows = [r for r in rows if "<td>" in r]
    assert len(rows) == 10, f"Expected 10 rows, got {len(rows)}"

    # Extract dates from each row and verify newest first
    import re

    dates = []
    for row in rows:
        match = re.search(r"(\d{1,2} \w{3} \d{4})", row)
        if match:
            dates.append(match.group(1))

    # Parse dates and verify descending order
    from datetime import date as date_cls

    month_map = {
        "Jan": 1,
        "Feb": 2,
        "Mar": 3,
        "Apr": 4,
        "May": 5,
        "Jun": 6,
        "Jul": 7,
        "Aug": 8,
        "Sep": 9,
        "Oct": 10,
        "Nov": 11,
        "Dec": 12,
    }
    parsed = []
    for d in dates:
        parts = d.split()
        day = int(parts[0])
        month = month_map[parts[1]]
        year = int(parts[2])
        parsed.append(date_cls(year, month, day))
    assert parsed == sorted(parsed, reverse=True), "Dates should be newest first"


def test_history_page_min_temp(client, history_data):
    """Temperature min values appear in the table."""
    resp = client.get("/history")
    # 9 days ago: temp was 15.0 + 0 = 15.0 (the lowest)
    assert f"15.0{DEG}" in resp.text


def test_history_page_max_temp(client, history_data):
    """Temperature max values appear in the table."""
    resp = client.get("/history")
    # 0 days ago: temp was 15.0 + 9 = 24.0 (the highest, only one reading per day)
    assert f"24.0{DEG}" in resp.text


def test_history_page_avg_temp(client, history_data):
    """Temperature avg values appear in the table (same as min/max with one reading)."""
    resp = client.get("/history")
    assert f"15.0{DEG}" in resp.text
    assert f"24.0{DEG}" in resp.text


def test_history_page_rain_total(client, history_data):
    """Rain total (mm) appears in the table."""
    resp = client.get("/history")
    # Day 9 (oldest): rain = 2.0 + 0 = 2.0 mm
    assert "2.0 mm" in resp.text


def test_history_page_humidity_avg(client, history_data):
    """Humidity average appears in the table."""
    resp = client.get("/history")
    # Day 9 (oldest): humidity = 55.0 + 0*2 = 55%
    assert "55%" in resp.text


def test_history_page_node_selector_hidden_single_node(client, history_data):
    """Node picker is not shown when there's only one weather node."""
    resp = client.get("/history")
    # The node selector form should not exist
    assert "node-selector" not in resp.text


def test_history_page_node_selector_visible_multiple_nodes(client, multi_node_history):
    """Node picker is shown when multiple weather nodes exist."""
    resp = client.get("/history")
    assert 'class="node-selector"' in resp.text
    assert "weather-garden" in resp.text
    assert "weather-terrace" in resp.text


def test_history_page_node_picker_select(client, multi_node_history):
    """Node picker renders <select> with option elements."""
    resp = client.get("/history")
    assert "<select" in resp.text
    assert "<option" in resp.text


def test_history_page_node_param(client, multi_node_history):
    """?node= selects a specific node for the history view."""
    resp = client.get("/history?node=weather-terrace")
    assert resp.status_code == 200
    assert "weather-terrace" in resp.text


def test_history_page_nav_active(client, history_data):
    """The 'History' nav link is marked as active."""
    resp = client.get("/history")
    assert 'href="/history" aria-current="page" class="nav-link active"' in resp.text


def test_history_page_shows_node_id(client, history_data):
    """The node ID is displayed in the page."""
    resp = client.get("/history")
    assert "weather-main" in resp.text


def test_history_page_zero_rain(client, db: Session):
    """Days with no rain show 0.0 mm."""
    _make_daily(
        db,
        "weather-main",
        "weather",
        0,
        {
            "temp_c": 20.0,
            "humidity_pct": 60.0,
            "rain_mm": 0.0,
            "pressure_hpa": 1013.0,
        },
    )
    resp = client.get("/history")
    assert "0.0 mm" in resp.text
