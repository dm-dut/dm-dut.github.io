const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const DATA = {};
const TYPE_ORDER = ["Monograph", "Book Chapter", "Journal Article", "Conference Paper", "Other"];
let PUB_DISPLAY_LANG = "en";

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
    const y = $("#pub-year-filter"), t = $("#pub-type-filter"), e = $("#pub-esi-filter"), q = $("#pub-search");
    if(y) y.value = "all";
    if(t) t.value = "all";
    if(e) e.value = "all";
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

function copyTextFallback(text){
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.style.position = "fixed";
  ta.style.left = "-9999px";
  document.body.appendChild(ta);
  ta.select();
  try{ document.execCommand("copy"); }catch(err){}
  document.body.removeChild(ta);
}

function copyTextToClipboard(text){
  if(navigator.clipboard && window.isSecureContext){
    return navigator.clipboard.writeText(text);
  }
  return new Promise((resolve, reject) => {
    try{
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      resolve();
    }catch(err){ reject(err); }
  });
}

function initBibtexButtons(){
  // Delegated click handler: publication entries are re-rendered after filters,
  // so binding to document is more stable than binding individual buttons.
  if(window.__homepageBibtexHandlerInstalled) return;
  window.__homepageBibtexHandlerInstalled = true;

  document.addEventListener("click", async (e) => {
    const btn = e.target.closest(".bib-btn");
    if(!btn) return;
    e.preventDefault();
    e.stopPropagation();

    const targetId = btn.getAttribute("data-bib-target");
    const box = targetId ? document.getElementById(targetId) : btn.closest(".pub")?.querySelector(".bibtex-box");
    if(!box) return;

    const wasOpen = box.classList.contains("open");

    document.querySelectorAll(".bibtex-box.open").forEach(el => {
      if(el !== box){
        el.classList.remove("open");
        el.setAttribute("aria-hidden", "true");
      }
    });
    document.querySelectorAll(".bib-btn").forEach(b => {
      if(b !== btn){
        b.classList.remove("copied");
        b.textContent = "BibTeX";
        b.setAttribute("aria-expanded", "false");
      }
    });

    const isOpen = !wasOpen;
    box.classList.toggle("open", isOpen);
    box.setAttribute("aria-hidden", isOpen ? "false" : "true");
    btn.setAttribute("aria-expanded", isOpen ? "true" : "false");
    btn.textContent = isOpen ? "Hide BibTeX" : "BibTeX";

    if(isOpen){
      const bib = box.textContent || box.innerText || "";
      try{
        await copyTextToClipboard(bib);
        btn.classList.add("copied");
        btn.textContent = "Copied";
        setTimeout(() => {
          btn.classList.remove("copied");
          if(box.classList.contains("open")) btn.textContent = "Hide BibTeX";
        }, 1200);
      }catch(err){
        // Clipboard may be blocked in local file previews. The BibTeX block
        // remains visible so users can still select and copy it manually.
      }
    }
  });
}

function initTheme(){
  const btn = $("#theme-toggle");
  const saved = localStorage.getItem("homepage-theme") || "light";
  document.documentElement.setAttribute("data-theme", saved);
  if(btn) btn.textContent = saved === "dark" ? "Light" : "Dark";
  if(btn){
    btn.addEventListener("click", () => {
      const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("homepage-theme", next);
      btn.textContent = next === "dark" ? "Light" : "Dark";
    });
  }
}

