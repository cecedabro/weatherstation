/** Helper utilities extracted from chart.js to keep the main module under 150 lines.

    Functions: barPath, _findSections, _selectorButtons, _fetchSeries, _initSelectors
    */

(function () {
  "use strict";

  /* Draw a bar-style path for *rain_mm* so uPlot renders vertical bars. */
  window.barPath = function barPath(uf, scale, pxScale, valToPixel, idx) {
    if (!uf.data[1] || !uf.data[1].length) return "";
    var vals = uf.data[1],
        barW = Math.min(Math.max(uf.width / vals.length * 0.7, 1), 12),
        bottom = valToPixel(scale[1], 0);
    var d = "M";
    for (var i = 0; i < vals.length; i++) {
      var cx = pxScale[0][i], x = cx - barW / 2;
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
  };

  function _findSections() {
    var sections = document.querySelectorAll("section.card"),
        result = [];
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

  function _fetchSeries(container) {
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
    return fetch("/api/v1/series?" + params).then(function (r) {
      return r.json();
    });
  }

  function _initSelectors(section, btns, chartEls) {
    for (var b = 0; b < btns.length; b++) {
      (function (btn, sec) {
        btn.addEventListener("click", function (e) {
          e.preventDefault();
          var sectionId = sec.id || sec.dataset.sectionId || "default";
          for (var i = 0; i < charts.length; i++) {
            if (charts[i].range._section === sectionId) {
              charts[i].range.from = btn.dataset.from;
              charts[i].range.to = btn.dataset.to;
              charts[i].range.step = btn.dataset.step || "5m";
              _fetchSeries(charts[i].el)
                .then(function (ch, data) {
                  return function () { _renderChart(ch, data); };
                }(charts[i]))
                .catch(function (ch) {
                  return function () { _renderChart(ch, []); };
                }(charts[i]));
            }
          }
        });
      })(btns[b], section);
    }
  }
})();
