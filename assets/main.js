const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const DATA = {};
const TYPE_ORDER = ["Monograph", "Book Chapter", "Journal Article", "Conference Paper", "Other"];

function esc(s){ return (s ?? "").toString().replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m])); }
function externalLink(url, label="Link"){
  return url ? `<a class="mini-link" href="${esc(url)}" target="_blank" rel="noopener">${esc(label)}</a>` : "";
}
async function loadJson(path, fallback=[]){
  try{
    const res = await fetch(path, {cache:"no-store"});
    if(!res.ok) throw new Error(path);
    return await res.json();
  }catch(e){ return fallback; }
}

function resetTabState(tab){
  if(tab === "publications"){
    const y = $("#pub-year-filter"), t = $("#pub-type-filter"), q = $("#pub-search");
    if(y) y.value = "all";
    if(t) t.value = "all";
    if(q) q.value = "";
    if(DATA.publications) renderPublications();
  }
  if(tab === "news"){
    const y = $("#news-year-filter"), c = $("#news-category-filter");
    if(y) y.value = "all";
    if(c) c.value = "all";
    if(DATA.news) renderNews();
  }
}
function activateTab(tab){
  const current = ($$(".tab").find(t => t.classList.contains("active")) || {}).id;
  $$(".nav button").forEach(b=>b.classList.toggle("active", b.dataset.tab===tab));
  $$(".tab").forEach(t=>t.classList.toggle("active", t.id===tab));
  // Always restore filterable tabs to their default view when a tab button is activated.
  // This keeps Publications/News from retaining stale filters after navigation.
  if(current !== tab || ["publications", "news"].includes(tab)) resetTabState(tab);
  history.replaceState(null, "", `#${tab}`);
  window.scrollTo({top:0, behavior:"smooth"});
}
function initTabs(){
  $$(".nav button").forEach(btn => btn.addEventListener("click", () => activateTab(btn.dataset.tab)));
  $$('[data-jump]').forEach(btn => btn.addEventListener('click', () => activateTab(btn.dataset.jump)));
  const hash = location.hash.replace("#", "");
  if(hash && document.getElementById(hash)) activateTab(hash);
}

function renderProfile(){
  const p = SITE_CONFIG.profile;
  $("#profile-name").textContent = p.name;
  $("#profile-title").textContent = p.title;
  $("#profile-affiliation").textContent = p.affiliation;
  $("#profile-contact").textContent = `${p.address} · E-mail: ${p.email}`;
  $("#profile-portrait").src = p.portrait;
  $("#profile-bio").innerHTML = p.bio.map(x=>`<p>${esc(x)}</p>`).join("");
  $("#keywords").innerHTML = p.researchKeywords.map(k=>`<span class="keyword">${esc(k)}</span>`).join("");
  $("#profile-links").innerHTML = SITE_CONFIG.links.map(l=>`<a class="pill" target="_blank" rel="noopener" href="${esc(l.url)}">${esc(l.label)}</a>`).join("");
}

async function renderScholar(){
  const fallback = SITE_CONFIG.scholar.fallbackStats || {};
  let s = {};

  try {
    s = await loadJson(SITE_CONFIG.scholar.statsJson, {});
  } catch (err) {
    s = {};
  }

  const citations = s.citations || fallback.citations || "—";
  const hindex = s.h_index || s.hindex || fallback.h_index || "—";
  const i10 = s.i10_index || s.i10 || fallback.i10_index || "—";
  const updated = s.updated || fallback.updated || "";

  $("#gs-citations").textContent = citations;
  $("#gs-hindex").textContent = hindex;
  $("#gs-i10").textContent = i10;

  // Keep this area intentionally minimal. Do not show default placeholder
  // text such as "Google Scholar profile" when the JSON request is blocked
  // by browser cache, local file preview, or network restrictions.
  const cleanUpdated = (/^\d{4}[-/]\d{1,2}[-/]\d{1,2}$|^\d{4}[-/]\d{1,2}$/.test(String(updated))) ? updated : "";
  $("#gs-status").innerHTML = cleanUpdated ? `<span>Last updated: ${esc(cleanUpdated)}</span>` : "";
}

function sortByDateDesc(a,b){ return String(b.date||"").localeCompare(String(a.date||"")); }
function yearOfDate(d){ return String(d||"").slice(0,4); }

function renderNewsItem(n){
  const isTalkDoi = String(n.category||"").toLowerCase() === "talk" && /doi\.org/i.test(String(n.link||""));
  const link = isTalkDoi ? "" : externalLink(n.link, n.link_text || "↗");
  return `<li class="item news-item"><span class="item-date">${esc(n.date)}</span><span class="news-category"><span class="tag">${esc(n.category||"News")}</span></span><span class="news-body"><span class="news-text">${esc(n.content)}</span>${link}</span></li>`;
}

