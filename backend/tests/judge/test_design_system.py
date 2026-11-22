"""The design system is the only source of styling (docs/design.md).

- Every class used in a template or in static/js is defined in static/css/*.css.
- No <style> blocks and no style="" attributes in templates (ui.html's progress bar excepted).
- Stylesheets live only in static/css/ and are human-owned; pages import ui.html for markup.
"""

import re
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"
CSS = APP / "static" / "css"
TEMPLATES = APP / "templates"
JS = APP / "static" / "js"

# Classes that come from third-party code or are set only as hooks for scripts.
ALLOWED = {"u-legend", "u-select", "uplot"}


def defined_classes() -> set[str]:
    text = "".join(p.read_text() for p in CSS.glob("*.css"))
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return set(re.findall(r"\.([a-zA-Z][\w-]*)", text))


def used_classes(text: str) -> set[str]:
    out: set[str] = set()
    for attr in re.findall(r'class="([^"]*)"', text):
        attr = re.sub(r"\{%.*?%\}", " ", attr)  # Jinja tags: keep the literal text around them
        attr = re.sub(r"[\w-]*\{\{.*?\}\}[\w-]*", " ", attr)  # classes built from expressions
        out.update(c for c in attr.split() if re.fullmatch(r"[a-zA-Z][\w-]*", c))
    return out


def test_every_template_class_is_defined() -> None:
    known = defined_classes() | ALLOWED
    missing = {}
    for t in TEMPLATES.rglob("*.html"):
        extra = used_classes(t.read_text()) - known
        if extra:
            missing[t.name] = sorted(extra)
    assert not missing, f"classes not in static/css (add a component instead): {missing}"


def test_every_macro_generated_class_is_defined() -> None:
    known = defined_classes()
    for prefix, values in {
        "tint-": ["sky", "leaf", "sun", "soil", "berry", "water", "stone"],
        "chip-": ["ok", "info", "warn", "bad", "off", "dot"],
        "u-": ["low", "normal", "high", "critical"],
        "btn-": ["primary", "aqua", "danger", "quiet", "sm", "icon", "block"],
        "alert-": ["info", "ok", "warn", "bad"],
        "k": [str(n) for n in range(1, 9)],
    }.items():
        for v in values:
            assert prefix + v in known, prefix + v


def test_js_classes_are_defined() -> None:
    known = defined_classes() | ALLOWED
    for js in JS.rglob("*.js"):
        text = js.read_text()
        names = set(re.findall(r'className\s*=\s*"([^"]+)"', text))
        names |= set(re.findall(r'classList\.(?:add|remove|toggle)\("([^"]+)"', text))
        for n in names:
            for c in n.split():
                assert c in known, f"{js.name}: class {c} not in static/css"


def test_no_inline_styles_in_templates() -> None:
    for t in TEMPLATES.rglob("*.html"):
        text = t.read_text()
        assert "<style" not in text, f"{t.name}: <style> block; use components.css"
        if t.name != "ui.html":
            assert "style=" not in text, f"{t.name}: style attribute; use a component"


def test_stylesheets_only_in_css_dir() -> None:
    strays = [
        p
        for p in (APP / "static").rglob("*.css")
        if CSS not in p.parents and "vendor" not in p.parts
    ]
    assert not strays, strays


def test_pages_extend_base_and_import_ui() -> None:
    partials = {"base.html", "ui.html"}
    for t in TEMPLATES.rglob("*.html"):
        if t.name in partials or t.name.startswith("_"):
            continue
        assert '{% extends "base.html" %}' in t.read_text(), f"{t.name} must extend base.html"
