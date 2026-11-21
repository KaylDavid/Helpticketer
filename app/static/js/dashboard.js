(function () {
  "use strict";

  const root = document.getElementById("dashboard");
  if (!root) {
    return; // not on the dashboard page
  }

  const isStaff = root.dataset.isStaff === "true";
  const PAGE_SIZE = 10;
  const BOARD_LIMIT = 50; // the API's largest page size
  const STATUSES = ["Open", "In Progress", "Resolved", "Closed"];
  const VIEW_KEY = "helpticketer-view";

  // scope is the "assigned" filter: "" (none), "me", or "unassigned"
  const state = { page: 1, scope: "", view: "table" };
  let requestId = 0; // used to ignore out-of-date responses
  let searchTimer = null;

  const el = {
    search: document.getElementById("filter-search"),
    status: document.getElementById("filter-status"),
    priority: document.getElementById("filter-priority"),
    category: document.getElementById("filter-category"),
    reset: document.getElementById("filter-reset"),
    form: document.getElementById("filter-form"),
    body: document.getElementById("tickets-body"),
    summary: document.getElementById("results-summary"),
    empty: document.getElementById("empty-state"),
    prev: document.getElementById("pager-prev"),
    next: document.getElementById("pager-next"),
    pageInfo: document.getElementById("page-info"),
    error: document.getElementById("load-error"),
    chartsNote: document.getElementById("charts-note"),
    tableView: document.getElementById("table-view"),
    boardView: document.getElementById("board-view"),
  };
  const chips = Array.from(document.querySelectorAll("[data-chip]"));
  const viewButtons = Array.from(document.querySelectorAll("[data-view]"));

  const STATUS_ICONS = { "Open": "○", "In Progress": "◐", "Resolved": "✓", "Closed": "■" };

  // ---------- small helpers ----------
  function slug(value) {
    return value.toLowerCase().replace(/ /g, "-");
  }

  function showError(message) {
    el.error.textContent = message;
    el.error.hidden = false;
  }

  function clearError() {
    el.error.hidden = true;
    el.error.textContent = "";
  }

  // Always textContent (never innerHTML) so ticket text can never run as code.
  function textCell(text, className) {
    const td = document.createElement("td");
    td.textContent = text;
    if (className) {
      td.className = className;
    }
    return td;
  }

  function priorityBadge(value) {
    const span = document.createElement("span");
    span.className = "badge badge-priority-" + slug(value);
    span.textContent = value;
    return span;
  }

  function priorityCell(value) {
    const td = document.createElement("td");
    td.appendChild(priorityBadge(value));
    return td;
  }

  function statusCell(value) {
    const td = document.createElement("td");
    const pill = document.createElement("span");
    pill.className = "pill pill-status-" + slug(value);

    const icon = document.createElement("span");
    icon.className = "pill-icon";
    icon.setAttribute("aria-hidden", "true"); // the text next to it carries the meaning
    icon.textContent = STATUS_ICONS[value] || "•";

    pill.appendChild(icon);
    pill.appendChild(document.createTextNode(value));
    td.appendChild(pill);
    return td;
  }

  function titleCell(ticket) {
    const td = document.createElement("td");
    td.className = "title-cell";
    const link = document.createElement("a");
    link.href = "/tickets/" + ticket.id;
    link.textContent = ticket.title;
    link.dataset.testid = "dashboard-ticket-link";
    td.appendChild(link);
    return td;
  }

  async function getJson(url) {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (response.status === 401) {
      window.location.href = "/login";
      return null;
    }
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Something went wrong.");
    }
    return data;
  }

  // The filters shared by the table and the board (everything except status and paging).
  function baseParams() {
    const params = new URLSearchParams();
    const filters = {
      priority: el.priority.value,
      category: el.category.value,
      q: el.search.value.trim(),
    };
    Object.keys(filters).forEach(function (key) {
      if (filters[key]) {
        params.set(key, filters[key]);
      }
    });
    if (state.scope === "me") {
      params.set("assigned", "me");
    } else if (state.scope === "unassigned") {
      params.set("unassigned", "true");
    }
    return params;
  }

  // ---------- table view ----------
  function renderRows(tickets) {
    el.body.replaceChildren();
    tickets.forEach(function (ticket) {
      const row = document.createElement("tr");
      row.className = "prio-" + slug(ticket.priority); // colored strip on the left edge
      row.dataset.testid = "dashboard-ticket-row";

      row.appendChild(textCell("#" + ticket.id));
      row.appendChild(titleCell(ticket));
      if (isStaff) {
        row.appendChild(textCell(ticket.requester.name));
      }
      row.appendChild(textCell(ticket.assignee ? ticket.assignee.name : "Unassigned"));
      row.appendChild(textCell(ticket.category));
      row.appendChild(priorityCell(ticket.priority));
      row.appendChild(statusCell(ticket.status));
      row.appendChild(textCell(ticket.created_at.slice(0, 10)));

      el.body.appendChild(row);
    });
  }

  function renderSummary(data) {
    if (data.total === 0) {
      el.summary.textContent = "No tickets found.";
      el.empty.hidden = false;
    } else {
      const first = (data.page - 1) * data.per_page + 1;
      const last = first + data.tickets.length - 1;
      el.summary.textContent = "Showing " + first + "-" + last + " of " + data.total + " tickets";
      el.empty.hidden = true;
    }
    el.pageInfo.textContent = "Page " + data.page + " of " + Math.max(data.pages, 1);
    el.prev.disabled = data.page <= 1;
    el.next.disabled = data.page >= data.pages;
  }

  async function loadTickets() {
    const myRequest = ++requestId;

    const params = baseParams();
    params.set("page", state.page);
    params.set("per_page", PAGE_SIZE);
    if (el.status.value) {
      params.set("status", el.status.value);
    }

    try {
      const data = await getJson("/api/tickets?" + params.toString());
      if (data === null || myRequest !== requestId) {
        return; // redirected, or a newer request has already replaced this one
      }
      clearError();
      renderRows(data.tickets);
      renderSummary(data);
    } catch (error) {
      if (myRequest !== requestId) {
        return;
      }
      showError("Could not load tickets: " + error.message);
    }
  }

  // ---------- board view ----------
  function boardNote(text) {
    const li = document.createElement("li");
    li.className = "board-note muted";
    li.textContent = text;
    return li;
  }

  function boardCard(ticket) {
    const li = document.createElement("li");
    li.className = "board-card prio-" + slug(ticket.priority); // same colored strip as the table
    li.dataset.testid = "board-card";

    const link = document.createElement("a");
    link.className = "board-card-title";
    link.href = "/tickets/" + ticket.id;
    link.textContent = ticket.title;
    link.dataset.testid = "board-ticket-link";
    li.appendChild(link);

    const top = document.createElement("div");
    top.className = "board-card-meta";
    const id = document.createElement("span");
    id.className = "muted";
    id.textContent = "#" + ticket.id;
    top.appendChild(id);
    top.appendChild(priorityBadge(ticket.priority));
    li.appendChild(top);

    const who = document.createElement("p");
    who.className = "board-card-line muted";
    who.textContent = "Assigned: " + (ticket.assignee ? ticket.assignee.name : "Unassigned");
    li.appendChild(who);

    if (isStaff) {
      const from = document.createElement("p");
      from.className = "board-card-line muted";
      from.textContent = "From: " + ticket.requester.name;
      li.appendChild(from);
    }
    return li;
  }

  function renderColumn(status, result) {
    const list = document.querySelector('[data-col-list="' + status + '"]');
    const count = document.querySelector('[data-col-count="' + status + '"]');
    list.replaceChildren();

    if (result.skipped) {
      count.textContent = "0";
      list.appendChild(boardNote("Hidden by the status filter."));
      return 0;
    }

    const data = result.data;
    count.textContent = data.total;
    if (data.tickets.length === 0) {
      list.appendChild(boardNote("No tickets."));
    }
    data.tickets.forEach(function (ticket) {
      list.appendChild(boardCard(ticket));
    });
    if (data.total > data.tickets.length) {
      const more = data.total - data.tickets.length;
      list.appendChild(boardNote(more + " more not shown. Narrow your filters or use the Table view."));
    }
    return data.total;
  }

  async function loadBoard() {
    const myRequest = ++requestId;
    const selected = el.status.value; // a status filter means only that column is loaded

    try {
      const results = await Promise.all(
        STATUSES.map(async function (status) {
          if (selected && selected !== status) {
            return { status: status, skipped: true };
          }
          const params = baseParams();
          params.set("status", status);
          params.set("per_page", BOARD_LIMIT);
          const data = await getJson("/api/tickets?" + params.toString());
          return { status: status, data: data };
        })
      );

      if (results.some(function (r) { return !r.skipped && r.data === null; })) {
        return; // redirected to the login page
      }
      if (myRequest !== requestId) {
        return; // a newer request has already replaced this one
      }

      clearError();
      let total = 0;
      results.forEach(function (result) {
        total += renderColumn(result.status, result);
      });
      el.summary.textContent = total === 0 ? "No tickets found." : total + " tickets on the board";
    } catch (error) {
      if (myRequest !== requestId) {
        return;
      }
      showError("Could not load the board: " + error.message);
    }
  }

  function loadCurrent() {
    if (state.view === "board") {
      loadBoard();
    } else {
      loadTickets();
    }
  }

  // ---------- table / board toggle ----------
  function setView(view, remember) {
    state.view = view;
    el.tableView.hidden = view !== "table";
    el.boardView.hidden = view !== "board";
    viewButtons.forEach(function (button) {
      button.setAttribute("aria-pressed", String(button.dataset.view === view));
    });
    if (remember) {
      try {
        window.localStorage.setItem(VIEW_KEY, view);
      } catch (error) {
        // storage can be blocked; the page still works, it just won't remember
      }
    }
  }

  function storedView() {
    try {
      return window.localStorage.getItem(VIEW_KEY) === "board" ? "board" : "table";
    } catch (error) {
      return "table";
    }
  }

  // ---------- summary cards, chip counts and charts ----------
  const STATUS_COLORS = {
    "Open": "#3b82f6",
    "In Progress": "#f59e0b",
    "Resolved": "#22c55e",
    "Closed": "#9ca3af",
  };
  const PRIORITY_COLORS = {
    "Low": "#9ca3af",
    "Medium": "#38bdf8",
    "High": "#fb923c",
    "Urgent": "#ef4444",
  };

  function fillCards(stats) {
    const values = {
      "total": stats.total,
      "open": stats.by_status["Open"],
      "in-progress": stats.by_status["In Progress"],
      "resolved": stats.by_status["Resolved"],
      "closed": stats.by_status["Closed"],
      "unassigned": stats.unassigned,
    };
    document.querySelectorAll("[data-stat]").forEach(function (node) {
      const value = values[node.dataset.stat];
      if (value !== undefined) {
        node.textContent = value;
      }
    });

    const chipValues = {
      "all": stats.total,
      "mine": stats.assigned_to_me,
      "unassigned": stats.unassigned,
      "urgent": stats.by_priority["Urgent"],
      "open": stats.by_status["Open"],
      "in-progress": stats.by_status["In Progress"],
      "resolved": stats.by_status["Resolved"],
    };
    document.querySelectorAll("[data-chip-count]").forEach(function (node) {
      const value = chipValues[node.dataset.chipCount];
      if (value !== undefined) {
        node.textContent = value;
      }
    });
  }

  function drawCharts(stats) {
    if (typeof Chart === "undefined") {
      el.chartsNote.textContent = "Charts could not be loaded. The numbers above are still correct.";
      el.chartsNote.hidden = false;
      return;
    }
    if (stats.total === 0) {
      el.chartsNote.textContent = "No tickets yet, so there is nothing to chart.";
      el.chartsNote.hidden = false;
      return;
    }

    const statusLabels = Object.keys(stats.by_status);
    new Chart(document.getElementById("status-chart"), {
      type: "bar",
      data: {
        labels: statusLabels,
        datasets: [{
          label: "Tickets",
          data: statusLabels.map(function (label) { return stats.by_status[label]; }),
          backgroundColor: statusLabels.map(function (label) { return STATUS_COLORS[label]; }),
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
      },
    });

    const priorityLabels = Object.keys(stats.by_priority);
    new Chart(document.getElementById("priority-chart"), {
      type: "doughnut",
      data: {
        labels: priorityLabels,
        datasets: [{
          data: priorityLabels.map(function (label) { return stats.by_priority[label]; }),
          backgroundColor: priorityLabels.map(function (label) { return PRIORITY_COLORS[label]; }),
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "bottom" } },
      },
    });
  }

  async function loadStats() {
    try {
      const data = await getJson("/api/stats");
      if (data === null) {
        return;
      }
      fillCards(data.stats);
      drawCharts(data.stats);
    } catch (error) {
      showError("Could not load statistics: " + error.message);
    }
  }

  // ---------- chips ----------
  function clearFilters() {
    el.search.value = "";
    el.status.value = "";
    el.priority.value = "";
    el.category.value = "";
    state.scope = "";
  }

  function chipIsOn(name) {
    switch (name) {
      case "all":
        return !state.scope && !el.status.value && !el.priority.value &&
          !el.category.value && !el.search.value.trim();
      case "mine":
        return state.scope === "me";
      case "unassigned":
        return state.scope === "unassigned";
      case "urgent":
        return el.priority.value === "Urgent";
      case "open":
        return el.status.value === "Open";
      case "in-progress":
        return el.status.value === "In Progress";
      case "resolved":
        return el.status.value === "Resolved";
      default:
        return false;
    }
  }

  function syncChips() {
    chips.forEach(function (chip) {
      chip.setAttribute("aria-pressed", String(chipIsOn(chip.dataset.chip)));
    });
  }

  function applyChip(name) {
    clearFilters(); // a chip starts a fresh view
    if (name === "mine") {
      state.scope = "me";
    } else if (name === "unassigned") {
      state.scope = "unassigned";
    } else if (name === "urgent") {
      el.priority.value = "Urgent";
    } else if (name === "open") {
      el.status.value = "Open";
    } else if (name === "in-progress") {
      el.status.value = "In Progress";
    } else if (name === "resolved") {
      el.status.value = "Resolved";
    }
    applyFilters();
  }

  // ---------- events ----------
  function applyFilters() {
    state.page = 1; // any change in filters starts again from page 1
    syncChips();
    loadCurrent();
  }

  chips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      applyChip(chip.dataset.chip);
    });
  });

  viewButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      if (state.view === button.dataset.view) {
        return;
      }
      setView(button.dataset.view, true);
      loadCurrent();
    });
  });

  el.search.addEventListener("input", function () {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(applyFilters, 300); // wait until typing pauses
  });
  [el.status, el.priority, el.category].forEach(function (select) {
    select.addEventListener("change", applyFilters);
  });
  el.form.addEventListener("submit", function (event) {
    event.preventDefault();
  });
  el.reset.addEventListener("click", function () {
    clearFilters();
    applyFilters();
  });
  el.prev.addEventListener("click", function () {
    state.page -= 1;
    loadTickets();
  });
  el.next.addEventListener("click", function () {
    state.page += 1;
    loadTickets();
  });

  // ---------- start ----------
  setView(storedView(), false);
  syncChips();
  loadStats();
  loadCurrent();
})();