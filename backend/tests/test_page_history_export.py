"""Tests for the download export form on GET /history (T37).

VERIFIES PLAN T37:
- Plain GET form (node, metric including "all", from/to as <input type="date">)
  submits to /api/v1/export.csv.
"""


# ---------------------------------------------------------------------------
# Form structure
# ---------------------------------------------------------------------------


def test_export_form_exists(client):
    """The export form is present on the history page."""
    resp = client.get("/history")
    assert resp.status_code == 200
    assert "Export Data" in resp.text
    assert 'action="/api/v1/export.csv"' in resp.text
    assert 'method="get"' in resp.text


def test_export_form_method(client):
    """The export form uses method=GET."""
    resp = client.get("/history")
    assert 'method="get"' in resp.text


def test_export_form_action(client):
    """The export form action is /api/v1/export.csv."""
    resp = client.get("/history")
    assert 'action="/api/v1/export.csv"' in resp.text


def test_export_form_node_select(client, multi_node_history):
    """The export form has a node <select> with options for all known nodes."""
    resp = client.get("/history")
    assert '<select name="node"' in resp.text or '<select name="node"' in resp.text
    assert '<option value="">' in resp.text or '<option value="">' in resp.text


def test_export_form_metric_select(client):
    """The export form has a metric <select> with an 'all' option."""
    resp = client.get("/history")
    assert '<select name="metric"' in resp.text or '<select name="metric"' in resp.text
    assert "All metrics" in resp.text


def test_export_form_from_date(client):
    """The export form has a <input type=\"date\"> for from."""
    resp = client.get("/history")
    assert 'type="date"' in resp.text
    assert 'name="from"' in resp.text
    assert 'id="export-from"' in resp.text


def test_export_form_to_date(client):
    """The export form has a <input type=\"date\"> for to."""
    resp = client.get("/history")
    assert 'name="to"' in resp.text
    assert 'id="export-to"' in resp.text


def test_export_form_submit_button(client):
    """The export form has a submit button."""
    resp = client.get("/history")
    assert "<button" in resp.text
    assert "Download CSV" in resp.text


# ---------------------------------------------------------------------------
# Node options in form
# ---------------------------------------------------------------------------


def test_export_form_shows_weather_nodes(client, multi_node_history):
    """The export form lists weather nodes as options."""
    resp = client.get("/history")
    assert "weather-garden" in resp.text
    assert "weather-terrace" in resp.text


def test_export_form_all_nodes_option_selected_by_default(client, multi_node_history):
    """The 'All nodes' option is the first in the export node select."""
    resp = client.get("/history")
    node_select_start = resp.text.find('id="export-node"')
    assert node_select_start != -1
    node_select_section = resp.text[node_select_start : node_select_start + 500]
    # First <option> should be the "All nodes" one
    first_option_start = node_select_section.find("<option")
    second_option_start = node_select_section.find("<option", first_option_start + 1)
    first_option = node_select_section[first_option_start:second_option_start]
    assert 'value=""' in first_option


# ---------------------------------------------------------------------------
# Metric options in form
# ---------------------------------------------------------------------------


def test_export_form_metric_has_all_option(client):
    """The metric select includes an empty/all option."""
    resp = client.get("/history")
    metric_select_start = resp.text.find('name="metric"')
    assert metric_select_start != -1
    metric_section = resp.text[metric_select_start : metric_select_start + 1000]
    first_option_start = metric_section.find("<option")
    second_option_start = metric_section.find("<option", first_option_start + 1)
    first_option = metric_section[first_option_start:second_option_start]
    assert 'value=""' in first_option or "All" in first_option


def test_export_form_metric_has_temp_option(client):
    """The metric select includes temp_c."""
    resp = client.get("/history")
    assert 'value="temp_c"' in resp.text


def test_export_form_metric_has_humidity_option(client):
    """The metric select includes humidity_pct."""
    resp = client.get("/history")
    assert 'value="humidity_pct"' in resp.text


def test_export_form_metric_has_rain_option(client):
    """The metric select includes rain_mm."""
    resp = client.get("/history")
    assert 'value="rain_mm"' in resp.text


def test_export_form_metric_has_pressure_option(client):
    """The metric select includes pressure_hpa."""
    resp = client.get("/history")
    assert 'value="pressure_hpa"' in resp.text


# ---------------------------------------------------------------------------
# Form labels
# ---------------------------------------------------------------------------


def test_export_form_has_labels(client):
    """The export form has labels for all fields."""
    resp = client.get("/history")
    assert (
        '<label for="export-node">Node</label>' in resp.text
        or 'label for="export-node"' in resp.text
    )
    assert (
        '<label for="export-metric">Metric</label>' in resp.text
        or 'label for="export-metric"' in resp.text
    )
    assert (
        '<label for="export-from">From</label>' in resp.text
        or 'label for="export-from"' in resp.text
    )
    assert '<label for="export-to">To</label>' in resp.text or 'label for="export-to"' in resp.text


# ---------------------------------------------------------------------------
# Date input type verification
# ---------------------------------------------------------------------------


def test_export_form_from_is_date_input(client):
    """The from field is an <input type=\"date\">."""
    resp = client.get("/history")
    form_section = resp.text[resp.text.find('action="/api/v1/export.csv"') :]
    assert (
        '<input type="date" name="from"' in form_section
        or '<input type="date" name="from" id="export-from"' in form_section
    )


def test_export_form_to_is_date_input(client):
    """The to field is an <input type=\"date\">."""
    resp = client.get("/history")
    form_section = resp.text[resp.text.find('action="/api/v1/export.csv"') :]
    assert (
        '<input type="date" name="to"' in form_section
        or '<input type="date" name="to" id="export-to"' in form_section
    )