function renderHomeNews(){
  const items = (DATA.news||[]).filter(n => String(n.show_on_home||"").toLowerCase() !== "no").sort(sortByDateDesc).slice(0,12);
  $("#home-news").innerHTML = items.map(renderNewsItem).join("");
}

function buildSelect(select, values, allLabel){
  const el = $(select);
  const current = el.value || "all";
  el.innerHTML = `<option value="all">${allLabel}</option>` + values.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join("");
  el.value = values.includes(current) ? current : "all";
}

function renderNews(){
  const all = (DATA.news||[]).sort(sortByDateDesc);
  buildSelect("#news-year-filter", [...new Set(all.map(n=>yearOfDate(n.date)).filter(Boolean))].sort((a,b)=>b.localeCompare(a)), "All years");
  buildSelect("#news-category-filter", [...new Set(all.map(n=>n.category||"News"))].sort(), "All categories");
  const yr = $("#news-year-filter").value, cat = $("#news-category-filter").value;
  const items = all.filter(n => (yr==="all" || yearOfDate(n.date)===yr) && (cat==="all" || (n.category||"News")===cat));
  $("#news-list").innerHTML = items.map(renderNewsItem).join("");
}

function arrayText(x){ return Array.isArray(x) ? x.join(", ") : (x || ""); }
function authorHtml(authors){
  const list = Array.isArray(authors) ? authors : String(authors||"").split(/;|,/).map(x=>x.trim()).filter(Boolean);
  return list.map(a => {
    const clean = String(a);
    const starred = clean.endsWith("*");
    const base = starred ? clean.slice(0,-1) : clean;
    const strong = base === "Zhen Zhang" ? `<strong>${esc(base)}</strong>` : esc(base);
    return strong + (starred ? "*" : "");
  }).join(", ");
}
function detailLine(p){
  const bits = [];
  if(p.type === "Monograph" || p.type === "Book Chapter"){
    if(p.venue) bits.push(p.venue);
    if(p.address) bits.push(p.address);
    if(p.isbn) bits.push(`ISBN: ${p.isbn}`);
  }else if(p.type === "Conference Paper"){
    if(p.venue) bits.push(p.venue);
    if(p.conference_date) bits.push(p.conference_date);
    if(p.conference_address) bits.push(p.conference_address);
    const proc = [p.volume ? `Vol. ${p.volume}` : "", p.pages ? `pp. ${p.pages}` : ""].filter(Boolean).join(", ");
    if(proc) bits.push(proc);
  }else{
    if(p.venue) bits.push(p.venue);
    const volumeIssue = `${p.volume || ""}${p.issue ? `(${p.issue})` : ""}`;
    if(volumeIssue) bits.push(volumeIssue);
    if(p.pages) bits.push(p.pages);
  }
  if(p.year) bits.push(p.year);
  return bits.filter(Boolean).join(", ");
}
function tagHtml(p){
  const tags = [...(Array.isArray(p.indexes) ? p.indexes : []), ...(Array.isArray(p.labels) ? p.labels : [])];
  if(p.note) tags.push(p.note);
  return tags.map(t => `<span class="pub-tag">${esc(t)}</span>`).join("");
}
function doiUrl(doi){
  if(!doi) return "";
  const d = String(doi).replace(/^https?:\/\/(dx\.)?doi\.org\//i, "").trim();
  return d ? `https://doi.org/${d}` : "";
}
function publicationExtraHtml(p){
  const parts = [];
  const doi = (p.doi || "").toString().replace(/^https?:\/\/(dx\.)?doi\.org\//i, "").trim();
  if(doi){
    parts.push(`<a class="pub-doi" href="${esc(doiUrl(doi))}" target="_blank" rel="noopener">DOI: ${esc(doi)}</a>`);
  }
  const isChinese = String(p.language || "").toLowerCase().startsWith("zh") || String(p.language || "").includes("中文");
  const cites = p.google_scholar_citations ?? p.citations ?? "";
  if(!isChinese && cites !== "" && cites !== null && String(cites) !== "—"){
    const label = `Google Scholar Citations: ${esc(cites)}`;
    if(p.google_scholar_url){
      parts.push(`<a class="pub-citations" href="${esc(p.google_scholar_url)}" target="_blank" rel="noopener">${label}</a>`);
    }else{
      parts.push(`<span class="pub-citations">${label}</span>`);
    }
  }
  return parts.length ? `<div class="pub-extra">${parts.join(`<span class="sep">|</span>`)}</div>` : "";
}
function formatPublication(p){
  const link = p.link || doiUrl(p.doi);
  const title = link ? `<a href="${esc(link)}" target="_blank" rel="noopener">${esc(p.title || "")}</a>` : esc(p.title || "");
  return `<article class="pub">
    <div class="pub-title">${title}</div>
    <div class="pub-authors">${authorHtml(p.authors)}</div>
    <div class="pub-meta">${esc(detailLine(p))}</div>
    ${publicationExtraHtml(p)}
    ${tagHtml(p) ? `<div class="pub-tags">${tagHtml(p)}</div>` : ""}
  </article>`;
}
function sortPublications(a,b){
  const ya = Number(a.year || 0), yb = Number(b.year || 0);
  if(yb !== ya) return yb - ya;
  return TYPE_ORDER.indexOf(a.type||"Other") - TYPE_ORDER.indexOf(b.type||"Other");
}
function renderPublications(){
  const all = (DATA.publications||[]).slice().sort(sortPublications);
  buildSelect("#pub-year-filter", [...new Set(all.map(p=>String(p.year||"")).filter(Boolean))].sort((a,b)=>b.localeCompare(a)), "All years");
  buildSelect("#pub-type-filter", [...new Set(all.map(p=>p.type||"Other"))].sort((a,b)=>TYPE_ORDER.indexOf(a)-TYPE_ORDER.indexOf(b)), "All types");
  const yr = $("#pub-year-filter").value, type = $("#pub-type-filter").value, q = ($("#pub-search").value||"").toLowerCase();
  const items = all.filter(p => {
    const text = [arrayText(p.authors),p.title,p.venue,arrayText(p.indexes),arrayText(p.labels),p.note,p.conference_address,p.conference_date].join(" ").toLowerCase();
    return (yr==="all" || String(p.year)===yr) && (type==="all" || (p.type||"Other")===type) && (!q || text.includes(q));
  });
  $("#pub-count").textContent = `${items.length} / ${all.length} records`;
  if(!items.length){
    $("#publication-list").innerHTML = `<div class="item">No publications to display.</div>`;
    return;
  }
  if(type === "all"){
    const groups = {};
    items.forEach(p => (groups[p.type || "Other"] ||= []).push(p));
    $("#publication-list").innerHTML = TYPE_ORDER.filter(t=>groups[t]).map(t => `<section class="pub-group"><h3>${esc(t)} <span>${groups[t].length}</span></h3>${groups[t].map(formatPublication).join("")}</section>`).join("");
  }else{
    $("#publication-list").innerHTML = items.map(formatPublication).join("");
  }
}

function renderServices(){
  const groups = {};
  (DATA.services||[]).forEach(s => (groups[s.category||"Service"] ||= []).push(s));
  $("#services-list").innerHTML = Object.entries(groups).map(([cat,items]) => `
    <div class="service-group">
      <h3>${esc(cat)}</h3>
      <ul>${items.map(s=>{
        const main = s.item || [s.role, s.organization].filter(Boolean).join(", ");
        const text = s.period ? `${main}, ${s.period}` : main;
        return `<li>${esc(text)}</li>`;
      }).join("")}</ul>
    </div>`).join("");
}
function renderGrants(){
  $("#grants-list").innerHTML = (DATA.grants||[]).map(g => {
    const text = `[${g.no}] ${g.role}, ${g.title}, granted by ${g.funder}${g.grant_no ? " ("+g.grant_no+")" : ""}, ${g.amount || ""}, ${g.period || ""}.`;
    return `<li class="item">${esc(text)}</li>`;
  }).join("");
}
function renderAwards(){
  const items = (DATA.awards||[]).slice().sort((a,b)=>String(b.year||"").localeCompare(String(a.year||"")));
  $("#awards-list").innerHTML = items.map(a => `<li class="item award-item"><span class="item-date">${esc(a.year)}</span><span>${esc(a.title)}${a.organization ? ` — ${esc(a.organization)}` : ""}</span></li>`).join("");
}
function renderGroup(){
  const groups = {};
  (DATA.group||[]).forEach(g => (groups[g.category||"Member"] ||= []).push(g));
  $("#group-list").innerHTML = Object.entries(groups).map(([cat,items]) => `
    <h3>${esc(cat)}</h3>
    <ul>${items.map(m => `<li>${m.link ? `<a href="${esc(m.link)}" target="_blank" rel="noopener">${esc(m.name)}</a>` : esc(m.name)}${m.note ? ` <span class="meta">(${esc(m.note)})</span>` : ""}</li>`).join("")}</ul>`).join("");
}

async function init(){
  initTabs();
  renderProfile();
  renderScholar();
  const [news, awards, grants, services, group, publications] = await Promise.all([
    loadJson("data/news.json"), loadJson("data/awards.json"), loadJson("data/grants.json"),
    loadJson("data/services.json"), loadJson("data/group.json"), loadJson("data/publications.json")
  ]);
  Object.assign(DATA, {news, awards, grants, services, group, publications});
  renderHomeNews(); renderNews(); renderPublications(); renderServices(); renderGrants(); renderAwards(); renderGroup();
  ["#news-year-filter","#news-category-filter"].forEach(s => $(s).addEventListener("change", renderNews));
  ["#pub-year-filter","#pub-type-filter"].forEach(s => $(s).addEventListener("change", renderPublications));
  $("#pub-search").addEventListener("input", renderPublications);
}
init();
