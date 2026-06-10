const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const DATA = {};

function esc(s){ return (s ?? "").toString().replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m])); }
function linkify(text, url){
  const safe = esc(text);
  return url ? `<a href="${esc(url)}" target="_blank" rel="noopener">${safe}</a>` : safe;
}
async function loadJson(path, fallback=[]){
  try{
    const res = await fetch(path, {cache:"no-store"});
    if(!res.ok) throw new Error(path);
    return await res.json();
  }catch(e){ return fallback; }
}

function activateTab(tab){
  $$(".nav button").forEach(b=>b.classList.toggle("active", b.dataset.tab===tab));
  $$(".tab").forEach(t=>t.classList.toggle("active", t.id===tab));
  window.scrollTo({top:0, behavior:"smooth"});
}
function initTabs(){
  $$(".nav button").forEach(btn => btn.addEventListener("click", () => activateTab(btn.dataset.tab)));
  $$('[data-jump]').forEach(btn => btn.addEventListener('click', () => activateTab(btn.dataset.jump)));
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
  const s = await loadJson(SITE_CONFIG.scholar.statsJson, {});
  $("#gs-citations").textContent = s.citations || "—";
  $("#gs-hindex").textContent = s.h_index || s.hindex || "—";
  $("#gs-i10").textContent = s.i10_index || s.i10 || "—";
  $("#gs-updated").textContent = s.updated || "—";
}

function sortByDateDesc(a,b){ return String(b.date||"").localeCompare(String(a.date||"")); }
function yearOfDate(d){ return String(d||"").slice(0,4); }

function renderHomeNews(){
  const items = (DATA.news||[]).filter(n => String(n.show_on_home||"").toLowerCase() !== "no").sort(sortByDateDesc).slice(0,12);
  $("#home-news").innerHTML = items.map(n => `<li class="item"><span class="item-date">${esc(n.date)}</span><span class="tag">${esc(n.category||"News")}</span>${linkify(n.content,n.link)}</li>`).join("");
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
  $("#news-list").innerHTML = items.map(n => `<li class="item"><span class="item-date">${esc(n.date)}</span><span class="tag">${esc(n.category||"News")}</span>${linkify(n.content,n.link)}</li>`).join("");
}

function formatPublication(p){
  const doiUrl = p.doi ? (String(p.doi).startsWith("http") ? p.doi : `https://doi.org/${p.doi}`) : (p.link||"");
  const meta = [p.venue, p.volume, p.issue ? `(${p.issue})` : "", p.pages].filter(Boolean).join(" ");
  const tags = [p.indexes, p.labels, p.note].filter(Boolean).join("; ");
  return `<div class="pub">
    <span class="pub-meta">${esc(p.authors || "")}.</span>
    <span class="pub-title"> ${linkify(p.title || "", doiUrl)}</span>
    <span class="pub-meta"> ${esc(meta)}${p.year ? ", " + esc(p.year) : ""}.</span>
    ${tags ? `<div class="pub-note">${esc(tags)}</div>` : ""}
  </div>`;
}

function renderPublications(){
  const all = (DATA.publications||[]).slice().sort((a,b)=> Number(b.year||0)-Number(a.year||0));
  buildSelect("#pub-year-filter", [...new Set(all.map(p=>String(p.year||"")).filter(Boolean))].sort((a,b)=>b.localeCompare(a)), "All years");
  buildSelect("#pub-type-filter", [...new Set(all.map(p=>p.type||p.category||"Other"))].sort(), "All types");
  const yr = $("#pub-year-filter").value, type = $("#pub-type-filter").value, q = ($("#pub-search").value||"").toLowerCase();
  const items = all.filter(p => {
    const ptype = p.type || p.category || "Other";
    const text = [p.authors,p.title,p.venue,p.indexes,p.labels,p.note].join(" ").toLowerCase();
    return (yr==="all" || String(p.year)===yr) && (type==="all" || ptype===type) && (!q || text.includes(q));
  });
  $("#pub-count").textContent = `${items.length} / ${all.length} records`;
  $("#publication-list").innerHTML = items.map(formatPublication).join("") || `<div class="item">No publications to display. Generate <code>data/publications.json</code> from your publication Excel.</div>`;
}

function renderServices(){
  const groups = {};
  (DATA.services||[]).forEach(s => (groups[s.category||"Service"] ||= []).push(s));
  $("#services-list").innerHTML = Object.entries(groups).map(([cat,items]) => `
    <div class="service-group">
      <h3>${esc(cat)}</h3>
      <ul>${items.map(s=>{
        const text = [s.role, s.item || s.organization, s.period].filter(Boolean).join(", ");
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
  $("#awards-list").innerHTML = (DATA.awards||[]).map(a => `<li class="item"><span class="item-date">${esc(a.year)}</span>${esc(a.title)}${a.organization ? ` — ${esc(a.organization)}` : ""}</li>`).join("");
}

function renderGroup(){
  const groups = {};
  (DATA.group||[]).forEach(g => (groups[g.category||"Member"] ||= []).push(g));
  $("#group-list").innerHTML = Object.entries(groups).map(([cat,items]) => `
    <h3>${esc(cat)}</h3>
    <ul>${items.map(m => `<li>${linkify(m.name,m.link)}${m.note ? ` <span class="meta">(${esc(m.note)})</span>` : ""}</li>`).join("")}</ul>`).join("");
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