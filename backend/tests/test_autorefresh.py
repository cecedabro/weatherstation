"""Tests for auto-refresh on / (SPEC 10.10).

SPEC 10.10: The current conditions on `/` refresh every 60 s through HTMX from
            `GET /partials/current` (an HTML fragment) without a full page reload.

The root element of `_current.html` carries:
  hx-get="/partials/current" hx-trigger="every 60s" hx-swap="outerHTML"
so it keeps refreshing after each swap.
"""


def test_root_has_htmx_id_on_home(client):
    """SPEC 10.10: the root wrapper div on / has id='current-conditions'."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'id="current-conditions"' in resp.text


def test_root_has_hx_get_on_home(client):
    """SPEC 10.10: the root wrapper div on / carries hx-get="/partials/current"."""
    resp = client.get("/")
    assert 'hx-get="/partials/current"' in resp.text


def test_root_has_hx_trigger_on_home(client):
    """SPEC 10.10: the root wrapper div on / carries hx-trigger="every 60s"."""
    resp = client.get("/")
    assert 'hx-trigger="every 60s"' in resp.text


def test_root_has_hx_swap_on_home(client):
    """SPEC 10.10: the root wrapper div on / carries hx-swap="outerHTML"."""
    resp = client.get("/")
    assert 'hx-swap="outerHTML"' in resp.text


def test_root_has_all_htmx_attrs_on_home(client):
    """SPEC 10.10: all three HTMX attributes appear together on the root div."""
    resp = client.get("/")
    text = resp.text
    assert 'id="current-conditions"' in text
    assert 'hx-get="/partials/current"' in text
    assert 'hx-trigger="every 60s"' in text
    assert 'hx-swap="outerHTML"' in text


# ---------------------------------------------------------------------------
# Tests: the fragment /partials/current also carries the HTMX attributes
# ---------------------------------------------------------------------------


def test_fragment_has_hx_get(client):
    """SPEC 10.10: /partials/current fragment has hx-get="/partials/current"."""
    resp = client.get("/partials/current")
    assert resp.status_code == 200
    assert 'hx-get="/partials/current"' in resp.text


def test_fragment_has_hx_trigger(client):
    """SPEC 10.10: /partials/current fragment has hx-trigger="every 60s"."""
    resp = client.get("/partials/current")
    assert 'hx-trigger="every 60s"' in resp.text


def test_fragment_has_hx_swap(client):
    """SPEC 10.10: /partials/current fragment has hx-swap="outerHTML"."""
    resp = client.get("/partials/current")
    assert 'hx-swap="outerHTML"' in resp.text


def test_fragment_has_htmx_id(client):
    """SPEC 10.10: /partials/current fragment has id='current-conditions'."""
    resp = client.get("/partials/current")
    assert 'id="current-conditions"' in resp.text


def test_fragment_has_all_htmx_attrs(client):
    """SPEC 10.10: all HTMX attributes are present on the fragment root."""
    resp = client.get("/partials/current")
    text = resp.text
    assert 'id="current-conditions"' in text
    assert 'hx-get="/partials/current"' in text
    assert 'hx-trigger="every 60s"' in text
    assert 'hx-swap="outerHTML"' in text
