(() => {
"use strict";

const PAGE_SIZE = 50;
const MAX_ITEMS = 1000;

let papers = [];
let previousDoi = new Set();
let journalOrder = new Map();

let selectedCategory = "All";
let selectedJournal = "All";
let selectedStatus = "All";
let selectedFetchDate = "All";
let currentPage = 1;

const $ = (id) => document.getElementById(id);

const searchBox = $("searchBox");
const categorySelect = $("categorySelect");
const journalSelect = $("journalSelect");
const statusSelect = $("statusSelect");
const fetchDateSelect = $("fetchDateSelect");
const sortBox = $("sortBox");
const summary = $("summary");
const paperList = $("paperList");
const pagination = $("pagination");
const updateTime = $("updateTime");

Promise.all([
  fetchJson("web/papers.json", []),
  fetchJson("web/previous_papers.json", []),
  fetchJson("web/update_time.json", {}),
  fetchJson("web/journal_order.json", {})
]).then(([paperData, previousData, timeData, orderData]) => {

  papers = Array.isArray(paperData) ? paperData : [];

  previousDoi = new Set(
    (Array.isArray(previousData) ? previousData : [])
      .map((p) => normalizeDoi(p.doi))
      .filter(Boolean)
  );

  buildJournalOrder(orderData);

  updateTime.textContent = timeData.updated || "--";

  initFilters();
  render();

}).catch((error) => {
  console.error(error);
  summary.textContent = "Data loading failed.";
  paperList.innerHTML =
    '<div class="empty">Unable to load paper data. Please check the JSON files and browser console.</div>';
});

function fetchJson(path, fallback) {
  return fetch(path)
    .then((r) => {
      if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
      return r.json();
    })
    .catch((error) => {
      console.warn(error);
      return fallback;
    });
}

function normalizeDoi(value) {
  return String(value || "").trim().toLowerCase();
}

function normalizeJournal(value) {

  return String(value || "")
    .replaceAll("&amp;", "&")
    .replaceAll("&", " and ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();

}

function buildJournalOrder(raw) {
  journalOrder = new Map();

  if (Array.isArray(raw)) {
    raw.forEach((item, index) => {
      if (typeof item === "string") {
        journalOrder.set(normalizeJournal(item), index + 1);
      } else if (item && item.journal) {
        const order = Number(item.order);
        journalOrder.set(
          normalizeJournal(item.journal),
          Number.isFinite(order) ? order : index + 1
        );
      }
    });
    return;
  }

  if (raw && typeof raw === "object") {
    Object.entries(raw).forEach(([name, value]) => {
      const n = Number(value);
      journalOrder.set(
        normalizeJournal(name),
        Number.isFinite(n) ? n : 999999
      );
    });
  }
}

function getJournalOrder(paper) {
  return journalOrder.get(normalizeJournal(paper.journal)) ?? 999999;
}

function isNew(paper) {
  const doi = normalizeDoi(paper.doi);
  return doi ? !previousDoi.has(doi) : false;
}

function initFilters() {
  const categories = [...new Set(
    papers.map((p) => p.category || "Other").filter(Boolean)
  )].sort((a, b) => a.localeCompare(b));

  categorySelect.innerHTML =
    '<option value="All">All Categories</option>' +
    categories.map((c) =>
      `<option value="${escapeAttr(c)}">${escapeHtml(c)}</option>`
    ).join("");

  updateJournalOptions();
  updateFetchDateOptions();

  categorySelect.addEventListener("change", () => {
    selectedCategory = categorySelect.value;
    selectedJournal = "All";
    currentPage = 1;
    updateJournalOptions();
    render();
  });

  journalSelect.addEventListener("change", () => {
    selectedJournal = journalSelect.value;
    currentPage = 1;
    render();
  });

  statusSelect.addEventListener("change", () => {
    selectedStatus = statusSelect.value;
    currentPage = 1;
    render();
  });

  fetchDateSelect.addEventListener("change", () => {
    selectedFetchDate = fetchDateSelect.value;
    currentPage = 1;
    render();
  });

  sortBox.addEventListener("change", () => {
    currentPage = 1;
    render();
  });

  searchBox.addEventListener("input", () => {
    currentPage = 1;
    render();
  });
}

function updateJournalOptions() {
  const journals = [...new Set(
    papers
      .filter((p) =>
        selectedCategory === "All" || p.category === selectedCategory
      )
      .map((p) => p.journal)
      .filter(Boolean)
  )];

  journals.sort((a, b) => {
    const oa = journalOrder.get(normalizeJournal(a)) ?? 999999;
    const ob = journalOrder.get(normalizeJournal(b)) ?? 999999;
    if (oa !== ob) return oa - ob;
    return a.localeCompare(b);
  });

  journalSelect.innerHTML =
    '<option value="All">All Journals</option>' +
    journals.map((j) =>
      `<option value="${escapeAttr(j)}">${escapeHtml(j)}</option>`
    ).join("");

  journalSelect.value = "All";
}

function updateFetchDateOptions() {
  const dates = [...new Set(
    papers.map((p) => p.fetched_date || "").filter(Boolean)
  )].sort((a, b) => b.localeCompare(a));

  fetchDateSelect.innerHTML =
    '<option value="All">All Fetch Dates</option>' +
    dates.map((d) =>
      `<option value="${escapeAttr(d)}">${escapeHtml(d)}</option>`
    ).join("");
}

function getFilteredSortedData() {
  const keyword = searchBox.value.trim().toLowerCase();

  let data = papers.filter((p) => {
    if (
      selectedCategory !== "All" &&
      p.category !== selectedCategory
    ) return false;

    if (
      selectedJournal !== "All" &&
      p.journal !== selectedJournal
    ) return false;

    if (
      selectedStatus === "New" &&
      !isNew(p)
    ) return false;

    if (
      selectedFetchDate !== "All" &&
      (p.fetched_date || "") !== selectedFetchDate
    ) return false;

    if (keyword) {
      const haystack = [
        p.title || "",
        p.authors || "",
        p.doi || "",
        p.journal || ""
      ].join(" ").toLowerCase();

      if (!haystack.includes(keyword)) return false;
    }

    return true;
  });

  data.sort((a, b) => {

    // NEW is always shown first.
    const newA = isNew(a) ? 0 : 1;
    const newB = isNew(b) ? 0 : 1;
    if (newA !== newB) return newA - newB;

    if (sortBox.value === "journal") {
      const orderA = getJournalOrder(a);
      const orderB = getJournalOrder(b);

      if (orderA !== orderB) return orderA - orderB;

      const journalCompare =
        (a.journal || "").localeCompare(b.journal || "");

      if (journalCompare !== 0) return journalCompare;

      return compareOnlineDateDesc(a, b);
    }

    const dateCompare = compareOnlineDateDesc(a, b);
    if (dateCompare !== 0) return dateCompare;

    const orderA = getJournalOrder(a);
    const orderB = getJournalOrder(b);

    if (orderA !== orderB) return orderA - orderB;

    return (a.title || "").localeCompare(b.title || "");
  });

  return data.slice(0, MAX_ITEMS);
}

function compareOnlineDateDesc(a, b) {
  return normalizeDate(b.online_date)
    .localeCompare(normalizeDate(a.online_date));
}

function normalizeDate(value) {
  const s = String(value || "").trim();

  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
  if (/^\d{4}-\d{2}$/.test(s)) return `${s}-00`;
  if (/^\d{4}$/.test(s)) return `${s}-00-00`;

  return "0000-00-00";
}

function render() {
  const data = getFilteredSortedData();
  const total = data.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  if (currentPage > totalPages) currentPage = 1;

  if (total === 0) {
    summary.textContent = "No matching papers.";
    paperList.innerHTML =
      '<div class="empty">No papers match the current filters.</div>';
    pagination.innerHTML = "";
    return;
  }

  const start = (currentPage - 1) * PAGE_SIZE;
  const pageData = data.slice(start, start + PAGE_SIZE);

  summary.textContent =
    `Showing ${start + 1}–${Math.min(start + PAGE_SIZE, total)} of ${total} papers`;

  paperList.innerHTML = pageData.map((p) => {
    const fresh = isNew(p);
    const doi = p.doi || "";

    return `
      <article class="paper${fresh ? " is-new" : ""}">
        <div class="title">
  ${
    p.doi
      ? `<a class="paper-title-link"
           href="https://doi.org/${encodeURIComponent(p.doi)}"
           target="_blank"
           rel="noopener noreferrer">
           ${escapeHtml(p.title || "")}
         </a>`
      : escapeHtml(p.title || "")
  }
  ${fresh ? '<span class="badge">NEW</span>' : ""}
</div>

        <div class="journal">
          ${escapeHtml(p.journal || "")}
        </div>

        <div class="author">
          ${escapeHtml(p.authors || "")}
        </div>

        <div class="meta">
          <span class="meta-part">Online: ${escapeHtml(p.online_date || "N/A")}</span>
          <span class="sep">|</span>
          <span class="meta-part">Fetched (GMT+8): ${escapeHtml(p.fetched_date || "N/A")}</span>
          <br>
          <a href="https://doi.org/${encodeURIComponent(doi)}"
             target="_blank"
             rel="noopener noreferrer">
             DOI: ${escapeHtml(doi)}
          </a>
        </div>
      </article>
    `;
  }).join("");

  renderPagination(totalPages);
}

function renderPagination(totalPages) {
  pagination.innerHTML = "";

  if (totalPages <= 1) return;

  const row = document.createElement("div");
  row.className = "pagination-buttons";

  const addButton = (label, target, active = false) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "page-btn" + (active ? " active" : "");
    button.textContent = label;

    button.addEventListener("click", () => {
      currentPage = target;
      render();
      window.scrollTo({ top: 0, behavior: "smooth" });
    });

    row.appendChild(button);
  };

  const addEllipsis = () => {
    const span = document.createElement("span");
    span.className = "page-ellipsis";
    span.textContent = "…";
    row.appendChild(span);
  };

  if (currentPage > 1) {
    addButton("Previous", currentPage - 1);
  }

  const startPage = Math.max(1, currentPage - 2);
  const endPage = Math.min(totalPages, currentPage + 2);

  if (startPage > 1) {
    addButton("1", 1);
    if (startPage > 2) addEllipsis();
  }

  for (let i = startPage; i <= endPage; i += 1) {
    addButton(String(i), i, i === currentPage);
  }

  if (endPage < totalPages) {
    if (endPage < totalPages - 1) addEllipsis();
    addButton(String(totalPages), totalPages);
  }

  if (currentPage < totalPages) {
    addButton("Next", currentPage + 1);
  }

  const info = document.createElement("div");
  info.className = "page-info";
  info.textContent = `Page ${currentPage} / ${totalPages}`;

  pagination.appendChild(row);
  pagination.appendChild(info);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value);
}

})();
