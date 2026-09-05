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
  ensureBibtexStyles();

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

function buildDoiUrl(value) {
  const doi = String(value || "").trim();

  if (!doi) return "#";

  // Encode special characters while preserving "/" inside the DOI.
  const encodedDoi = encodeURIComponent(doi)
    .replace(/%2F/gi, "/");

  return `https://doi.org/${encodedDoi}`;
}

function ensureBibtexStyles() {
  if (document.getElementById("paper-monitor-bibtex-style")) return;

  const style = document.createElement("style");
  style.id = "paper-monitor-bibtex-style";
  style.textContent = `
    .paper-title-row {
      display: flex;
      align-items: flex-start;
      gap: 10px;
    }

    .paper-title-row .title {
      flex: 1 1 auto;
      min-width: 0;
    }

    .bibtex-btn {
      flex: 0 0 auto;
      margin-left: auto;
      padding: 5px 9px;
      border: 1px solid #b8cbe0;
      border-radius: 4px;
      background: #f4f8fc;
      color: #1f4e85;
      font-size: 12px;
      line-height: 1.2;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
    }

    .bibtex-btn:hover {
      background: #e9f2fa;
      border-color: #8eafd0;
    }

    .bibtex-btn:focus {
      outline: 2px solid #aac7e3;
      outline-offset: 2px;
    }

    @media only screen and (max-width: 600px) {
      .paper-title-row {
        gap: 7px;
      }

      .bibtex-btn {
        padding: 4px 7px;
        font-size: 10.5px;
      }
    }
  `;

  document.head.appendChild(style);
}