function initTabs(){
  initTheme();
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

function splitNewsLinkField(value){
  if(Array.isArray(value)){
    return value.flatMap(v => splitNewsLinkField(v));
  }
  return String(value || "")
    .split(/[;；]/)
    .map(u => u.trim())
    .filter(Boolean);
}

function normalizeNewsLinks(n){
  const raw = [
    ...splitNewsLinkField(n.links),
    ...splitNewsLinkField(n.link)
  ];
  const seen = new Set();
  return raw
    .map(u => String(u || "").trim())
    .filter(u => u && !seen.has(u) && seen.add(u))
    .filter(u => !(String(n.category||"").toLowerCase() === "talk" && /doi\.org/i.test(u)));
}

function newsCategoryClass(category){
  return String(category || "News").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "news";
}

function renderNewsItem(n){
  const category = n.category || "News";
  const linkList = normalizeNewsLinks(n);
  const links = linkList.map((url, idx) => externalLink(url, linkList.length > 1 ? `↗${idx + 1}` : "↗")).join("");
  return `<li class="item news-item news-card">
    <div class="news-date-box">${esc(n.date || "")}</div>
    <div class="news-main">
      <div class="news-head"><span class="news-tag news-tag-${esc(newsCategoryClass(category))}">${esc(category)}</span></div>
      <div class="news-body"><span class="news-text">${esc(n.content)}</span>${links}</div>
    </div>
  </li>`;
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
function pickLang(p, base){
  if(PUB_DISPLAY_LANG === "zh") return p[`${base}_zh`] || p[`${base}_cn`] || p[base] || p[`${base}_en`] || "";
  return p[`${base}_en`] || p[base] || p[`${base}_zh`] || p[`${base}_cn`] || "";
}
function displayTitle(p){ return pickLang(p, "title"); }
function displayVenue(p){ return pickLang(p, "venue"); }
function displayAuthors(p){
  const field = PUB_DISPLAY_LANG === "zh" ? (p.authors_zh || p.authors_cn || p.authors || p.authors_en) : (p.authors_en || p.authors || p.authors_zh || p.authors_cn);
  return Array.isArray(field) ? field : String(field||"").split(/;|,/).map(x=>x.trim()).filter(Boolean);
}
function authorHtml(pub){
  const list = displayAuthors(pub);
  return list.map(a => {
    const clean = String(a);
    const starred = clean.endsWith("*");
    const base = starred ? clean.slice(0,-1) : clean;
    const strong = (base === "Zhang, Zhen" || base === "Zhen Zhang" || base === "张震") ? `<strong>${esc(base)}</strong>` : esc(base);
    return strong + (starred ? "*" : "");
  }).join(PUB_DISPLAY_LANG === "zh" ? "，" : ", ");
}
function detailLine(p){
  const bits = [];
  const venue = displayVenue(p);
  if(p.type === "Monograph" || p.type === "Book Chapter"){
    if(venue) bits.push(venue);
    if(p.address) bits.push(p.address);
    if(p.isbn) bits.push(`ISBN: ${p.isbn}`);
  }else if(p.type === "Conference Paper"){
    if(venue) bits.push(venue);
    if(p.conference_date) bits.push(p.conference_date);
    if(p.conference_address) bits.push(p.conference_address);
    const proc = [p.volume ? `Vol. ${p.volume}` : "", p.pages ? `pp. ${p.pages}` : ""].filter(Boolean).join(", ");
    if(proc) bits.push(proc);
  }else{
    if(venue) bits.push(venue);
    const volumeIssue = `${p.volume || ""}${p.issue ? `(${p.issue})` : ""}`;
    if(volumeIssue) bits.push(volumeIssue);
    if(p.pages) bits.push(p.pages);
  }
  if(p.year) bits.push(p.year);
  return bits.filter(Boolean).join(PUB_DISPLAY_LANG === "zh" ? "，" : ", ");
}
function tagHtml(p){
  const tags = [...(Array.isArray(p.indexes) ? p.indexes : []), ...(Array.isArray(p.labels) ? p.labels : [])];
  const note = PUB_DISPLAY_LANG === "zh" ? (p.note_zh || p.note_cn || p.note) : (p.note_en || p.note);
  if(note) tags.push(note);
  return tags.map(t => `<span class="pub-tag">${esc(t)}</span>`).join("");
}
function doiUrl(doi){
  if(!doi) return "";
  const d = String(doi).replace(/^https?:\/\/(dx\.)?doi\.org\//i, "").trim();
  return d ? `https://doi.org/${d}` : "";
}
function bibtexType(p){
  if(p.type === "Conference Paper") return "inproceedings";
  if(p.type === "Monograph") return "book";
  if(p.type === "Book Chapter") return "incollection";
  return "article";
}
function bibtexKey(p, idx){
  const authors = displayAuthors(p).join(" ");
  const first = (authors.replace(/\*/g, "").match(/[A-Za-z]+/) || ["Zhang"])[0];
  const year = String(p.year || "n.d.").replace(/\D/g, "") || "nd";
  const titleWord = (displayTitle(p).match(/[A-Za-z0-9]+/) || ["paper"])[0];
  return `${first}${year}${titleWord}${idx}`.replace(/[^A-Za-z0-9_:-]/g, "");
}
function bibtexEntry(p, idx){
  const type = bibtexType(p);
  const authors = displayAuthors(p).join(" and ").replace(/\*/g, "");
  const fields = [];
  if(authors) fields.push(["author", authors]);
  const title = displayTitle(p);
  if(title) fields.push(["title", title]);
  if(p.year) fields.push(["year", String(p.year)]);
  const venue = displayVenue(p);
  if(venue){
    const name = type === "inproceedings" ? "booktitle" : (type === "book" ? "publisher" : "journal");
    fields.push([name, venue]);
  }
  if(p.volume) fields.push(["volume", String(p.volume)]);
  if(p.issue) fields.push(["number", String(p.issue)]);
  if(p.pages) fields.push(["pages", String(p.pages).replace(/–/g, "--")]);
  const doi = (p.doi || "").toString().replace(/^https?:\/\/(dx\.)?doi\.org\//i, "").trim();
  if(doi) fields.push(["doi", doi]);
  if(p.isbn) fields.push(["isbn", p.isbn]);
  const body = fields.map(([k,v]) => `  ${k} = {${String(v).replace(/[{}]/g, "")}}`).join(",\n");
  return `@${type}{${bibtexKey(p, idx)},\n${body}\n}`;
}
function scholarUrl(p){
  return (p.google_scholar_url || p.google_scholar_link || p.scholar_url || p.scholar_link || "").toString().trim();
}
function googleScholarSearchUrl(p){
  const title = displayTitle(p) || p.title_en || p.title_zh || p.title || "";
  return title ? `https://scholar.google.com/scholar?q=${encodeURIComponent(title)}` : "";
}
function citationValueForDisplay(p){
  // Important: citation value may be numeric 0. Do not treat 0 as empty.
  const candidates = [
    p.google_scholar_citations,
    p.google_scholar_citation,
    p.google_scholar_cited_by_count,
    p.scholar_citations,
    p.scholar_citation_count,
    p.citations
  ];
  if(p.cited_by && typeof p.cited_by === "object"){
    candidates.push(p.cited_by.value, p.cited_by.total, p.cited_by.count);
  }
  for(const raw of candidates){
    if(raw === null || raw === undefined) continue;
    const value = String(raw).trim();
    if(value !== "" && value !== "—" && value.toLowerCase() !== "nan") return value;
  }
  return "";
}
function publicationExtraHtml(p, idx){
  const parts = [];
  const doi = (p.doi || "").toString().replace(/^https?:\/\/(dx\.)?doi\.org\//i, "").trim();
  if(doi){
    parts.push(`<a class="pub-doi" href="${esc(doiUrl(doi))}" target="_blank" rel="noopener">DOI: ${esc(doi)}</a>`);
  }

  // Prefer the Scholar record URL generated by scripts/update_publication_citations.py.
  // If the citation script has not matched a paper yet, still provide a Scholar search link
  // so the Scholar entry does not disappear from the publication card.
  const directGsUrl = scholarUrl(p);
  const gsUrl = directGsUrl || googleScholarSearchUrl(p);
  const cites = citationValueForDisplay(p);
  if(gsUrl){
    const label = cites !== "" ? `Google Scholar Citation: ${esc(cites)}` : "Google Scholar";
    parts.push(`<a class="pub-citations" href="${esc(gsUrl)}" target="_blank" rel="noopener">${label}</a>`);
  }else if(cites !== ""){
    parts.push(`<span class="pub-citations">Google Scholar Citation: ${esc(cites)}</span>`);
  }

  const bibId = `bibtex-${idx}-${Math.random().toString(36).slice(2, 8)}`;
  const bib = bibtexEntry(p, idx);
  parts.push(`<button class="bib-btn" type="button" data-bib-target="${esc(bibId)}" aria-expanded="false">BibTeX</button>`);
  return `<div class="pub-extra">${parts.join(`<span class="sep">|</span>`)}</div><pre id="${esc(bibId)}" class="bibtex-box" aria-hidden="true">${esc(bib)}</pre>`;
}
function formatPublication(p, idx=0){
  const link = p.link || doiUrl(p.doi);
  const titleText = displayTitle(p);
  const title = link ? `<a href="${esc(link)}" target="_blank" rel="noopener">${esc(titleText || "")}</a>` : esc(titleText || "");
  return `<article class="pub">
    <div class="pub-title">${title}</div>
    <div class="pub-authors">${authorHtml(p)}</div>
    <div class="pub-meta">${esc(detailLine(p))}</div>
    ${publicationExtraHtml(p, idx)}
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
  const yr = $("#pub-year-filter").value, type = $("#pub-type-filter").value, esi = $("#pub-esi-filter") ? $("#pub-esi-filter").value : "all", q = ($("#pub-search").value||"").toLowerCase();
  const items = all.filter(p => {
    const tagsText = [arrayText(p.indexes), arrayText(p.labels), p.note, p.note_en, p.note_zh, p.note_cn].join(" ").toLowerCase();
    const text = [arrayText(p.authors), arrayText(p.authors_en), arrayText(p.authors_zh), p.title, p.title_en, p.title_zh, p.title_cn, p.venue, p.venue_en, p.venue_zh, p.venue_cn, tagsText, p.conference_address, p.conference_date].join(" ").toLowerCase();
    const matchEsi = esi === "all" ||
      (esi === "highly" && tagsText.includes("esi highly cited")) ||
      (esi === "hot" && tagsText.includes("esi hot"));
    return (yr==="all" || String(p.year)===yr) && (type==="all" || (p.type||"Other")===type) && matchEsi && (!q || text.includes(q));
  });
  $("#pub-count").textContent = `${items.length} / ${all.length} records`;
  if(!items.length){
    $("#publication-list").innerHTML = `<div class="item">No publications to display.</div>`;
    return;
  }
  if(type === "all"){
    const groups = {};
    items.forEach(p => (groups[p.type || "Other"] ||= []).push(p));
    $("#publication-list").innerHTML = TYPE_ORDER.filter(t=>groups[t]).map(t => `<section class="pub-group"><h3>${esc(t)} <span>${groups[t].length}</span></h3>${groups[t].map((p,i)=>formatPublication(p, `${t}-${i}`)).join("")}</section>`).join("");
  }else{
    $("#publication-list").innerHTML = items.map((p,i)=>formatPublication(p, i)).join("");
  }
}

function parseServiceItem(item){
  const raw = String(item || "").trim();
  if(!raw) return {role:"", organization:"", period:"", note:""};

  let first = raw;
  let note = "";
  if(raw.includes(";")){
    const parts = raw.split(";");
    first = parts.shift().trim();
    note = parts.join("; ").trim();
  }

  let main = first;
  let period = "";
  const periodMatch = first.match(/,\s*((?:since\s+)?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?(?:\s+\d{4})?(?:\s*[-–]\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?(?:\s+\d{4})?|\s*[-–]\s*Present)?|since\s+.+)$/i);
  if(periodMatch){
    period = periodMatch[1].trim();
    main = first.slice(0, periodMatch.index).trim();
  }

  let role = "";
  let organization = main;
  const ofMatch = main.match(/^(.+?)\s+of\s+(.+)$/i);
  if(ofMatch){
    role = ofMatch[1].trim();
    organization = ofMatch[2].trim();
  }else if(main.includes(",")){
    const pieces = main.split(/,(.+)/).map(x=>x.trim()).filter(Boolean);
    role = pieces[0] || "";
    organization = pieces[1] || "";
  }

  return {role, organization, period, note};
}

function renderServiceRecord(s, cat){
  const item = s.item || "";
  const parsed = parseServiceItem(item);
  const role = s.role || parsed.role || "";
  const organization = s.organization || s.journal || s.series || parsed.organization || "";
  const period = s.period || parsed.period || "";
  const note = s.note || parsed.note || "";

  // Editorial Boards are intentionally rendered as a normal text list,
  // not as a two-column/table layout. Prefer the curated item text because
  // it already preserves role, journal/series, period, and past role notes.
  if(String(cat || "").toLowerCase().includes("editorial")){
    const text = item || [
      [role, organization].filter(Boolean).join(" of "),
      period,
      note
    ].filter(Boolean).join("; ");
    return `<li>${esc(text)}</li>`;
  }

  const main = item || [role, organization].filter(Boolean).join(", ");
  const text = [main, period, note].filter(Boolean).join(", ");
  return `<li>${esc(text)}</li>`;
}

function renderServices(){
  const groups = {};
  (DATA.services||[]).forEach(s => (groups[s.category||"Service"] ||= []).push(s));
  $("#services-list").innerHTML = Object.entries(groups).map(([cat,items]) => `
    <div class="service-group">
      <h3>${esc(cat)}</h3>
      <ul>${items.map(s=>renderServiceRecord(s, cat)).join("")}</ul>
    </div>`).join("");
}
function formatFundingAmount(amount){
  const raw = String(amount || "").trim();
  if(!raw) return "";
  const m = raw.match(/^\s*(CNY|RMB|¥)?\s*([0-9]+(?:\.[0-9]+)?)\s*([KkMm])?\s*$/);
  if(!m) return raw;
  const currency = (m[1] || "CNY").toUpperCase() === "RMB" ? "RMB" : "CNY";
  let value = parseFloat(m[2]);
  const unit = (m[3] || "").toUpperCase();
  if(unit === "K") value *= 1000;
  if(unit === "M") value *= 1000000;
  const formatted = Math.round(value).toLocaleString("en-US");
  return `${currency} ${formatted}`;
}
function renderGrants(){
  $("#grants-list").innerHTML = (DATA.grants||[]).map(g => {
    const amount = formatFundingAmount(g.amount);
    const parts = [`[${g.no}] ${g.role}`, g.title, `granted by ${g.funder}${g.grant_no ? " ("+g.grant_no+")" : ""}`, amount, g.period].filter(Boolean);
    return `<li class="item">${esc(parts.join(", "))}.</li>`;
  }).join("");
}
function renderAwards(){
  const items = (DATA.awards||[]).slice().sort((a,b)=>{
    const ay = parseInt(String(a.year||"").match(/\d{4}/)?.[0] || "0", 10);
    const by = parseInt(String(b.year||"").match(/\d{4}/)?.[0] || "0", 10);
    if (by !== ay) return by - ay;
    return String(a.title||"").localeCompare(String(b.title||""));
  });

  $("#awards-list").innerHTML = items.map(a => {
    const org = a.organization ? `<div class="award-org">${esc(a.organization)}</div>` : "";
    return `<li class="award-card">
      <div class="award-year">${esc(a.year)}</div>
      <div class="award-main">
        <div class="award-title">${esc(a.title)}</div>
        ${org}
      </div>
    </li>`;
  }).join("");
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
  initBibtexButtons();
  renderProfile();
  renderScholar();
  const [news, awards, grants, services, group, publications] = await Promise.all([
    loadJson("data/news.json"), loadJson("data/awards.json"), loadJson("data/grants.json"),
    loadJson("data/services.json"), loadJson("data/group.json"), loadJson("data/publications.json")
  ]);
  Object.assign(DATA, {news, awards, grants, services, group, publications});
  renderHomeNews(); renderNews(); renderPublications(); renderServices(); renderGrants(); renderAwards(); renderGroup();
  ["#news-year-filter","#news-category-filter"].forEach(s => $(s).addEventListener("change", renderNews));
  ["#pub-year-filter","#pub-type-filter","#pub-esi-filter"].forEach(s => $(s).addEventListener("change", renderPublications));
  $$("[data-pub-lang]").forEach(btn => btn.addEventListener("click", () => {
    PUB_DISPLAY_LANG = btn.dataset.pubLang || "en";
    $$("[data-pub-lang]").forEach(b => b.classList.toggle("active", b === btn));
    renderPublications();
  }));
  $("#pub-search").addEventListener("input", renderPublications);
}
init();