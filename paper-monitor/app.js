const DATA_URL = "./data/online_papers.json";
const CONFIG = window.PAPER_TRACKER_CONFIG || {};
let allPapers = [];
let currentPublisher = "全部";
let generatedAt = "";
let refreshRunning = false;

const tabsEl = document.getElementById("publisherTabs");
const listEl = document.getElementById("paperList");
const emptyEl = document.getElementById("empty");
const rangeEl = document.getElementById("rangeSelect");
const searchEl = document.getElementById("searchInput");
const statsEl = document.getElementById("stats");
const refreshButtonEl = document.getElementById("refreshButton");
const refreshButtonTextEl = document.getElementById("refreshButtonText");
const refreshStatusEl = document.getElementById("refreshStatus");

function esc(s = "") {
  return String(s).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}

function localDateKey(iso) {
  return iso || "未知日期";
}

function generatedAtLabel(iso) {
  if (!iso) return "尚无更新时间";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

function setRefreshState(state, message = "") {
  refreshStatusEl.textContent = message;
  refreshStatusEl.className = `refresh-status ${state || ""}`.trim();
  refreshButtonEl.disabled = refreshRunning;
  refreshButtonTextEl.textContent = refreshRunning ? "更新中…" : "立即更新";
  refreshButtonEl.classList.toggle("spinning", refreshRunning);
}

function renderTabs() {
  const pubs = ["全部", ...[...new Set(allPapers.map(p => p.publisher).filter(Boolean))].sort()];
  tabsEl.innerHTML = pubs.map(p => `<button class="tab ${p === currentPublisher ? 'active' : ''}" data-pub="${esc(p)}">${esc(p)}</button>`).join("");
  tabsEl.querySelectorAll(".tab").forEach(btn => btn.addEventListener("click", () => {
    currentPublisher = btn.dataset.pub;
    renderTabs();
    render();
  }));
}

function withinRange(p) {
  const v = rangeEl.value;
  if (v === "all") return true;
  if (!p.online_date) return false;
  const cutoff = new Date();
  cutoff.setHours(0,0,0,0);
  cutoff.setDate(cutoff.getDate() - Number(v));
  return new Date(p.online_date + "T00:00:00") >= cutoff;
}

function matchesSearch(p) {
  const q = searchEl.value.trim().toLowerCase();
  if (!q) return true;
  return [p.title, p.journal, p.authors, p.doi].some(v => (v || "").toLowerCase().includes(q));
}

function render() {
  const papers = allPapers.filter(p =>
    (currentPublisher === "全部" || p.publisher === currentPublisher) && withinRange(p) && matchesSearch(p)
  );

  emptyEl.hidden = papers.length > 0;
  const groups = new Map();
  for (const p of papers) {
    const key = localDateKey(p.online_date);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(p);
  }

  let html = "";
  for (const [dateKey, items] of groups.entries()) {
    html += `<div class="date-group">${esc(dateKey)} <span>(${items.length})</span></div>`;
    for (const p of items) {
      const href = p.url || (p.doi ? `https://doi.org/${encodeURIComponent(p.doi)}` : "");
      const title = href ? `<a href="${esc(href)}" target="_blank" rel="noopener">${esc(p.title)}</a>` : esc(p.title);
      html += `
        <article class="paper">
          <div class="meta">
            <span class="badge">${esc(p.publisher)}</span>
            <span>${esc(p.journal)}</span>
            <span>·</span>
            <span>${esc(p.display_date || p.online_date)}</span>
            ${p.content_type ? `<span>· ${esc(p.content_type)}</span>` : ""}
          </div>
          <h2 class="title">${title}</h2>
          ${p.authors ? `<div class="authors">${esc(p.authors)}</div>` : ""}
        </article>`;
    }
  }
  listEl.innerHTML = html;
}

async function fetchFeed(cacheBust = false) {
  const suffix = cacheBust ? `${DATA_URL.includes("?") ? "&" : "?"}t=${Date.now()}` : "";
  const res = await fetch(DATA_URL + suffix, {cache: "no-store"});
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function applyFeed(data) {
  allPapers = data.articles || [];
  generatedAt = data.generated_at || "";
  statsEl.textContent = `${allPapers.length.toLocaleString()} 条记录 · 更新于 ${generatedAtLabel(generatedAt)}`;
  renderTabs();
  render();
}

async function boot() {
  try {
    applyFeed(await fetchFeed(true));
  } catch (e) {
    listEl.innerHTML = `<div class="empty">数据加载失败：${esc(e.message)}</div>`;
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
  throw new Error("更新任务已触发，但网页尚未检测到新的数据文件。可稍后再次点击或刷新页面查看。 ");
}

async function triggerRefresh() {
  if (refreshRunning) return;

  const endpoint = String(CONFIG.refreshEndpoint || "").trim();
  if (!endpoint) {
    setRefreshState("error", "尚未配置安全更新入口，请先填写 paper-monitor/config.js 中的 refreshEndpoint。");
    return;
  }

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
      body: JSON.stringify({source: "web"}),
    });

    let body = {};
    try { body = await res.json(); } catch (_) { /* ignore non-JSON body */ }
    if (!res.ok) {
      throw new Error(body.error || body.message || `触发失败（HTTP ${res.status}）`);
    }

    setRefreshState("working", "更新任务已启动，正在等待新的论文数据…");
    await waitForNewFeed(previousGeneratedAt);
    setRefreshState("success", "更新完成，页面数据已刷新。 ");
  } catch (e) {
    setRefreshState("error", e.message || String(e));
  } finally {
    refreshRunning = false;
    refreshButtonEl.disabled = false;
    refreshButtonTextEl.textContent = "立即更新";
    refreshButtonEl.classList.remove("spinning");
  }
}

rangeEl.addEventListener("change", render);
searchEl.addEventListener("input", render);
refreshButtonEl.addEventListener("click", triggerRefresh);
boot();
