(function () {
  "use strict";

  const toggle = document.getElementById("menu-toggle");
  const sidebar = document.getElementById("sidebar");
  const backdrop = document.getElementById("sidebar-backdrop");
  if (!toggle || !sidebar || !backdrop) {
    return; // logged-out pages have no sidebar
  }

  function setOpen(open) {
    sidebar.classList.toggle("is-open", open);
    backdrop.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
    toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    if (open) {
      const first = sidebar.querySelector("a, button");
      if (first) {
        first.focus();
      }
    }
  }

  toggle.addEventListener("click", function () {
    setOpen(!sidebar.classList.contains("is-open"));
  });

  backdrop.addEventListener("click", function () {
    setOpen(false);
    toggle.focus();
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && sidebar.classList.contains("is-open")) {
      setOpen(false);
      toggle.focus(); // put keyboard users back where they were
    }
  });

  // If the window grows to desktop size, reset the mobile menu.
  window.matchMedia("(min-width: 901px)").addEventListener("change", function (event) {
    if (event.matches) {
      setOpen(false);
    }
  });
})();