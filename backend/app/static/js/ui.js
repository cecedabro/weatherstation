/* Garden UI behaviour shared by every page. Human-owned (docs/design.md). No inline scripts (CSP).
   - [data-theme-toggle]  switches light/dark and remembers it
   - [data-open="id"]     opens <dialog id>; [data-close] closes the dialog it sits in
   - form[data-confirm]   asks before submitting
   - <time datetime>      keeps "5 min ago" texts fresh */
(function () {
  "use strict";
  var KEY = "garden-theme";
  function stored() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function apply(theme) {
    if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme;
    else delete document.documentElement.dataset.theme;
  }
  apply(stored());

  function isDark() {
    var t = document.documentElement.dataset.theme;
    if (t) return t === "dark";
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-theme-toggle],[data-open],[data-close]");
    if (!t) return;
    if (t.hasAttribute("data-theme-toggle")) {
      var next = isDark() ? "light" : "dark";
      apply(next);
      try { localStorage.setItem(KEY, next); } catch (err) { /* private mode */ }
      document.dispatchEvent(new CustomEvent("garden:theme", { detail: next }));
    } else if (t.hasAttribute("data-open")) {
      var d = document.getElementById(t.getAttribute("data-open"));
      if (d && d.showModal) d.showModal();
    } else {
      var dlg = t.closest("dialog");
      if (dlg) dlg.close();
    }
  });

  document.addEventListener("submit", function (e) {
    var msg = e.target.getAttribute && e.target.getAttribute("data-confirm");
    if (msg && !window.confirm(msg)) e.preventDefault();
  });

  function ago(iso) {
    var s = (Date.now() - new Date(iso).getTime()) / 1000;
    if (!isFinite(s)) return null;
    if (s < 60) return "just now";
    if (s < 3600) return Math.round(s / 60) + " min ago";
    if (s < 86400) return Math.round(s / 3600) + " h ago";
    return Math.round(s / 86400) + " d ago";
  }
  function refreshTimes() {
    document.querySelectorAll("time[datetime][title]").forEach(function (el) {
      if (!/ago$|just now/.test(el.textContent)) return;
      var t = ago(el.getAttribute("datetime"));
      if (t) el.textContent = t;
    });
  }
  setInterval(refreshTimes, 60000);
  window.GardenUI = { isDark: isDark };
})();
