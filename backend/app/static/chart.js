/** Client-side chart rendering via uPlot and /api/v1/series.

    Supports multiple charts on one page. Each chart is a <div data-chart>
    carrying ``data-node`` and ``data-metric`` attributes.

    Selector buttons inside a ``.chart-selector`` group control every chart
    inside the same parent section.  ``rain_mm`` is drawn as bars; all other
    metrics use line rendering.
    */

(function () {
  "use strict";

  /* ---- helpers ------------------------------------------------------- */

  /* Draw a bar-style path for *rain_mm* so uPlot renders vertical bars
     instead of a thin line.  Returns a *uPlot.Path* object. */
  function barPath(uf, scale, pxScale, valToPixel, idx) {
    if (!uf.data[1] || !uf.data[1].length) return "";
    var vals = uf.data[1],
        x0 = pxScale[0][0],
        x1 = pxScale[0][vals.length - 1],
        barW = Math.max(Math.min(uf.width / vals.length * 0.7, 12), 1),
        bottom = valToPixel(scale[1], 0);

    var d = "M";
    for (var i = 0; i < vals.length; i++) {
      var cx = pxScale[0][i],
          x = cx - barW / 2;
      if (i > 0) d += "M";
      d += x.toFixed(1) + "," + bottom.toFixed(1);
      d += "v" + (bottom - valToPixel(scale[1], vals[i])).toFixed(1);
      d += "h" + barW.toFixed(1);
      d += "v" + (-bottom + valToPixel(scale[1], vals[i])).toFixed(1);
      d += "z";
    }
    return {
      fill: "var(--color-accent-alpha)",
      stroke: "var(--color-accent)",
      points: [],
      path: d,
    };
  }

  /* ---- state per container ------------------------------------------- */

  var charts = [];

  function _findSections() {
    var sections = document.querySelectorAll("section.card");
    var result = [];
    for (var i = 0; i < sections.length; i++) {
      if (sections[i].querySelector("[data-chart]")) {
        result.push(sections[i]);
      }
    }
    return result;
  }

  function _selectorButtons(section) {
    return Array.from(section.querySelectorAll(".chart-btn")) || [];
  }

  /* ---- fetch --------------------------------------------------------- */

  async function _fetchSeries(container) {
    var params = new URLSearchParams({
      node: container.dataset.node,
      metric: container.dataset.metric,
      from: "",
      to: "",
      step: "5m",
    });
    for (var i = 0; i < charts.length; i++) {
      if (charts[i].el === container) {
        params.set("from", charts[i].range.from || "");
        params.set("to", charts[i].range.to || "");
        params.set("step", charts[i].range.step);
        break;
      }
    }
    var res = await fetch("/api/v1/series?" + params);
    return res.json();
  }

  /* ---- render -------------------------------------------------------- */

  function _renderChart(chart, data) {
    var el = chart.el;
    if (!el) return;

    if (!data || data.length === 0) {
      el.innerHTML =
        '<p style="text-align:center;padding:40px;color:var(--color-text-muted);">No data for this range</p>';
      return;
    }

    var xs = data.map(function (d) { return new Date(d.ts).getTime() / 1000; }),
        ys = data.map(function (d) { return d.value; }),
        seriesData = [[], ys];

    var isRain = chart.metric === "rain_mm",
        opts = {
          width: el.clientWidth || 600,
          height: 280,
          cursor: { drag: { x: true } },
          axis: [
            {
              labels: false,
              stroke: "var(--color-text-muted)",
              split: 5,
            },
            {
              label: chart.metric,
              stroke: "var(--color-accent)",
              grid: { stroke: "var(--color-border)" },
            },
          ],
          series: [
            {},
            {
              stroke: isRain ? "var(--color-accent)" : "var(--color-accent)",
              fill: isRain ? "var(--color-accent-alpha)" : "var(--color-accent-alpha)",
              width: 2,
              points: { show: false },
              path: isRain ? barPath : undefined,
            },
          ],
          legend: { show: false },
        };

    el.innerHTML = "";
    try {
      chart.instance = new uPlot(opts, seriesData, el);
    } catch (e) {
      el.innerHTML =
        '<p style="text-align:center;padding:40px;color:var(--color-text-muted);">Chart error</p>';
    }
  }

  /* ---- init & events ------------------------------------------------- */

  document.addEventListener("DOMContentLoaded", function () {
    var sections = _findSections();

    /* Register every chart container in a section. */
    for (var s = 0; s < sections.length; s++) {
      var section = sections[s],
          btns = _selectorButtons(section),
          chartEls = section.querySelectorAll("[data-chart]");

      for (var c = 0; c < chartEls.length; c++) {
        var container = chartEls[c],
            range = {
              from: btns[0] ? btns[0].dataset.from : null,
              to: btns[0] ? btns[0].dataset.to : null,
              step: btns[0] ? (btns[0].dataset.step || "5m") : "5m",
              _section: section.id || "default",
            };
        charts.push({ el: container, range: range, metric: container.dataset.metric });

        /* First chart in each section kicks off the data fetch. */
        if (c === 0) {
          (function (chart, section) {
            _fetchSeries(chart.el).then(function (data) {
              _renderChart(chart, data);
            }).catch(function () {
              _renderChart(chart, []);
            });
          })(charts[charts.length - 1], section);
        }
      }
    }

    /* Click handlers on selector buttons (one per section). */
    for (var s2 = 0; s2 < sections.length; s2++) {
      var sec = sections[s2],
          secBtns = _selectorButtons(sec);
      for (var b = 0; b < secBtns.length; b++) {
        (function (btn, sec) {
          btn.addEventListener("click", function (e) {
            e.preventDefault();
            var sectionId = sec.id || sec.dataset.sectionId || "default";

            /* Update all charts in this section. */
            var i;
            for (i = 0; i < charts.length; i++) {
              if (charts[i].range._section === sectionId) {
                charts[i].range.from = btn.dataset.from;
                charts[i].range.to = btn.dataset.to;
                charts[i].range.step = btn.dataset.step || "5m";
                _fetchSeries(charts[i].el).then(function (data, ch) {
                  return function () { _renderChart(ch, data); };
                }(charts[i])).catch(function (ch) {
                  return function () { _renderChart(ch, []); };
                }(charts[i]));
              }
            }
          });
        })(secBtns[b], sec);
      }
    }
  });
})();
