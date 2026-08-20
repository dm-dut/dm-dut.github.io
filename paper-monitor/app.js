const DATA_URL = "./data/online_papers.json";
const CONFIG = window.PAPER_TRACKER_CONFIG || {};
let allPapers = [];
let feedMeta = {};
let generatedAt = "";

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
const refreshStatusEl = document.getElementById("refreshStatus");

function esc(value = "") {
  return String(value).replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));
}
function formatUpdatedAt(iso) {
  if (!iso) return "尚无更新记录";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("zh-CN", {hour12:false});
}
function localDate(value) {
  const d = new Date(`${value || ""}T00:00:00`);
  return Number.isNaN(d.getTime()) ? null : d;
}
function definitions() {
  const rows = feedMeta.filters?.journals;
  if (Array.isArray(rows) && rows.length) return rows;
  const m = new Map();
  for (const p of allPapers) if (p.journal) m.set(`${p.publisher}\0${p.journal}`, {publisher:p.publisher||"", journal:p.journal});
  return [...m.values()];
}
function populatePublishers() {
  const arr = feedMeta.filters?.publishers || [...new Set(allPapers.map(p=>p.publisher).filter(Boolean))].sort();
  const cur = publisherEl.value;
  publisherEl.innerHTML = '<option value="">全部出版社</option>' + arr.map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join("");
  if (arr.includes(cur)) publisherEl.value = cur;
}
function populateJournals() {
  const cur = journalEl.value, pub = publisherEl.value;
  const arr = [...new Set(definitions().filter(x=>!pub || x.publisher===pub).map(x=>x.journal).filter(Boolean))].sort((a,b)=>a.localeCompare(b,"en"));
  journalEl.innerHTML = '<option value="">全部期刊</option>' + arr.map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join("");
  journalEl.value = arr.includes(cur) ? cur : "";
}
function withinRange(p, days=rangeEl.value) {
  if (days === "all") return true;
  const d = localDate(p.fetched_date); if (!d) return false;
  const cutoff = new Date(); cutoff.setHours(0,0,0,0); cutoff.setDate(cutoff.getDate()-Number(days));
  return d >= cutoff;
}
function matches(p) {
  const q = searchEl.value.trim().toLowerCase();
  return !q || [p.title,p.authors,p.journal,p.publisher].some(v=>String(v||"").toLowerCase().includes(q));
}
function comparePapers(a,b) {
  const f = String(b.fetched_date||"").localeCompare(String(a.fetched_date||""));
  if (f) return f;
  const j = String(a.journal||"").localeCompare(String(b.journal||""), "en");
  if (j) return j;
  const d = String(b.online_sort_date||"").localeCompare(String(a.online_sort_date||""));
  if (d) return d;
  return Number(a.source_rank||9999)-Number(b.source_rank||9999);
}
function filtered() {
  const pub=publisherEl.value, journal=journalEl.value;
  return allPapers.filter(p=>(!pub||p.publisher===pub)&&(!journal||p.journal===journal)&&withinRange(p)&&matches(p)).sort(comparePapers);
}
function renderSummary() {
  totalCountEl.textContent = allPapers.length.toLocaleString();
  weekCountEl.textContent = allPapers.filter(p=>withinRange(p,"7")).length.toLocaleString();
  journalCountEl.textContent = String(feedMeta.monitoring?.journal_count ?? definitions().length);
  updatedAtEl.textContent = formatUpdatedAt(generatedAt);
}
function dateBadge(p) {
  if (!p.display_date) return "";
  const label = p.date_kind === "online" ? "Online" : (p.date_kind === "publication" ? "发表" : "日期");
  return `<span class="date-pill">${esc(label)}: ${esc(p.display_date)}</span>`;
}
function render() {
  const papers = filtered();
  resultCountEl.textContent = `当前显示 ${papers.length.toLocaleString()} 条论文`;
  emptyEl.hidden = papers.length > 0;
  const groups = new Map();
  for (const p of papers) {
    const k=p.fetched_date||"未知获取日期";
    if(!groups.has(k)) groups.set(k,[]);
    groups.get(k).push(p);
  }
  let html="";
  for (const [dateKey,items] of groups.entries()) {
    html += `<div class="date-group"><span>获取日期 ${esc(dateKey)}</span><span class="date-count">${items.length} 篇</span></div>`;
    for (const p of items) {
      const title = p.url ? `<a href="${esc(p.url)}" target="_blank" rel="noopener noreferrer">${esc(p.title)}</a>` : esc(p.title);
      html += `<article class="paper-card">
        <div class="paper-meta"><strong>${esc(p.journal||"")}</strong>${dateBadge(p)}</div>
        <h2 class="paper-title">${title}</h2>
        ${p.authors ? `<div class="authors">${esc(p.authors)}</div>` : ""}
      </article>`;
    }
  }
  listEl.innerHTML=html;
}
async function fetchFeed() {
  const res=await fetch(`${DATA_URL}?t=${Date.now()}`,{cache:"no-store"});
  if(!res.ok) throw new Error(`HTTP ${res.status}`);
  const data=await res.json(); if(!data||!Array.isArray(data.articles)) throw new Error("online_papers.json 格式不正确"); return data;
}
function applyFeed(data) {
  feedMeta=data; generatedAt=data.generated_at||"";
  allPapers=[...(data.articles||[])].sort(comparePapers);
  populatePublishers(); populateJournals(); renderSummary(); render();
}
async function boot(){try{applyFeed(await fetchFeed());}catch(e){resultCountEl.textContent="数据加载失败";listEl.innerHTML=`<div class="empty-state"><h2>无法加载论文数据</h2><p>${esc(e.message)}</p></div>`;}}

publisherEl.addEventListener("change",()=>{populateJournals();render();});
journalEl.addEventListener("change",render); rangeEl.addEventListener("change",render); searchEl.addEventListener("input",render);
resetEl.addEventListener("click",()=>{publisherEl.value="";populateJournals();journalEl.value="";rangeEl.value="30";searchEl.value="";render();});
refreshButtonEl.addEventListener("click",()=>{refreshStatusEl.textContent="当前为本地更新模式：运行 update_papers.bat；推送完成后刷新本页。";refreshStatusEl.className="refresh-status working";});
boot();
