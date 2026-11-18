(function () {
  "use strict";

  const root = document.getElementById("dashboard");
  if (!root) {
    return; // not on the dashboard page
  }

  const isStaff = root.dataset.isStaff === "true";
  const PAGE_SIZE = 10;

  const state = { page: 1 };
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
  };

  // ---------- small helpers ----------
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

  function badgeCell(kind, value) {
    const td = document.createElement("td");
    const span = document.createElement("span");
    span.className = "badge badge-" + kind + "-" + value.toLowerCase().replace(/ /g, "-");
    span.textContent = value;
    td.appendChild(span);
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

  // ---------- ticket table ----------
  function renderRows(tickets) {
    el.body.replaceChildren();
    tickets.forEach(function (ticket) {
      const row = document.createElement("tr");
      row.dataset.testid = "dashboard-ticket-row";

      row.appendChild(textCell("#" + ticket.id));
      row.appendChild(titleCell(ticket));
      if (isStaff) {
        row.appendChild(textCell(ticket.requester.name));
      }
      row.appendChild(textCell(ticket.assignee ? ticket.assignee.name : "Unassigned"));
      row.appendChild(textCell(ticket.category));
      row.appendChild(badgeCell("priority", ticket.priority));
      row.appendChild(badgeCell("status", ticket.status));
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

    const params = new URLSearchParams({ page: state.page, per_page: PAGE_SIZE });
    const filters = {
      status: el.status.value,
      priority: el.priority.value,
      category: el.category.value,
      q: el.search.value.trim(),
    };
    Object.keys(filters).forEach(function (key) {
      if (filters[key]) {
        params.set(key, filters[key]);
      }
    });

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

  // ---------- summary cards and charts ----------
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

  // ---------- events ----------
  function applyFilters() {
    state.page = 1; // any change in filters starts again from page 1
    loadTickets();
  }

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
    el.search.value = "";
    el.status.value = "";
    el.priority.value = "";
    el.category.value = "";
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
  loadStats();
  loadTickets();
})();