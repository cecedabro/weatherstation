/** Client-side chart rendering via uPlot and /api/v1/series. */

(function () {
  "use strict";

  const range = { from: null, to: null, step: "5m" };

  async function fetchSeries() {
    const params = new URLSearchParams({
      node: document.currentScript.dataset.node,
      metric: document.currentScript.dataset.metric,
      from: range.from || "",
      to: range.to || "",
      step: range.step,
    });
    const res = await fetch("/api/v1/series?" + params);
    return res.json();
  }

  function renderChart(data) {
    const el = document.getElementById("chart-container");
    if (!el) return;

    if (!data || data.length === 0) {
      el.innerHTML =
        '<p style="text-align:center;padding:40px;color:var(--color-text-muted);">No data for this range</p>';
      return;
    }

    const xs = data.map((d) => new Date(d.ts).getTime() / 1000);
    const ys = data.map((d) => d.value);
    const seriesData = [[], ys];

    const opts = {
      width: el.clientWidth,
      height: 280,
      cursor: { drag: { x: true } },
      axis: [
        {
          labels: false,
          stroke: "var(--color-text-muted)",
          split: 5,
        },
        {
          label: "Value",
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
        },
      ],
      legend: { show: false },
    };

    el.innerHTML = "";
    new uPlot(opts, seriesData, el);
  }

  document.addEventListener("DOMContentLoaded", async () => {
    const btns = document.querySelectorAll(".chart-btn");
    if (btns.length) {
      const first = btns[0].dataset;
      range.from = first.from;
      range.to = first.to;
      range.step = first.step || "5m";
    }
    try {
      const data = await fetchSeries();
      renderChart(data);
    } catch {
      renderChart([]);
    }

    btns.forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.preventDefault();
        range.from = btn.dataset.from;
        range.to = btn.dataset.to;
        range.step = btn.dataset.step || "5m";
        try {
          const data = await fetchSeries();
          renderChart(data);
        } catch {
          renderChart([]);
        }
      });
    });
  });
})();
