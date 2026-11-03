/** Client-side chart rendering via uPlot and /api/v1/series.

    Supports multiple charts on one page. Each chart is a <div data-chart>
    carrying ``data-node`` and ``data-metric`` attributes.

    Selector buttons inside a ``.chart-selector`` group control every chart
    inside the same parent section.  ``rain_mm`` is drawn as bars; all other
    metrics use line rendering.
    */

(function () {
  "use strict";

  /* ---- state per container ------------------------------------------- */

  var charts = [];

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
        seriesData = [[], ys],
        isRain = chart.metric === "rain_mm",
        opts = {
          width: el.clientWidth || 600,
          height: 280,
          cursor: { drag: { x: true } },
          axis: [
            { labels: false, stroke: "var(--color-text-muted)", split: 5 },
            {
              label: chart.metric,
              stroke: "var(--color-accent)",
              grid: { stroke: "var(--color-border)" },
            },
          ],
          series: [
            {},
            {
              stroke: "var(--color-accent)",
              fill: "var(--color-accent-alpha)",
              width: 2,
              points: { show: false },
              path: isRain ? window.barPath : undefined,
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
      _initSelectors(section, btns, chartEls);
    }
  });
})();
