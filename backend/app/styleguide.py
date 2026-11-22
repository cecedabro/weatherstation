# ruff: noqa: E501  (template snippets read better on one line)
"""The component list behind /styleguide. Human-owned (docs/design.md).

Each example is real template code: the page renders it and shows the same code next to it, so what
you copy is exactly what you see. Add an example here whenever a component is added to ui.html.
"""

from datetime import UTC, datetime, timedelta

from markupsafe import Markup

from app.templating import env

EXAMPLES: list[tuple[str, str, str]] = [
    (
        "Layout",
        "Page head",
        '{% call ui.page_head("Tasks", "Jobs and reminders.") %}'
        '{{ ui.button("New task", variant="primary", icon="＋") }}{% endcall %}',
    ),
    ("Layout", "Card", '{% call ui.card("Soil", "🪴", "soil") %}<p>Any content.</p>{% endcall %}'),
    (
        "Layout",
        "Card tints",
        '<div class="grid">{% for t in ["sky","leaf","sun","soil","berry","water","stone"] %}'
        '{% call ui.card(t, tint=t) %}<p class="small muted">tint="{{ t }}"</p>{% endcall %}{% endfor %}</div>',
    ),
    (
        "Layout",
        "Link card",
        '{{ ui.link_card("/seeds", "Seed log", "What you sowed and where.", "🌱", "sun", meta="12 entries") }}',
    ),
    (
        "Layout",
        "Grids",
        '<div class="grid-3"><div class="stat">grid-3</div><div class="stat">…</div><div class="stat">…</div></div>',
    ),
    (
        "Data",
        "Stat tiles",
        '<div class="stats">{{ ui.stat("Temperature", 14.2, "°C", "🌡️", tint="sun") }}'
        '{{ ui.stat("Humidity", 81, "%", "💧", fmt="%.0f") }}{{ ui.stat("Rain", None, "mm", "🌧️", meta="no data") }}'
        '{{ ui.stat("Days to harvest", 46, icon="🍅", fmt="%d", big=True) }}</div>',
    ),
    (
        "Data",
        "Table",
        '{% call ui.table(["Day", "Min °C#", "Max °C#", "Status"]) %}'
        '<tr><td>Mon 3 Nov</td><td class="num">4.1</td><td class="num">11.8</td><td>{{ ui.chip("ok", "ok", dot=True) }}</td></tr>'
        '<tr class="row-alert"><td>Tue 4 Nov</td><td class="num">-1.2</td><td class="num">6.0</td><td>{{ ui.chip("frost", "bad", dot=True) }}</td></tr>'
        "{% endcall %}",
    ),
    (
        "Data",
        "Chart",
        '<div data-chart-group>{{ ui.seg_buttons([("24h","Day"),("7d","Week"),("30d","Month")], "7d") }}'
        '{{ ui.chart("Air temperature", [("weather-main","temp_c","Air"), ("weather-main","humidity_pct","Humidity")], unit="°C") }}</div>',
    ),
    (
        "Data",
        "Key / value",
        '{{ ui.kv([("Crop", "Tomato"), ("Sown", "12 Apr"), ("Bed", "Bed 3"), ("Notes", "")]) }}',
    ),
    ("Data", "Relative time", "<p>Updated {{ ui.when(yesterday) }} · hover for the exact time</p>"),
    ("Data", "Progress", '{{ ui.progress(62, "Growth") }}'),
    (
        "Data",
        "Timeline",
        '<ol class="timeline"><li class="timeline-item"><div class="timeline-date">12 Apr</div>Sown</li>'
        '<li class="timeline-item"><div class="timeline-date">20 Apr</div>Sprouted</li></ol>',
    ),
    (
        "Status",
        "Chips",
        '<div class="row">{{ ui.chip("ok", "ok") }}{{ ui.chip("info", "info") }}{{ ui.chip("warn", "warn") }}'
        '{{ ui.chip("bad", "bad") }}{{ ui.chip("off", "off") }}{{ ui.online(True) }}{{ ui.online(False) }}</div>',
    ),
    (
        "Status",
        "Urgency",
        '<div class="row">{% for u in ["low","normal","high","critical"] %}{{ ui.chip(u, urgency=u, dot=True) }}{% endfor %}</div>',
    ),
    (
        "Status",
        "Category swatches",
        '<div class="legend">{% for n in range(1, 9) %}<span class="legend-item">{{ ui.swatch(n) }}c{{ n }}</span>{% endfor %}</div>',
    ),
    (
        "Status",
        "Alerts",
        '<div class="alerts">{{ ui.alert("Frost warning", "Cover the beans tonight.", "bad", "❄️") }}'
        '{{ ui.alert("Water needed", "Bed 2 is at 18 %.", "warn", "💧") }}{{ ui.alert("Saved", kind="ok", icon="✓") }}</div>',
    ),
    (
        "Status",
        "Empty state",
        '{{ ui.empty("No tasks yet", "Add the first job for the garden.", "✅", "#", "New task") }}',
    ),
    (
        "Controls",
        "Buttons",
        '<div class="row">{{ ui.button("Save", variant="primary") }}{{ ui.button("Open map", variant="aqua") }}'
        '{{ ui.button("Default") }}{{ ui.button("Quiet", variant="quiet") }}{{ ui.button("Delete", variant="danger") }}'
        '{{ ui.button("Small", size="sm") }}{{ ui.button("✎", size="icon", attrs={"aria-label": "Edit"}) }}</div>',
    ),
    (
        "Controls",
        "Segmented links",
        '{{ ui.seg([("air","Air"),("soil","Soil"),("rain","Rain")], "soil", href_for, "Category") }}',
    ),
    (
        "Controls",
        "Tabs",
        '{{ ui.tabs([("#a","Open","✅",4),("#b","Done","☑️",12),("#c","All",None,None)], "#a") }}',
    ),
    (
        "Controls",
        "Form",
        '<form class="form"><div class="form-row">{{ ui.field("title", "Title", required=True, attrs={"placeholder": "Fix the compost bin"}) }}'
        '{{ ui.field("urgency", "Urgency", "select", "high", options=[("low","Low"),("normal","Normal"),("high","High"),("critical","Critical")]) }}'
        '{{ ui.field("deadline", "Deadline", "date") }}</div>{{ ui.field("notes", "Notes", "textarea", hint="Optional.") }}'
        '{{ ui.field("done", "Done", "checkbox") }}{{ ui.field("bad", "With an error", value="x", error="Too short.") }}'
        '<div class="form-actions">{{ ui.button("Cancel", variant="quiet") }}{{ ui.button("Save", type="submit", variant="primary") }}</div></form>',
    ),
    (
        "Controls",
        "Toolbar",
        '<div class="toolbar"><div class="search"><input class="input" type="search" aria-label="Search" placeholder="Search"></div>'
        '{{ ui.seg([("open","Open"),("done","Done")], "open", href_for, "Status") }}<span class="toolbar-spacer"></span>{{ ui.button("New", variant="primary", size="sm") }}</div>',
    ),
    (
        "Controls",
        "List",
        '<ul class="list">{% call ui.list_item("Fix the compost bin", [ui.chip("high", urgency="high"), "repair", "due in 3 days"], "🧰") %}'
        '{{ ui.button("Done", size="sm") }}{% endcall %}{{ ui.list_item("Finish the edging", ["build"], "🧱", done=True) }}</ul>',
    ),
    (
        "Controls",
        "Dialog",
        '{{ ui.button("Open dialog", attrs={"data-open": "demo-dialog"}) }}'
        '{% call ui.dialog("demo-dialog", "New find") %}<p>Any form goes here.</p>{% endcall %}',
    ),
    (
        "Map",
        "Map frame",
        '<div class="map"><div class="map-toolbar">{{ ui.button("Move", size="sm") }}{{ ui.button("Add bed", size="sm", variant="primary") }}</div>'
        '<div class="map-legend legend"><span class="legend-item">{{ ui.swatch(2) }}bed</span><span class="legend-item">{{ ui.swatch(1) }}sensor</span></div></div>',
    ),
]


def render_examples() -> list[dict[str, object]]:
    now = datetime.now(UTC)
    ctx = {"href_for": lambda v: f"?v={v}", "now": now, "yesterday": now - timedelta(days=1)}
    out: list[dict[str, object]] = []
    for group, name, code in EXAMPLES:
        html = env.from_string('{% import "ui.html" as ui %}' + code).render(**ctx)
        out.append({"group": group, "name": name, "code": code, "html": Markup(html)})  # nosec B704: our own template code
    return out