function bibtexEscape(value) {
  const replacements = {
    "\\": "\\textbackslash{}",
    "{": "\\{",
    "}": "\\}",
    "%": "\\%",
    "&": "\\&",
    "_": "\\_",
    "#": "\\#",
    "$": "\\$",
    "~": "\\textasciitilde{}",
    "^": "\\textasciicircum{}"
  };

  return String(value || "").replace(
    /[\\{}%&_#$~^]/g,
    (char) => replacements[char]
  );
}

function bibtexEscapeNoAmpersand(value) {
  const replacements = {
    "\\": "\\textbackslash{}",
    "{": "\\{",
    "}": "\\}",
    "%": "\\%",
    "_": "\\_",
    "#": "\\#",
    "$": "\\$",
    "~": "\\textasciitilde{}",
    "^": "\\textasciicircum{}"
  };

  // Keep "&" unchanged in title, author, and journal fields for reference-manager import.
  return String(value || "").replace(
    /[\\{}%_#$~^]/g,
    (char) => replacements[char]
  );
}


function bibtexAuthors(value) {
  return String(value || "")
    .split(";")
    .map((name) => name.trim())
    .filter(Boolean)
    .join(" and ");
}

function shouldPreserveBibtexCase(part) {
  const text = String(part || "");

  /*
   * Preserve likely abbreviations / proper-name forms, for example:
   * AI, GDM, MCDM, LSTM, COVID-19, DeGroot, CrossRef, eWOM.
   */
  const asciiLetters = text.match(/[A-Za-z]/g) || [];

  if (asciiLetters.length === 0) {
    return true;
  }

  const uppercaseCount = (
    text.match(/[A-Z]/g) || []
  ).length;

  if (uppercaseCount >= 2) {
    return true;
  }

  if (/[a-z][A-Z]/.test(text)) {
    return true;
  }

  return false;
}


function sentenceCaseBibtexWord(word, capitalizeFirst) {
  /*
   * Process hyphenated words part by part:
   *
   * AI-Based       -> AI-based
   * Decision-Making -> Decision-making
   * DeGroot-Based  -> DeGroot-based
   */
  let firstPart = true;

  return String(word || "")
    .split(/(-)/)
    .map((part) => {

      if (part === "-") {
        return part;
      }

      if (!part) {
        return part;
      }

      const preserve = shouldPreserveBibtexCase(part);
      let result;

      if (preserve) {
        result = part;
      } else {
        result = part.toLowerCase();

        if (capitalizeFirst && firstPart) {
          result = result.replace(
            /\p{L}/u,
            (char) => char.toUpperCase()
          );
        }
      }

      firstPart = false;
      return result;
    })
    .join("");
}


function sentenceCaseBibtexSegment(segment) {
  /*
   * Convert a title segment to sentence case while preserving
   * likely acronyms and mixed-case proper-name forms.
   *
   * Example:
   * Data Mining with AI
   * ->
   * Data mining with AI
   */
  let firstWord = true;

  return String(segment || "").replace(
    /[\p{L}\p{N}][\p{L}\p{N}'’.-]*/gu,
    (word) => {

      const result = sentenceCaseBibtexWord(
        word,
        firstWord
      );

      firstWord = false;
      return result;
    }
  );
}


function formatBibtexTitle(value) {
  /*
   * Convert copied BibTeX titles to sentence case.
   *
   * Rules:
   * 1. Capitalize the first word of the title.
   * 2. Lowercase ordinary title-case words.
   * 3. Capitalize the first word after ":".
   * 4. Preserve likely abbreviations / mixed-case terms.
   *
   * Example:
   * Data Mining with AI: alter Decision-Making
   * ->
   * Data mining with AI: Alter decision-making
   */
  const title = String(value || "")
    .trim()
    .replace(/\s+/g, " ");

  if (!title) {
    return "";
  }

  const pieces = title.split(/(:)/);

  return pieces
    .map((piece) => {
      if (piece === ":") {
        return piece;
      }

      return sentenceCaseBibtexSegment(piece);
    })
    .join("");
}

function getPaperYear(paper) {
  const onlineDate = String(paper.online_date || "").trim();
  const fetchedDate = String(paper.fetched_date || "").trim();

  const onlineMatch = onlineDate.match(/^(\d{4})/);
  if (onlineMatch) return onlineMatch[1];

  const fetchedMatch = fetchedDate.match(/^(\d{4})/);
  if (fetchedMatch) return fetchedMatch[1];

  return "";
}

function asciiToken(value) {
  return String(value || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^A-Za-z0-9]/g, "");
}

function buildBibtexKey(paper) {
  const authors = String(paper.authors || "");
  const firstAuthor = authors.split(";")[0].trim();
  const authorParts = firstAuthor.split(/\s+/).filter(Boolean);
  const surname = asciiToken(authorParts[authorParts.length - 1] || "");

  const year = getPaperYear(paper);

  const titleWords = String(paper.title || "")
    .split(/\s+/)
    .map(asciiToken)
    .filter((word) => word.length >= 4);

  const titleToken = titleWords[0] || "";

  if (surname || titleToken) {
    return `${surname || "Paper"}${year}${titleToken || "Article"}`;
  }

  const doiToken = asciiToken(paper.doi || "").slice(-8);
  return `Paper${year}${doiToken || "Citation"}`;
}

function buildBibtex(paper) {
  const key = buildBibtexKey(paper);
  const fields = [];

  const title = formatBibtexTitle(
    paper.title
  );
  const authors = bibtexAuthors(paper.authors);
  const journal = String(paper.journal || "").trim();
  const publisher = String(paper.publisher || "").trim();
  const year = getPaperYear(paper);
  const volume = String(paper.volume || "").trim();
  const number = String(paper.number || "").trim();
  const pages = String(paper.pages || "").trim();
  const articleNumber = String(paper.article_number || "").trim();
  const doi = String(paper.doi || "").trim();

  // Online-only / in-press papers without formal volume or issue
  // information should not include a BibTeX year field.
  const hasFormalVolumeIssue = Boolean(volume || number);

  if (title) {
    fields.push(`  title = {${bibtexEscapeNoAmpersand(title)}}`);
  }

  if (authors) {
    fields.push(`  author = {${bibtexEscapeNoAmpersand(authors)}}`);
  }

  if (journal) {
    fields.push(`  journal = {${bibtexEscapeNoAmpersand(journal)}}`);
  }

  if (year && hasFormalVolumeIssue) {
    fields.push(`  year = {${year}}`);
  }

  if (volume) {
    fields.push(`  volume = {${bibtexEscape(volume)}}`);
  }

  if (number) {
    fields.push(`  number = {${bibtexEscape(number)}}`);
  }

  if (pages) {
    fields.push(`  pages = {${bibtexEscape(pages)}}`);
  } else if (articleNumber) {
    fields.push(`  pages = {${bibtexEscape(articleNumber)}}`);
  }

  if (publisher) {
    fields.push(`  publisher = {${bibtexEscape(publisher)}}`);
  }

  if (doi) {
    fields.push(`  doi = {${bibtexEscape(doi)}}`);
    fields.push(`  url = {${buildDoiUrl(doi)}}`);
  }

  return {
    key,
    content: `@article{${key},\n${fields.join(",\n")}\n}\n`
  };
}

async function copyBibtex(paper, button) {
  const bibtex = buildBibtex(paper);
  const originalText = button ? button.textContent : "BibTeX";

  try {
    if (
      navigator.clipboard &&
      typeof navigator.clipboard.writeText === "function"
    ) {
      await navigator.clipboard.writeText(bibtex.content);
    } else {
      const textarea = document.createElement("textarea");
      textarea.value = bibtex.content;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "fixed";
      textarea.style.left = "-9999px";

      document.body.appendChild(textarea);
      textarea.select();

      const copied = document.execCommand("copy");
      textarea.remove();

      if (!copied) {
        throw new Error("Clipboard copy failed.");
      }
    }

    if (button) {
      button.textContent = "Copied!";
      button.disabled = true;

      window.setTimeout(() => {
        button.textContent = originalText;
        button.disabled = false;
      }, 1200);
    }

  } catch (error) {
    console.error("BibTeX copy failed:", error);

    if (button) {
      button.textContent = "Copy failed";

      window.setTimeout(() => {
        button.textContent = originalText;
      }, 1500);
    }
  }
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

  // Sorting is fixed as:
  // NEW -> journal -> online date,
  // then non-NEW -> journal -> online date.
  if (sortBox) {
    sortBox.disabled = true;
    sortBox.title =
      "Fixed order: NEW first, then Journal and Online Date";
  }

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

    // 1. NEW papers always come first.
    const newA = isNew(a) ? 0 : 1;
    const newB = isNew(b) ? 0 : 1;

    if (newA !== newB) {
      return newA - newB;
    }

    // 2. Within NEW and non-NEW groups, sort by configured
    //    journal order first.
    const orderA = getJournalOrder(a);
    const orderB = getJournalOrder(b);

    if (orderA !== orderB) {
      return orderA - orderB;
    }

    // 3. Fallback to journal name when needed.
    const journalCompare =
      (a.journal || "").localeCompare(b.journal || "");

    if (journalCompare !== 0) {
      return journalCompare;
    }

    // 4. Within the same journal, newest online date first.
    const dateCompare = compareOnlineDateDesc(a, b);

    if (dateCompare !== 0) {
      return dateCompare;
    }

    // 5. Final tie-breaker.
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


function isLikelyArticleNumber(value) {
  const s = String(value || "").trim();

  if (!s) return false;

  // Page ranges are real pages.
  if (/[-–—,]/.test(s)) {
    return false;
  }

  // Common e-locator / article-number forms.
  if (/[A-Za-z]/.test(s)) {
    return true;
  }

  // Long standalone numeric values are usually article IDs.
  if (/^\d{4,}$/.test(s)) {
    return true;
  }

  return false;
}


function buildPublicationInfo(paper) {
  const volume = String(paper.volume || "").trim();
  const number = String(paper.number || "").trim();
  const rawPages = String(paper.pages || "").trim();
  const explicitArticleNumber = String(
    paper.article_number || ""
  ).trim();

  let pages = rawPages;
  let articleNumber = explicitArticleNumber;

  // Some Crossref records place an article ID in the page field.
  // For display, show it as Article No. instead of Pages.
  if (!articleNumber && isLikelyArticleNumber(rawPages)) {
    articleNumber = rawPages;
    pages = "";
  }

  const parts = [];

  if (!volume && (pages || articleNumber)) {
    parts.push("In Press");
  }

  if (volume) {
    parts.push(`Vol. ${escapeHtml(volume)}`);
  }

  if (number) {
    parts.push(`No. ${escapeHtml(number)}`);
  }

  // Article number has higher display priority than pages.
  if (articleNumber) {
    parts.push(`Article No. ${escapeHtml(articleNumber)}`);
  } else if (pages) {
    parts.push(`Pages ${escapeHtml(pages)}`);
  }

  return parts.join(
    ' <span class="sep">|</span> '
  );
}

function groupPageDataByJournal(items) {
  const groups = new Map();

  items.forEach((paper) => {
    const journal = String(
      paper.journal || "Unknown Journal"
    ).trim() || "Unknown Journal";

    if (!groups.has(journal)) {
      groups.set(journal, []);
    }

    groups.get(journal).push(paper);
  });

  // Map preserves the first appearance order from the already
  // filtered/sorted page data. Therefore:
  // - Date sort: journal groups follow the first/latest appearance.
  // - Journal sort: journal groups follow the configured journal order.
  return [...groups.entries()];
}


function renderPaperCard(p) {
  const fresh = isNew(p);
  const doi = p.doi || "";
  const publicationInfo = buildPublicationInfo(p);

  return `
    <article class="paper${fresh ? " is-new" : ""}">
      <div class="paper-title-row">
        <div class="title">
          ${
            p.doi
              ? `<a class="paper-title-link"
                   href="${buildDoiUrl(p.doi)}"
                   target="_blank"
                   rel="noopener noreferrer">
                   ${escapeHtml(p.title || "")}
                 </a>`
              : escapeHtml(p.title || "")
          }
          ${fresh ? '<span class="badge">NEW</span>' : ""}
        </div>

        <button type="button"
                class="bibtex-btn"
                title="Copy BibTeX to clipboard">
          BibTeX
        </button>
      </div>

      <div class="author">
        ${escapeHtml(p.authors || "")}
      </div>

      ${
        publicationInfo
          ? `<div class="meta">
               ${publicationInfo}
             </div>`
          : ""
      }

      <div class="meta">
        <span class="meta-part">Online: ${escapeHtml(p.online_date || "N/A")}</span>
        <span class="sep">|</span>
        <span class="meta-part">Fetched (GMT+8): ${escapeHtml(p.fetched_date || "N/A")}</span>
        <br>
        <a href="${buildDoiUrl(doi)}"
           target="_blank"
           rel="noopener noreferrer">
           DOI: ${escapeHtml(doi)}
        </a>
      </div>
    </article>
  `;
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

  const journalGroups = groupPageDataByJournal(pageData);
  const renderedPapers = [];

  paperList.innerHTML = journalGroups.map(([journal, journalPapers]) => {
    const cards = journalPapers.map((paper) => {
      renderedPapers.push(paper);
      return renderPaperCard(paper);
    }).join("");

    return `
      <section class="journal-group">
        <h2 class="journal-group-title">
          ${escapeHtml(journal)}
        </h2>
        <div class="journal-group-papers">
          ${cards}
        </div>
      </section>
    `;
  }).join("");

  paperList
    .querySelectorAll(".bibtex-btn")
    .forEach((button, index) => {
      button.addEventListener("click", () => {
        copyBibtex(renderedPapers[index], button);
      });
    });

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
