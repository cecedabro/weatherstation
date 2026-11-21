/* Garden charts: draws every [data-chart] with uPlot from /api/v1/series. Human-owned (docs/design.md).
   Markup comes from the ui.chart() macro:
     data-series='[["node","metric","label"], ...]'  data-kind="line|bar|area"  data-unit  data-range  data-height
   data-x="hour": compare days. Each series is [node, metric, label, "YYYY-MM-DD"]; the x axis is the hour
   of day (0–23, UTC) and each day is drawn as its own line.
   Range buttons: any [data-range] button inside the same [data-chart-group] (or the page when there is none)
   switches every chart in that group. Optional data-from/data-to on the plot (ISO) override the range.
   Colours come from the CSS tokens --c1..--c8, so light/dark follows the theme. Needs vendor/uPlot. */
(function () {
  "use strict";
  var RANGES = { "24h": [24, "5m"], "7d": [168, "1h"], "30d": [720, "1h"], "90d": [2160, "1d"], "365d": [8760, "1d"] };
  var charts = [];

  function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function color(i) { return css("--c" + ((i % 8) + 1)) || "#0a84ff"; }

  function window_(el) {
    if (el.dataset.from && el.dataset.to) {
      var span = (new Date(el.dataset.to) - new Date(el.dataset.from)) / 3600000;
      return { from: el.dataset.from, to: el.dataset.to, step: span <= 48 ? "5m" : span <= 24 * 45 ? "1h" : "1d" };
    }
    var r = RANGES[el.dataset.range] || RANGES["7d"], now = new Date();
    return { from: new Date(now - r[0] * 3600000).toISOString(), to: now.toISOString(), step: r[1] };
  }

  function fetchSeries(node, metric, w) {
    var q = new URLSearchParams({ node: node, metric: metric, from: w.from, to: w.to, step: w.step });
    return fetch("/api/v1/series?" + q).then(function (r) { return r.ok ? r.json() : []; }).catch(function () { return []; });
  }

  /* Align several [{ts,value}] lists on one time axis (seconds). */
  function join(lists) {
    var xs = {}, i, j;
    for (i = 0; i < lists.length; i++) for (j = 0; j < lists[i].length; j++) xs[Date.parse(lists[i][j].ts) / 1000] = 1;
    var x = Object.keys(xs).map(Number).sort(function (a, b) { return a - b; });
    var idx = {}; x.forEach(function (t, k) { idx[t] = k; });
    var out = [x];
    for (i = 0; i < lists.length; i++) {
      var ys = new Array(x.length).fill(null);
      for (j = 0; j < lists[i].length; j++) ys[idx[Date.parse(lists[i][j].ts) / 1000]] = lists[i][j].value;
      out.push(ys);
    }
    return out;
  }

  function fmt(v, unit) { return v == null ? "—" : (Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(1)) + (unit ? " " + unit : ""); }

  function tooltip(c) {
    var tip = document.createElement("div");
    tip.className = "chart-tip hidden";
    c.el.appendChild(tip);
    return function (u) {
      var i = u.cursor.idx;
      if (i == null) { tip.classList.add("hidden"); return; }
      var head = c.hours ? u.data[0][i] + ":00 UTC" : new Date(u.data[0][i] * 1000).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
      var rows = [head];
      for (var s = 1; s < u.series.length; s++) rows.push(u.series[s].label + ": " + fmt(u.data[s][i], c.unit));
      tip.textContent = "";
      rows.forEach(function (r, k) { var d = document.createElement("div"); if (!k) d.className = "muted"; d.textContent = r; tip.appendChild(d); });
      tip.classList.remove("hidden");
      var left = Math.min(u.cursor.left + 14, u.over.clientWidth - tip.offsetWidth);
      tip.style.left = Math.max(0, left) + "px";
      tip.style.top = Math.max(0, u.cursor.top - tip.offsetHeight - 8) + "px";
    };
  }

  function draw(c, data) {
    if (c.plot) { c.plot.destroy(); c.plot = null; }
    c.el.textContent = "";
    var has = data.slice(1).some(function (ys) { return ys.some(function (v) { return v != null; }); });
    c.el.classList.toggle("is-empty", !has);
    if (!has) { c.el.style.height = c.height + "px"; c.el.textContent = "No readings in this period"; return; }
    c.el.style.height = "";
    var axis = css("--chart-axis"), grid = css("--chart-grid"), bars = c.kind === "bar" && uPlot.paths && uPlot.paths.bars;
    var series = [{}].concat(c.series.map(function (s, i) {
      var col = color(i);
      return { label: s[2], stroke: col, width: 2, spanGaps: false, points: { show: false },
               fill: c.kind === "line" ? undefined : col + "33", paths: bars ? uPlot.paths.bars({ size: [0.7, 24] }) : undefined };
    }));
    var opts = {
      width: c.el.clientWidth || 600, height: c.height, legend: { show: false },
      cursor: { drag: { x: false, y: false }, points: { size: 8 } },
      scales: { x: { time: !c.hours } },
      axes: [{ stroke: axis, grid: { stroke: grid, width: 1 }, ticks: { show: false } },
             { stroke: axis, grid: { stroke: grid, width: 1 }, ticks: { show: false }, size: 48,
               values: function (u, vals) { return vals.map(function (v) { return v == null ? "" : v + (c.unit && c.unit.length < 4 ? c.unit : ""); }); } }],
      series: series,
      hooks: { setCursor: [tooltip(c)] }
    };
    c.plot = new uPlot(opts, data, c.el);
  }

  function loadHours(c) {
    Promise.all(c.series.map(function (s) {
      var from = new Date(s[3] + "T00:00:00Z"), to = new Date(from.getTime() + 86400000);
      return fetchSeries(s[0], s[1], { from: from.toISOString(), to: to.toISOString(), step: "1h" });
    })).then(function (lists) {
      var x = []; for (var h = 0; h < 24; h++) x.push(h);
      var data = [x];
      lists.forEach(function (list) {
        var ys = new Array(24).fill(null);
        list.forEach(function (p) { ys[new Date(p.ts).getUTCHours()] = p.value; });
        data.push(ys);
      });
      c.data = data;
      draw(c, data);
    });
  }

  function load(c) {
    if (c.hours) { loadHours(c); return; }
    var w = window_(c.el);
    Promise.all(c.series.map(function (s) { return fetchSeries(s[0], s[1], w); })).then(function (lists) {
      c.data = join(lists);
      draw(c, c.data);
    });
  }

  function init() {
    if (!window.uPlot) return;
    document.querySelectorAll("[data-chart]").forEach(function (el) {
      var c = { el: el, kind: el.dataset.kind || "line", hours: el.dataset.x === "hour", unit: el.dataset.unit || "", height: +el.dataset.height || 240,
                series: JSON.parse(el.dataset.series || "[]") };
      charts.push(c);
      load(c);
    });
    document.addEventListener("click", function (e) {
      var b = e.target.closest("button[data-range]");
      if (!b) return;
      var group = b.closest("[data-chart-group]") || document;
      group.querySelectorAll("button[data-range]").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
      charts.forEach(function (c) {
        if (!c.hours && (group === document || group.contains(c.el))) { c.el.dataset.range = b.dataset.range; delete c.el.dataset.from; delete c.el.dataset.to; load(c); }
      });
    });
    var redraw = function () { charts.forEach(function (c) { if (c.data) draw(c, c.data); }); };
    document.addEventListener("garden:theme", redraw);
    var t; window.addEventListener("resize", function () { clearTimeout(t); t = setTimeout(redraw, 150); });
  }
  window.GardenCharts = { reload: function () { charts.forEach(load); }, join: join };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
