let currentTab = "cn";
let allData = { cn: [], en: [] };

const rankOrder = ["T1", "T2", "A", "B", "C", "D", "其他"];

const tableConfig = {
  cn: {
    label: "中文期刊目录",
    file: "data/journals_cn.json",
    columns: [
      { key: "serial", label: "总序号", cls: "col-serial" },
      { key: "rank", label: "级别", cls: "col-rank", rank: true },
      { key: "title", label: "期刊名称", cls: "col-title" },
      { key: "publisher", label: "主办单位", cls: "col-publisher" }
    ],
    searchKeys: ["title", "publisher", "rank"]
  },
  en: {
    label: "外文期刊目录",
    file: "data/journals_en.json",
    columns: [
      { key: "serial", label: "总序号", cls: "col-serial" },
      { key: "rank", label: "级别", cls: "col-rank", rank: true },
      { key: "title", label: "期刊名称", cls: "col-title" },
      { key: "issn", label: "ISSN", cls: "col-issn" },
      { key: "eissn", label: "eISSN", cls: "col-issn" }
    ],
    searchKeys: ["title", "issn", "eissn", "rank"]
  }
};

function norm(v) {
  return String(v ?? "")
    .trim()
    .replace(/\u3000/g, " ")
    .replace(/\s+/g, " ")
    .toLowerCase();
}

function escapeHTML(v) {
  return String(v ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function matchKeyword(item, query, keys) {
  const q = norm(query);
  if (!q) return true;

  const haystack = norm(keys.map(k => item[k] ?? "").join(" "));
  const keywords = q.split(/\s+/).filter(Boolean);
  return keywords.every(kw => haystack.includes(kw));
}

function rankSort(a, b) {
  const ra = rankOrder.indexOf(a.rank);
  const rb = rankOrder.indexOf(b.rank);
  const rankA = ra === -1 ? 99 : ra;
  const rankB = rb === -1 ? 99 : rb;

  const sa = Number.isFinite(Number(a.serial)) ? Number(a.serial) : 999999;
  const sb = Number.isFinite(Number(b.serial)) ? Number(b.serial) : 999999;

  return rankA - rankB || sa - sb || String(a.title).localeCompare(String(b.title));
}

async function loadData() {
  const [cnRes, enRes] = await Promise.all([
    fetch(tableConfig.cn.file),
    fetch(tableConfig.en.file)
  ]);

  allData.cn = (await cnRes.json()).sort(rankSort);
  allData.en = (await enRes.json()).sort(rankSort);

  document.getElementById("totalCount").textContent =
    `中文 ${allData.cn.length} 条；外文 ${allData.en.length} 条`;

  bindEvents();
  setTab("cn");
}

function bindEvents() {
  document.querySelectorAll(".tab").forEach(btn => {
    btn.addEventListener("click", () => setTab(btn.dataset.tab));
  });

  document.getElementById("keywordInput").addEventListener("input", applyFilters);
  document.getElementById("rankFilter").addEventListener("change", applyFilters);

  document.getElementById("resetBtn").addEventListener("click", () => {
    document.getElementById("keywordInput").value = "";
    document.getElementById("rankFilter").value = "";
    renderCurrentTable(allData[currentTab]);
  });
}

function setTab(tab) {
  currentTab = tab;

  document.querySelectorAll(".tab").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });

  document.getElementById("keywordInput").value = "";
  populateRankFilter();
  renderCurrentTable(allData[currentTab]);
}

function populateRankFilter() {
  const select = document.getElementById("rankFilter");
  select.innerHTML = `<option value="">全部级别</option>`;

  const ranks = [...new Set(allData[currentTab].map(i => i.rank).filter(Boolean))]
    .sort((a, b) => {
      const ia = rankOrder.indexOf(a);
      const ib = rankOrder.indexOf(b);
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
    });

  ranks.forEach(r => {
    const opt = document.createElement("option");
    opt.value = r;
    opt.textContent = r;
    select.appendChild(opt);
  });
}

function applyFilters() {
  const query = document.getElementById("keywordInput").value;
  const rank = document.getElementById("rankFilter").value;
  const cfg = tableConfig[currentTab];

  const result = allData[currentTab].filter(item => {
    const mKeyword = matchKeyword(item, query, cfg.searchKeys);
    const mRank = !rank || item.rank === rank;
    return mKeyword && mRank;
  });

  renderCurrentTable(result);
}

function renderCurrentTable(data) {
  const cfg = tableConfig[currentTab];
  const thead = document.getElementById("tableHead");
  const tbody = document.getElementById("tableBody");

  thead.innerHTML = `<tr>${cfg.columns.map(col =>
    `<th class="${col.cls || ""}">${escapeHTML(col.label)}</th>`
  ).join("")}</tr>`;

  document.getElementById("activeInfo").textContent = cfg.label;
  document.getElementById("resultInfo").textContent =
    `显示 ${data.length} / ${allData[currentTab].length} 条`;

  if (!data.length) {
    tbody.innerHTML = `<tr><td class="empty" colspan="${cfg.columns.length}">无匹配记录</td></tr>`;
    return;
  }

  tbody.innerHTML = data.map(row => {
    return `<tr>${cfg.columns.map(col => {
      const value = row[col.key] || "";
      const content = col.rank
        ? `<span class="rank">${escapeHTML(value || "-")}</span>`
        : escapeHTML(value || "-");
      return `<td class="${col.cls || ""}" title="${escapeHTML(value)}">${content}</td>`;
    }).join("")}</tr>`;
  }).join("");
}

window.addEventListener("load", loadData);
