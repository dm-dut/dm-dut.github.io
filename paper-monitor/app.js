const DATA_URL = "./data/online_papers.json";
const CONFIG = window.PAPER_TRACKER_CONFIG || {};

let allPapers = [];
let feedMeta = {};
let generatedAt = "";
let refreshRunning = false;

const publisherEl = document.getElementById("publisherSelect");
const journalEl = document.getElementById("journalSelect");
const rangeEl = document.getElementById("rangeSelect");
const searchEl = document.getElementById("searchInput");
const resetEl = document.getElementById("resetButton");
const listEl = document.getElementById("paperList");
const emptyEl = document.getElementById("empty");
const resultCountEl = document.getElementById("resultCount");
const totalCountEl = document.getElementById("totalCount");
const weekCountEl = document.getElementById("weekCount");
const journalCountEl = document.getElementById("journalCount");
const updatedAtEl = document.getElementById("updatedAt");
const refreshButtonEl = document.getElementById("refreshButton");
const refreshButtonTextEl = document.getElementById("refreshButtonText");
const refreshStatusEl = document.getElementById("refreshStatus");

function esc(value = "") {
  return String(value).replace(/[&<>'"]/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
  }[c]));
}

function formatUpdatedAt(iso) {
  if (!iso) return "尚无更新记录";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("zh-CN", { hour12: false });
}

function parsePaperDate(p) {
  if (!p.online_date) return null;
  const d = new Date(`${p.online_date}T00:00:00`);
  return Number.isNaN(d.getTime()) ? null : d;
}

function sourceIsFallback(p) {
  return String(p.source || "").toLowerCase().includes("fallback");
}

function setRefreshState(state, message = "") {
  refreshStatusEl.textContent = message;
  refreshStatusEl.className = `refresh-status ${state || ""}`.trim();
  refreshButtonEl.disabled = refreshRunning;
  refreshButtonTextEl.textContent = refreshRunning ? "更新中…" : "立即更新";
  refreshButtonEl.classList.toggle("spinning", refreshRunning);
}

function availableJournalDefinitions() {
  const defined = feedMeta.filters?.journals;
  if (Array.isArray(defined) && defined.length) return defined;
  const map = new Map();
  for (const p of allPapers) {
    if (!p.journal) continue;
    map.set(`${p.publisher || ""}\u0000${p.journal}`, { publisher: p.publisher || "", journal: p.journal });
  }
  return [...map.values()];
}

function populatePublisherOptions() {
  const configured = feedMeta.filters?.publishers;
  const publishers = Array.isArray(configured) && configured.length
    ? configured
    : [...new Set(allPapers.map(p => p.publisher).filter(Boolean))].sort();
  const current = publisherEl.value;
  publisherEl.innerHTML = '<option value="">全部出版社</option>' +
    publishers.map(p => `<option value="${esc(p)}">${esc(p)}</option>`).join("");
  if (publishers.includes(current)) publisherEl.value = current;
}

function populateJournalOptions() {
  const current = journalEl.value;
  const publisher = publisherEl.value;
  const journals = availableJournalDefinitions()
    .filter(x => !publisher || x.publisher === publisher)
    .map(x => x.journal)
    .filter(Boolean);
  const unique = [...new Set(journals)].sort((a, b) => a.localeCompare(b, "en"));
  journalEl.innerHTML = '<option value="">全部期刊</option>' +
    unique.map(j => `<option value="${esc(j)}">${esc(j)}</option>`).join("");
  journalEl.value = unique.includes(current) ? current : "";
}

function withinRange(p, daysValue = rangeEl.value) {
  if (daysValue === "all") return true;
  const d = parsePaperDate(p);
  if (!d) return false;
  const cutoff = new Date();
  cutoff.setHours(0, 0, 0, 0);
  cutoff.setDate(cutoff.getDate() - Number(daysValue));
  return d >= cutoff;
}

function matchesSearch(p) {
  const q = searchEl.value.trim().toLowerCase();
  if (!q) return true;
  return [p.title, p.journal, p.authors, p.doi, p.publisher]
    .some(v => String(v || "").toLowerCase().includes(q));
}

function filteredPapers() {
  const publisher = publisherEl.value;
  const journal = journalEl.value;
  return allPapers.filter(p =>
    (!publisher || p.publisher === publisher) &&
    (!journal || p.journal === journal) &&
    withinRange(p) &&
    matchesSearch(p)
  );
}

function renderSummary() {
  totalCountEl.textContent = allPapers.length.toLocaleString();
  weekCountEl.textContent = allPapers.filter(p => withinRange(p, "7")).length.toLocaleString();
  journalCountEl.textContent = String(feedMeta.monitoring?.journal_count ?? availableJournalDefinitions().length);
  updatedAtEl.textContent = formatUpdatedAt(generatedAt);
}

