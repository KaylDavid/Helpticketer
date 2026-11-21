(function () {
  "use strict";

  const KEY = "helpticketer-theme";
  const buttons = Array.from(document.querySelectorAll("[data-theme-toggle]"));

  function current() {
    return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
  }

  function sync() {
    const dark = current() === "dark";
    buttons.forEach(function (button) {
      button.setAttribute("aria-pressed", String(dark));
    });
  }

  buttons.forEach(function (button) {
    button.addEventListener("click", function () {
      const next = current() === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      try {
        window.localStorage.setItem(KEY, next);
      } catch (error) {
        // storage can be blocked; the theme still changes, it just won't be remembered
      }
      sync();
      // The charts are drawn in the old colors, so redraw the dashboard.
      if (document.getElementById("dashboard")) {
        window.location.reload();
      }
    });
  });

  sync();
})();