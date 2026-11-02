"""Accessibility tests (SPEC 10.12 — T41).

Verifies that:
- Every chart element has role="img" and an aria-label naming metric and node.
- Pages with charts (/, /weather, /soil/<node>) have a <noscript> note.
- Decorative emoji elements have aria-hidden="true".
- Every form control has an associated <label>.
"""

from html.parser import HTMLParser

import pytest

PAGES_WITH_CHARTS = ["/", "/weather"]


class _EmojiChecker(HTMLParser):
    """Collect all elements that contain emoji-like content."""

    EMOJI_RE = __import__("re").compile(r"[\U0001F300-\U0001F9FF\u2600-\u27BF\uFE0F\uFE0F]")

    def __init__(self):
        super().__init__()
        self.emoji_elements = []
        self._current_attrs = {}
        self._current_tag = ""

    def handle_starttag(self, tag, attrs):
        self._current_tag = tag
        self._current_attrs = dict(attrs)

    def handle_endtag(self, tag):
        self._current_tag = ""
        self._current_attrs = {}

    def handle_data(self, data):
        text = data.strip()
        if text and self._current_tag and self.EMOJI_RE.search(text):
            self.emoji_elements.append({"tag": self._current_tag, "attrs": self._current_attrs})


class _LabelCollector(HTMLParser):
    """Collect all <label for='...'> values from the page."""

    def __init__(self):
        super().__init__()
        self.label_fors = set()

    def handle_starttag(self, tag, attrs):
        if tag == "label":
            for attr_name, attr_val in attrs:
                if attr_name == "for" and attr_val:
                    self.label_fors.add(attr_val)


class _FormControlChecker(HTMLParser):
    """Check that every form control has an associated <label>."""

    FORM_CONTROLS = {"input", "select", "textarea"}

    def __init__(self, label_fors):
        super().__init__()
        self.label_fors = label_fors
        self.unlabeled = []
        self._in_form = False

    def handle_starttag(self, tag, attrs):
        if tag == "form":
            self._in_form = True
        if self._in_form and tag in self.FORM_CONTROLS:
            for attr_name, attr_val in attrs:
                if attr_name == "id" and attr_val and attr_val not in self.label_fors:
                    self.unlabeled.append(
                        f"<{tag} id={attr_val!r}> found without <label for={attr_val!r}>"
                    )

    def handle_endtag(self, tag):
        if tag == "form":
            self._in_form = False


def _check_aria_hidden_on_emojis(text):
    """Return a list of emoji elements missing aria-hidden='true'."""
    checker = _EmojiChecker()
    checker.feed(text)
    missing = []
    for el in checker.emoji_elements:
        ah = el.get("attrs", {}).get("aria-hidden")
        if ah is None or ah != "true":
            missing.append(el)
    return missing


def _check_form_labels(text):
    """Return a list of form controls missing labels."""
    label_collector = _LabelCollector()
    label_collector.feed(text)
    checker = _FormControlChecker(label_collector.label_fors)
    checker.feed(text)
    return checker.unlabeled


def test_chart_elements_have_role_and_aria_label(client, db):
    """Every <div data-chart> must have role='img' and an aria-label."""
    # / and /weather render chart divs
    for url in PAGES_WITH_CHARTS:
        resp = client.get(url)
        assert resp.status_code == 200
        parser = HTMLParser()
        parser.feed(resp.text)
        # use html.parser directly to find data-chart divs
        import html.parser

        class _ChartFinder(html.parser.HTMLParser):
            def __init__(self):
                super().__init__()
                self.charts = []
                self._attrs = {}

            def handle_starttag(self, tag, attrs):
                if tag == "div":
                    a = dict(attrs)
                    if "data-chart" in a:
                        self.charts.append(a)

        finder = _ChartFinder()
        finder.feed(resp.text)
        for chart in finder.charts:
            assert "role" in chart and chart["role"] == "img", f"Chart on {url} missing role='img'"
            assert "aria-label" in chart and chart["aria-label"].strip(), (
                f"Chart on {url} missing aria-label"
            )
            # aria-label should name metric and node
            label = chart["aria-label"].lower()
            assert "chart" in label, f"Chart aria-label on {url} should contain 'chart': {label}"


def test_noscript_on_chart_pages(client, db):
    """Pages with charts (/, /weather) must have a <noscript> block."""
    for url in PAGES_WITH_CHARTS:
        resp = client.get(url)
        assert resp.status_code == 200
        assert "<noscript" in resp.text, f"{url} missing <noscript> block"
        assert "javascript" in resp.text.lower() or "js" in resp.text.lower(), (
            f"{url} <noscript> should mention JavaScript"
        )


def _soil_detail_url():
    """Return a URL that hits /soil/<node_id> with a valid soil node."""
    from sqlalchemy import text

    from app.db import engine

    with engine.connect() as conn:
        r = conn.execute(text("SELECT node_id FROM node LIMIT 1")).scalar()
        conn.commit()
        if r:
            return f"/soil/{r}"
    return None


def test_noscript_on_soil_detail(client, db):
    """/soil/<node_id> must have a <noscript> block when rendered."""
    url = _soil_detail_url()
    if url is None:
        pytest.skip("No soil nodes in database")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "<noscript" in resp.text, f"{url} missing <noscript> block"


def test_decorative_emojis_have_aria_hidden(client, db):
    """Decorative emoji elements must have aria-hidden='true'."""
    all_pages = ["/", "/weather", "/soil", "/history", "/about"]
    for url in all_pages:
        resp = client.get(url)
        assert resp.status_code == 200
        missing = _check_aria_hidden_on_emojis(resp.text)
        assert missing == [], (
            f"{url} emojis missing aria-hidden='true': {[e['tag'] for e in missing]}"
        )


def test_form_controls_have_labels(client, db):
    """Every form control must have an associated <label>."""
    pages = ["/", "/weather", "/soil", "/history", "/about"]
    for url in pages:
        resp = client.get(url)
        assert resp.status_code == 200
        unlabeled = _check_form_labels(resp.text)
        assert unlabeled == [], f"{url} unlabeled form controls: {unlabeled}"


def test_soil_detail_chart_aria_label(client, db):
    """/soil/<node_id> chart divs must have role='img' and aria-label."""
    url = _soil_detail_url()
    if url is None:
        pytest.skip("No soil nodes in database")
    resp = client.get(url)
    assert resp.status_code == 200

    class _ChartFinder(HTMLParser):
        def __init__(self):
            super().__init__()
            self.charts = []
            self._attrs = {}

        def handle_starttag(self, tag, attrs):
            if tag == "div":
                a = dict(attrs)
                if "data-chart" in a:
                    self.charts.append(a)

    finder = _ChartFinder()
    finder.feed(resp.text)
    for chart in finder.charts:
        assert "role" in chart and chart["role"] == "img", f"Chart on {url} missing role='img'"
        assert "aria-label" in chart and chart["aria-label"].strip(), (
            f"Chart on {url} missing aria-label"
        )