function render() {
  const papers = filteredPapers();
  resultCountEl.textContent = `当前显示 ${papers.length.toLocaleString()} 条论文`;
  emptyEl.hidden = papers.length > 0;

  const groups = new Map();
  for (const p of papers) {
    const key = p.online_date || p.display_date || "未知日期";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(p);
  }

  let html = "";
  for (const [dateKey, items] of groups.entries()) {
    html += `<div class="date-group"><span>${esc(dateKey)}</span><span class="date-count">${items.length} 篇</span></div>`;
    for (const p of items) {
      const href = p.url || (p.doi ? `https://doi.org/${encodeURIComponent(p.doi)}` : "");
      const title = href
        ? `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(p.title)}</a>`
        : esc(p.title);
      const fallback = sourceIsFallback(p)
        ? `<span class="source-pill" title="该日期来自备用数据源，具体来源见标签；后续如获得更高优先级日期会自动升级">${esc(p.source)}</span>`
        : "";
      const doiLink = p.doi
        ? `<a href="https://doi.org/${encodeURIComponent(p.doi)}" target="_blank" rel="noopener noreferrer">DOI</a>`
        : "";

      html += `
        <article class="paper-card">
          <div class="paper-meta">
            <span class="publisher-pill">${esc(p.publisher || "")}</span>
            <span>${esc(p.journal || "")}</span>
            ${fallback}
          </div>
          <h2 class="paper-title">${title}</h2>
          ${p.authors ? `<div class="authors">${esc(p.authors)}</div>` : ""}
          ${doiLink ? `<div class="paper-links">${doiLink}</div>` : ""}
        </article>`;
    }
  }
  listEl.innerHTML = html;
}

async function fetchFeed(cacheBust = false) {
  const suffix = cacheBust ? `${DATA_URL.includes("?") ? "&" : "?"}t=${Date.now()}` : "";
  const res = await fetch(DATA_URL + suffix, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  if (!data || !Array.isArray(data.articles)) {
    throw new Error("online_papers.json 格式不正确：缺少 articles 数组");
  }
  return data;
}

function applyFeed(data) {
  feedMeta = data;
  allPapers = [...(data.articles || [])].sort((a, b) =>
    String(b.online_date || "").localeCompare(String(a.online_date || ""))
  );
  generatedAt = data.generated_at || "";
  populatePublisherOptions();
  populateJournalOptions();
  renderSummary();
  render();
}

async function boot() {
  try {
    applyFeed(await fetchFeed(true));
  } catch (e) {
    resultCountEl.textContent = "数据加载失败";
    listEl.innerHTML = `<div class="empty-state"><h2>无法加载论文数据</h2><p>${esc(e.message)}</p></div>`;
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function waitForNewFeed(previousGeneratedAt) {
  const interval = Number(CONFIG.refreshPollIntervalMs || 5000);
  const timeout = Number(CONFIG.refreshTimeoutMs || 600000);
  const deadline = Date.now() + timeout;

  while (Date.now() < deadline) {
    await sleep(interval);
    const data = await fetchFeed(true);
    if (data.generated_at && data.generated_at !== previousGeneratedAt) {
      applyFeed(data);
      return data;
    }
  }
  throw new Error("更新任务可能仍在运行。请稍后刷新页面查看最新数据。");
}

async function triggerSecureRefresh(endpoint) {
  const password = window.prompt("请输入数据更新密码：");
  if (password === null) return;
  if (!password) {
    setRefreshState("error", "未输入更新密码。");
    return;
  }

  refreshRunning = true;
  setRefreshState("working", "正在触发数据更新…");
  const previousGeneratedAt = generatedAt;

  try {
    const res = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Refresh-Password": password,
      },
      body: JSON.stringify({ source: "web" }),
    });

    let body = {};
    try { body = await res.json(); } catch (_) { /* ignore non-JSON body */ }
    if (!res.ok) throw new Error(body.error || body.message || `触发失败（HTTP ${res.status}）`);

    setRefreshState("working", "更新任务已启动，正在等待新的论文数据…");
    await waitForNewFeed(previousGeneratedAt);
    setRefreshState("success", "更新完成，页面数据已刷新。");
  } catch (e) {
    setRefreshState("error", e.message || String(e));
  } finally {
    refreshRunning = false;
    refreshButtonEl.disabled = false;
    refreshButtonTextEl.textContent = "立即更新";
    refreshButtonEl.classList.remove("spinning");
  }
}

async function triggerRefresh() {
  if (refreshRunning) return;
  const endpoint = String(CONFIG.refreshEndpoint || "").trim();
  if (endpoint) {
    await triggerSecureRefresh(endpoint);
    return;
  }

  // A static GitHub Pages site cannot safely store a GitHub token. If the
  // optional secure Worker has not been deployed yet, open the authenticated
  if (CONFIG.localMode) {
    setRefreshState("working", "当前为本地更新模式：请在本地 dm-dut.github.io 目录双击 update_papers.bat；推送完成后刷新本页即可。");
    return;
  }

  const actionsUrl = String(CONFIG.actionsUrl || "").trim();
  if (actionsUrl) {
    window.open(actionsUrl, "_blank", "noopener,noreferrer");
    setRefreshState("working", "已打开 GitHub Actions。运行更新工作流后，返回本页刷新即可。");
    return;
  }
  setRefreshState("error", "未配置安全更新入口。");
}

publisherEl.addEventListener("change", () => {
  populateJournalOptions();
  render();
});
journalEl.addEventListener("change", render);
rangeEl.addEventListener("change", render);
searchEl.addEventListener("input", render);
resetEl.addEventListener("click", () => {
  publisherEl.value = "";
  populateJournalOptions();
  journalEl.value = "";
  rangeEl.value = "30";
  searchEl.value = "";
  render();
});
refreshButtonEl.addEventListener("click", triggerRefresh);

boot();
