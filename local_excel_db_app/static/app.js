let tables = [];
let currentTable = null;
let allRows = [];
let currentRows = [];
let editingRow = null;
let activeFilters = [];
let pubSelectedTypes = new Set(['期刊', '工作']);
let pubShowAllTypes = false;
let formRenderToken = 0;
let dirtyPublicationCount = 0;

const tableTabs = document.querySelector('#tableTabs');
const currentTitle = document.querySelector('#currentTitle');
const currentHint = document.querySelector('#currentHint');
const searchInput = document.querySelector('#searchInput');
const addBtn = document.querySelector('#addBtn');
const updateChangedBtn = document.querySelector('#updateChangedBtn');
const dataTable = document.querySelector('#dataTable');
const modal = document.querySelector('#modal');
const modalTitle = document.querySelector('#modalTitle');
const recordForm = document.querySelector('#recordForm');
const saveBtn = document.querySelector('#saveBtn');
const cancelBtn = document.querySelector('#cancelBtn');
const closeModal = document.querySelector('#closeModal');
const importFile = document.querySelector('#importFile');
const importPubFile = document.querySelector('#importPubFile');
const importIfFile = document.querySelector('#importIfFile');
const autoExportStatus = document.querySelector('#autoExportStatus');
const filterPanel = document.querySelector('#filterPanel');
const toolStatus = document.querySelector('#toolStatus');
const generatedFiles = document.querySelector('#generatedFiles');

async function api(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const payload = await res.json();
      msg = payload.error || JSON.stringify(payload);
    } catch (_) {
      msg = await res.text();
    }
    throw new Error(msg);
  }
  return res.json();
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

const acronymMap = {
  issn: 'ISSN', eissn: 'EISSN', doi: 'DOI', if: 'IF', sci: 'SCI', ssci: 'SSCI', ei: 'EI',
  cssci: 'CSSCI', istp: 'ISTP', fms: 'FMS', abs: 'ABS', isbn: 'ISBN', esi: 'ESI', cn: 'CN', en: 'EN', jcr: 'JCR'
};

const fieldLabelZh = {
  type: '类型',
  language: '语言',
  year: '年份',
  date: '日期',
  category: '分类',
  status: '状态',
  level: '级别',
  role: '角色',
  title: '标题',
  titlechinese: '中文题名',
  titleenglish: '英文题名',
  author: '作者',
  authorchinese: '中文作者',
  authorenglish: '英文作者',
  authorschinese: '中文作者',
  authorsenglish: '英文作者',
  correspondingauthorcn: '中文通讯作者',
  correspondingauthoren: '英文通讯作者',
  source: '来源',
  sourcechinese: '中文来源',
  sourceenglish: '英文来源',
  journal: '期刊',
  journalname: '期刊名称',
  journalchinese: '中文期刊',
  journalenglish: '英文期刊',
  volume: '卷',
  number: '期',
  issue: '期',
  page: '页码',
  pages: '页码',
  address: '出版地',
  publisher: '出版社',
  organization: '机构',
  content: '内容',
  description: '描述',
  note: '备注',
  notechinese: '中文备注',
  noteenglish: '英文备注',
  link: '链接',
  link1: '链接1',
  link2: '链接2',
  abstract: '摘要',
  conference: '会议',
  conferencedate: '会议日期',
  conferenceaddress: '会议地点',
  quartile: '分区',
  jcrquartile: 'JCR分区',
  esihighlycited: 'ESI高被引',
  esihot: 'ESI热点',
  impactfactor: '影响因子',
  impact: '影响',
  grant: '项目',
  award: '奖励',
  service: '服务',
  student: '学生',
  email: '邮箱',
  url: '网址',
  issn: 'ISSN',
  eissn: 'EISSN',
  doi: 'DOI',
  if: '影响因子',
  jif: 'JIF',
  sci: 'SCI',
  ssci: 'SSCI',
  ei: 'EI',
  cssci: 'CSSCI',
  istp: 'ISTP',
  fms: 'FMS',
  abs: 'ABS',
  isbn: 'ISBN'
};

const tokenLabelZh = {
  chinese: '中文', english: '英文', author: '作者', authors: '作者', corresponding: '通讯',
  title: '题名', source: '来源', journal: '期刊', name: '名称', note: '备注',
  conference: '会议', date: '日期', address: '地点', highly: '高被引', cited: '', hot: '热点',
  impact: '影响', factor: '因子', volume: '卷', number: '期', page: '页码', pages: '页码',
  language: '语言', type: '类型', year: '年份', status: '状态', category: '分类', role: '角色', level: '级别'
};

function formatLabel(name) {
  if (!name) return '';
  const normalized = normField(name);
  if (fieldLabelZh[normalized]) return fieldLabelZh[normalized];
  const raw = String(name).trim().replace(/_+/g, ' ');
  const parts = raw.split(/\s+/).map(part => {
    const key = part.toLowerCase();
    if (acronymMap[key]) return acronymMap[key];
    if (tokenLabelZh[key] !== undefined) return tokenLabelZh[key];
    if (/^[\u4e00-\u9fff]+$/.test(part)) return part;
    return part.charAt(0).toUpperCase() + part.slice(1);
  }).filter(Boolean);
  return parts.join('') || raw;
}

function normField(name) {
  return String(name || '').toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]/g, '');
}

function findColumn(candidates, cols = currentTable?.columns || []) {
  const map = new Map(cols.map(c => [normField(c), c]));
  for (const cand of candidates) {
    const key = normField(cand);
    if (map.has(key)) return map.get(key);
  }
  return null;
}

function isLongField(name) {
  return /content|title|note|item|organization|link|description|abstract|author|address/i.test(name);
}

function looksCategorical(name) {
  const key = name.toLowerCase();
  return /type|language|category|status|role|level|quartile|sci|ssci|cssci|istp|esi|hot|fms|abs|source|publisher|year/i.test(key);
}

function isPublicationsTable() {
  return currentTable && currentTable.table_name === 'Publications';
}

function getTypeColumn() {
  return findColumn(['Type', '类型']);
}

function getRowType(row) {
  const col = getTypeColumn();
  return col ? String(row[col] || '').trim() : '';
}

const pubProfileCandidates = {
  '期刊': [
    'Type', 'Language', 'Corresponding_Author_cn', 'Corresponding_Author_en',
    'Author_Chinese', 'Author_English', 'Year', 'Title_Chinese', 'Title_English',
    'Source_English', 'ISSN', 'Source_Chinese', 'Volume', 'Number', 'Page', 'DOI', 'IF',
    'SCI', 'SSCI', 'EI', 'CSSCI', 'FMS', 'ABS', 'ESI_Highly_Cited', 'ESI_Hot',
    'Note_Chinese', 'Note_English'
  ],
  '工作': [
    'Type', 'Language', 'Corresponding_Author_cn', 'Corresponding_Author_en',
    'Author_Chinese', 'Author_English', 'Title_Chinese', 'Title_English',
    'Source_English', 'ISSN', 'Source_Chinese', 'IF', 'SCI', 'SSCI', 'EI', 'CSSCI', 'FMS', 'ABS',
    'Note_Chinese', 'Note_English'
  ],
  '会议': [
    'Type', 'Language', 'Corresponding_Author_cn', 'Corresponding_Author_en',
    'Author_Chinese', 'Author_English', 'Year', 'Title_Chinese', 'Title_English',
    'Source_English', 'Source_Chinese', 'Volume', 'Page', 'DOI', 'EI', 'ISTP',
    'Conference_Date', 'Conference_Address', 'Note_Chinese', 'Note_English'
  ],
  '专著': [
    'Type', 'Language', 'Author_Chinese', 'Author_English', 'Year', 'Title_Chinese', 'Title_English',
    'Address', 'Source_English', 'Source_Chinese', 'DOI', 'ISBN', 'Note_Chinese', 'Note_English'
  ]
};

const pubCoreCandidates = [
  'Type', 'Language', 'Author_Chinese', 'Author_English', 'Year',
  'Title_Chinese', 'Title_English', 'Source_English', 'ISSN', 'IF'
];

function resolveColumns(candidateNames) {
  const result = [];
  for (const name of candidateNames) {
    const col = findColumn([name]);
    if (col && !result.includes(col)) result.push(col);
  }
  return result;
}

function valuesForColumn(col, rows = allRows) {
  const set = new Set();
  rows.forEach(row => {
    const v = String(row[col] || '').trim();
    if (v) set.add(v);
  });
  return [...set].sort((a, b) => String(a).localeCompare(String(b), 'zh-Hans-CN'));
}

function hasNonEmpty(col, rows) {
  return rows.some(row => String(row[col] || '').trim() !== '');
}

function getSelectedPublicationTypes() {
  if (!isPublicationsTable()) return [];
  const types = [...new Set(allRows.map(getRowType).filter(Boolean))];
  if (pubShowAllTypes) return types;
  return [...pubSelectedTypes];
}

function getPublicationDisplayColumns() {
  const selectedTypes = getSelectedPublicationTypes();
  const typeCol = getTypeColumn();
  const relevantRows = currentRows.length ? currentRows : allRows.filter(row => {
    const t = getRowType(row);
    return pubShowAllTypes || selectedTypes.includes(t);
  });
  const typeCandidates = selectedTypes.length ? selectedTypes : ['期刊', '工作'];
  const candidates = [];
  typeCandidates.forEach(t => candidates.push(...(pubProfileCandidates[t] || pubProfileCandidates['期刊'])));
  const profileCols = resolveColumns(candidates);
  const coreCols = resolveColumns(pubCoreCandidates);
  const cols = [];

  for (const col of [...profileCols, ...currentTable.columns]) {
    if (col === 'id' || col === '_order_index') continue;
    const isCore = coreCols.includes(col);
    const isTypeCol = col === typeCol;
    if (isCore || isTypeCol || hasNonEmpty(col, relevantRows)) {
      if (!cols.includes(col)) cols.push(col);
    }
  }
  // For a single selected type, Type is still useful but less critical; keep it first for clarity.
  return cols;
}

function getPublicationFormColumns(row = {}) {
  const typeCol = getTypeColumn();
  let type = typeCol ? String(row[typeCol] || '').trim() : '';
  if (!type) {
    type = pubSelectedTypes.size === 1 ? [...pubSelectedTypes][0] : '期刊';
    if (typeCol) row[typeCol] = type;
  }
  const profile = resolveColumns(pubProfileCandidates[type] || pubProfileCandidates['期刊']);
  const filledOtherCols = currentTable.columns.filter(col => {
    if (col === 'id' || col === '_order_index' || profile.includes(col)) return false;
    return String(row[col] || '').trim() !== '';
  });
  return [...profile, ...filledOtherCols];
}

function getVisibleColumns() {
  if (!currentTable) return [];
  if (isPublicationsTable()) return getPublicationDisplayColumns();
  return currentTable.columns.filter(c => c !== 'id' && c !== '_order_index');
}

async function refreshAutoExportStatus() {
  try {
    const status = await api('/api/auto_export_status');
    if (!autoExportStatus) return;
    if (status.exists) {
      autoExportStatus.textContent = `Excel 已更新：${status.modified_at}`;
    } else {
      autoExportStatus.textContent = '';
    }
  } catch (e) {
    if (autoExportStatus) autoExportStatus.textContent = '';
  }
}

async function loadTables() {
  tables = await api('/api/tables');
  tableTabs.innerHTML = '';
  tables.forEach((t, index) => {
    const btn = document.createElement('button');
    btn.className = `tab tab-${index % 8}`;
    btn.innerHTML = `<span>${escapeHtml(t.sheet_name)}</span><em>${escapeHtml(t.source_type || '')}</em>`;
    btn.onclick = () => selectTable(t.table_name);
    tableTabs.appendChild(btn);
    if (index === 0 && !currentTable) currentTable = t;
  });
  if (currentTable && tables.some(t => t.table_name === currentTable.table_name)) {
    await selectTable(currentTable.table_name);
  } else if (tables.length) {
    await selectTable(tables[0].table_name);
  }
}

function setActiveTab() {
  [...tableTabs.children].forEach((btn, index) => {
    btn.classList.toggle('active', tables[index]?.table_name === currentTable?.table_name);
  });
}

async function selectTable(tableName) {
  currentTable = tables.find(t => t.table_name === tableName);
  if (!currentTable) return;
  setActiveTab();
  currentTitle.textContent = currentTable.sheet_name;
  searchInput.value = '';
  activeFilters = [];
  if (isPublicationsTable()) {
    pubSelectedTypes = new Set(['期刊', '工作']);
    pubShowAllTypes = false;
  }
  await loadRows();
  await refreshPublicationDirtyCount();
}

async function loadRows() {
  if (!currentTable) return;
  allRows = await api(`/api/rows/${currentTable.table_name}`);
  renderFilterPanel();
  applyFilters();
}

function getFilterableColumns() {
  if (!currentTable) return [];
  const cols = currentTable.columns.filter(c => c !== 'id' && c !== '_order_index');
  if (isPublicationsTable()) {
    const preferred = ['Type', 'Language', 'Year', 'Source_English', 'Source_Chinese', 'SCI', 'SSCI', 'EI', 'CSSCI', 'FMS', 'ABS', 'ESI_Highly_Cited', 'ESI_Hot', 'IF'];
    const resolved = resolveColumns(preferred);
    return [...resolved, ...cols.filter(c => !resolved.includes(c) && looksCategorical(c))];
  }
  return cols.filter(looksCategorical).length ? cols.filter(looksCategorical) : cols.slice(0, 8);
}

function renderFilterPanel() {
  if (!filterPanel || !currentTable) return;
  const filterable = getFilterableColumns();
  const fieldOptions = filterable.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(formatLabel(c))}</option>`).join('');
  const typeCol = getTypeColumn();
  const types = isPublicationsTable()
    ? [...new Set([...allRows.map(getRowType).filter(Boolean), '期刊', '工作', '会议', '专著'])]
    : [];

  const typeHtml = isPublicationsTable() ? `
    <div class="pub-type-filter">
      <span class="filter-label">类型显示</span>
      ${types.map(t => `
        <button type="button" class="type-pill ${!pubShowAllTypes && pubSelectedTypes.has(t) ? 'active' : ''}" data-type="${escapeHtml(t)}">
          ${escapeHtml(t)}
        </button>`).join('')}
      <button type="button" class="type-pill all ${pubShowAllTypes ? 'active' : ''}" data-show-all="1">全部类型</button>
    </div>` : '';

  const chips = activeFilters.map((f, idx) => `
    <button type="button" class="filter-chip" data-remove-filter="${idx}">
      ${escapeHtml(formatLabel(f.field))}: ${escapeHtml(f.value)} ×
    </button>`).join('');

  const updateBtnHtml = isPublicationsTable()
    ? `<button type="button" id="filterUpdateChangedBtn" class="btn ghost compact-action" ${dirtyPublicationCount === 0 ? 'disabled' : ''}>${dirtyPublicationCount > 0 ? `更新（${dirtyPublicationCount}）` : '更新'}</button>`
    : '';
  filterPanel.innerHTML = `
    ${typeHtml}
    <div class="filter-row">
      <span class="filter-label">筛选</span>
      <select id="filterField">${fieldOptions}</select>
      <input id="filterValue" list="filterValueList" placeholder="选择或输入筛选值" />
      <datalist id="filterValueList"></datalist>
      <button type="button" id="addFilterBtn" class="mini-btn">添加筛选</button>
      <button type="button" id="clearFiltersBtn" class="mini-btn ghost">清空</button>
      <span class="filter-actions">
        ${updateBtnHtml}
        <button type="button" id="filterAddRecordBtn" class="btn compact-action">新增记录</button>
      </span>
    </div>
    <div class="filter-chips">${chips || '<span class="empty-filter">暂无附加筛选</span>'}</div>
  `;

  filterPanel.querySelectorAll('[data-type]').forEach(btn => {
    btn.addEventListener('click', () => {
      const t = btn.getAttribute('data-type');
      pubShowAllTypes = false;
      if (pubSelectedTypes.has(t)) pubSelectedTypes.delete(t);
      else pubSelectedTypes.add(t);
      if (!pubSelectedTypes.size) pubSelectedTypes.add(t);
      renderFilterPanel();
      applyFilters();
    });
  });
  const allBtn = filterPanel.querySelector('[data-show-all]');
  if (allBtn) {
    allBtn.addEventListener('click', () => {
      pubShowAllTypes = true;
      renderFilterPanel();
      applyFilters();
    });
  }

  const fieldSel = filterPanel.querySelector('#filterField');
  const valueInput = filterPanel.querySelector('#filterValue');
  const valueList = filterPanel.querySelector('#filterValueList');
  const updateValues = () => {
    const col = fieldSel.value;
    const values = valuesForColumn(col, allRows).slice(0, 200);
    valueList.innerHTML = values.map(v => `<option value="${escapeHtml(v)}"></option>`).join('');
    valueInput.value = '';
  };
  if (fieldSel) {
    fieldSel.addEventListener('change', updateValues);
    updateValues();
  }
  const addFilterBtn = filterPanel.querySelector('#addFilterBtn');
  if (addFilterBtn) {
    addFilterBtn.addEventListener('click', () => {
      const field = fieldSel.value;
      const value = valueInput.value.trim();
      if (!field || !value) return;
      activeFilters.push({ field, value });
      renderFilterPanel();
      applyFilters();
    });
  }
  const clearBtn = filterPanel.querySelector('#clearFiltersBtn');
  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      activeFilters = [];
      if (isPublicationsTable()) {
        pubSelectedTypes = new Set(['期刊', '工作']);
        pubShowAllTypes = false;
      }
      renderFilterPanel();
      applyFilters();
    });
  }

  const addRecordBtn = filterPanel.querySelector('#filterAddRecordBtn');
  if (addRecordBtn) addRecordBtn.addEventListener('click', openAdd);

  const updateBtn = filterPanel.querySelector('#filterUpdateChangedBtn');
  if (updateBtn) updateBtn.addEventListener('click', updateChangedPublications);

  filterPanel.querySelectorAll('[data-remove-filter]').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = Number(btn.getAttribute('data-remove-filter'));
      activeFilters.splice(idx, 1);
      renderFilterPanel();
      applyFilters();
    });
  });
}

function rowMatchesSearch(row, q) {
  if (!q) return true;
  const lower = q.toLowerCase();
  return currentTable.columns.some(col => String(row[col] || '').toLowerCase().includes(lower));
}

function rowMatchesFilters(row) {
  if (isPublicationsTable() && !pubShowAllTypes) {
    const t = getRowType(row);
    if (!pubSelectedTypes.has(t)) return false;
  }
  for (const f of activeFilters) {
    const cell = String(row[f.field] || '').toLowerCase();
    if (!cell.includes(String(f.value || '').toLowerCase())) return false;
  }
  return true;
}

function applyFilters() {
  const q = searchInput.value.trim();
  currentRows = allRows.filter(row => rowMatchesSearch(row, q) && rowMatchesFilters(row));
  renderTable();
  updateHint();
}

async function refreshPublicationDirtyCount() {
  if (!isPublicationsTable()) {
    dirtyPublicationCount = 0;
    return;
  }
  try {
    const payload = await api('/api/publications/dirty_count');
    dirtyPublicationCount = Number(payload.count || 0);
  } catch (_) {
    dirtyPublicationCount = 0;
  }
  renderFilterPanel();
}

async function updateChangedPublications() {
  if (!isPublicationsTable()) return;
  const updateBtn = document.querySelector('#filterUpdateChangedBtn');
  const oldText = updateBtn ? updateBtn.textContent : '更新';
  if (updateBtn) {
    updateBtn.disabled = true;
    updateBtn.textContent = '更新中...';
  }
  try {
    const res = await api('/api/publications/update_changed', { method: 'POST' });
    await loadRows();
    await refreshAutoExportStatus();
    await refreshPublicationDirtyCount();
    if (res.processed === 0) {
      alert('没有需要更新的新增或编辑记录。');
    } else if (!res.changed) {
      alert(`已检查 ${res.processed} 条记录，未发现需要回填的作者、中文题名、中文来源、ISSN 或影响因子。`);
    }
  } catch (e) {
    if (updateBtn) {
      updateBtn.textContent = oldText;
      updateBtn.disabled = false;
    }
    alert(`更新失败：${e.message}`);
  }
}

function updateHint() {
  if (!currentTable) return;
  if (isPublicationsTable()) {
    const typeInfo = pubShowAllTypes ? '全部类型' : [...pubSelectedTypes].join('、');
    currentHint.textContent = `${currentRows.length}/${allRows.length} 条记录 · ${typeInfo}`;
  } else {
    currentHint.textContent = `${currentRows.length}/${allRows.length} 条记录`;
  }
}

function renderTable() {
  const cols = getVisibleColumns();
  dataTable.querySelector('thead').innerHTML = `
    <tr>
      <th class="row-actions sticky-actions">操作</th>
      ${cols.map(c => `<th title="${escapeHtml(c)}">${escapeHtml(formatLabel(c))}</th>`).join('')}
    </tr>`;

  const body = dataTable.querySelector('tbody');
  if (!currentRows.length) {
    body.innerHTML = `<tr><td class="empty-cell" colspan="${cols.length + 1}">暂无数据</td></tr>`;
    return;
  }

  body.innerHTML = currentRows.map(row => `
    <tr>
      <td class="row-actions sticky-actions">
        <button class="small-btn" onclick="openEdit(${row.id})">编辑</button>
        <button class="small-btn danger" onclick="deleteRow(${row.id})">删除</button>
      </td>
      ${cols.map(c => `<td>${escapeHtml(row[c] || '')}</td>`).join('')}
    </tr>`).join('');
}

function collectCurrentFormValues() {
  const formData = new FormData(recordForm);
  const values = {};
  for (const col of currentTable.columns) {
    if (col === 'id' || col === '_order_index') continue;
    values[col] = formData.get(col) ?? '';
  }
  return values;
}

async function openAdd() {
  editingRow = null;
  modalTitle.textContent = `新增记录：${currentTable.sheet_name}`;
  const row = {};
  if (isPublicationsTable()) {
    const typeCol = getTypeColumn();
    if (typeCol) row[typeCol] = pubSelectedTypes.size === 1 ? [...pubSelectedTypes][0] : '期刊';
  }
  await renderForm(row);
  modal.classList.remove('hidden');
}

async function openEdit(id) {
  editingRow = currentRows.find(r => r.id === id) || allRows.find(r => r.id === id);
  if (!editingRow) return;
  modalTitle.textContent = `编辑记录：${currentTable.sheet_name}`;
  await renderForm({ ...editingRow });
  modal.classList.remove('hidden');
}

async function getOptionsForColumn(column) {
  if (!looksCategorical(column) && !isPublicationsTable()) return [];
  try {
    return await api(`/api/options/${currentTable.table_name}/${encodeURIComponent(column)}`);
  } catch (_) {
    const values = valuesForColumn(column, allRows);
    return values.slice(0, 80);
  }
}

async function renderForm(row) {
  const token = ++formRenderToken;
  recordForm.innerHTML = '';
  const workingRow = { ...row };
  const cols = isPublicationsTable()
    ? getPublicationFormColumns(workingRow)
    : currentTable.columns.filter(c => c !== 'id' && c !== '_order_index');

  const optionMap = {};
  await Promise.all(cols.map(async col => {
    optionMap[col] = await getOptionsForColumn(col);
  }));
  if (token !== formRenderToken) return;

  cols.forEach((col, index) => {
    const value = workingRow[col] || '';
    const group = document.createElement('label');
    group.className = isLongField(col) ? 'field wide' : 'field';
    const title = document.createElement('span');
    title.textContent = formatLabel(col);
    title.title = col;
    group.appendChild(title);

    const options = optionMap[col] || [];
    const dataListId = `dl_${currentTable.table_name}_${col}_${index}`.replace(/[^a-zA-Z0-9_]/g, '_');
    if (isLongField(col)) {
      const textarea = document.createElement('textarea');
      textarea.name = col;
      textarea.value = value;
      textarea.rows = /abstract|description|note/i.test(col) ? 4 : 3;
      group.appendChild(textarea);
    } else {
      const input = document.createElement('input');
      input.name = col;
      input.value = value;
      if (options.length) {
        input.setAttribute('list', dataListId);
        input.placeholder = '从下拉选项选择，或直接输入新值';
        const dl = document.createElement('datalist');
        dl.id = dataListId;
        options.forEach(opt => {
          const o = document.createElement('option');
          o.value = opt;
          dl.appendChild(o);
        });
        group.appendChild(input);
        group.appendChild(dl);
      } else {
        group.appendChild(input);
      }
      if (isPublicationsTable() && col === getTypeColumn()) {
        input.addEventListener('change', async () => {
          const currentValues = { ...workingRow, ...collectCurrentFormValues() };
          currentValues[col] = input.value.trim() || '期刊';
          await renderForm(currentValues);
        });
      }
    }
    recordForm.appendChild(group);
  });
}

function showMatchResult(payload) {
  if (!toolStatus || !payload || !payload.match_result) return;
  const wrapper = payload.match_result || {};
  const impact = wrapper.impact || wrapper;
  const authors = wrapper.authors;
  const source = wrapper.source;
  const messages = [];
  if (authors) {
    if (authors.updated) {
      messages.push(`作者英文自动生成：已回填 ${Object.keys(authors.updates || {}).map(formatLabel).join('、')}`);
    } else if (authors.reason && !/already filled/i.test(authors.reason)) {
      messages.push('作者英文自动生成：未更新');
    }
  }
  if (source && source.updated) {
    messages.push(`中文来源自动回填：已回填 ${Object.keys(source.updates || {}).map(formatLabel).join('、')}`);
  }
  if (impact) {
    if (impact.matched) {
      const fields = impact.updates ? Object.keys(impact.updates) : [];
      if (fields.length) messages.push(`ISSN/IF 自动匹配：已按${impact.method || '记录'}回填 ${fields.map(formatLabel).join('、')}`);
      else messages.push('ISSN/IF 自动匹配：已匹配到影响因子库记录，但当前 ISSN/IF 已有值，未覆盖');
    } else if (impact.reason) {
      messages.push('ISSN/IF 自动匹配：未匹配，可手动填写 ISSN/EISSN 或 IF');
    }
  }
  toolStatus.textContent = messages.join('；') || '保存完成';
}

async function saveRow() {
  const formData = new FormData(recordForm);
  const payload = {};
  currentTable.columns.filter(c => c !== 'id' && c !== '_order_index').forEach(col => {
    payload[col] = editingRow ? (editingRow[col] || '') : '';
  });
  for (const [key, value] of formData.entries()) {
    payload[key] = value || '';
  }
  let result;
  if (editingRow) {
    result = await api(`/api/rows/${currentTable.table_name}/${editingRow.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  } else {
    result = await api(`/api/rows/${currentTable.table_name}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  }
  closeEditor();
  await loadRows();
  await refreshPublicationDirtyCount();
  showMatchResult(result);
  await refreshAutoExportStatus();
}

function closeEditor() {
  modal.classList.add('hidden');
}

async function deleteRow(id) {
  if (!confirm('确定删除这条记录吗？')) return;
  await api(`/api/rows/${currentTable.table_name}/${id}`, { method: 'DELETE' });
  await loadRows();
  await refreshPublicationDirtyCount();
  await refreshAutoExportStatus();
}

async function updatePublicationFields(id) {
  try {
    const res = await api(`/api/publications/update_fields/${id}`, { method: 'POST' });
    const impact = res.result?.impact || {};
    const authors = res.result?.authors || {};
    await loadRows();
    await refreshAutoExportStatus();
    if (!res.result?.changed && impact && impact.matched === false) {
      alert(`未匹配到 ISSN/IF。${impact.reason || '可手动填写 ISSN 或 EISSN 后再次点击更新。'}`);
    } else if (!res.result?.changed && authors && authors.updated === false && impact && impact.matched) {
      // 已匹配但没有需要改动的字段，保持静默，避免频繁弹窗。
    }
  } catch (e) {
    alert(`更新失败：${e.message}`);
  }
}

async function uploadExcel(input, url, message) {
  const file = input.files[0];
  if (!file) return;
  if (!confirm(message)) {
    input.value = '';
    return;
  }
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch(url, { method: 'POST', body: fd });
  if (!res.ok) {
    alert('导入失败');
    input.value = '';
    return;
  }
  input.value = '';
  currentTable = null;
  await loadTables();
  await refreshPublicationDirtyCount();
  await refreshAutoExportStatus();
  alert('导入完成');
}

let timer = null;
searchInput.addEventListener('input', () => {
  clearTimeout(timer);
  timer = setTimeout(applyFilters, 180);
});
if (addBtn) addBtn.addEventListener('click', openAdd);
saveBtn.addEventListener('click', saveRow);
cancelBtn.addEventListener('click', closeEditor);
closeModal.addEventListener('click', closeEditor);
modal.addEventListener('click', e => { if (e.target === modal) closeEditor(); });

importFile.addEventListener('change', () => uploadExcel(
  importFile,
  '/api/import',
  '导入基础 Excel 会替换 News、Awards、Grants、Services、Group 等基础数据表，不会影响 Publications 和影响因子库。是否继续？'
));
importPubFile.addEventListener('change', () => uploadExcel(
  importPubFile,
  '/api/import_publications',
  '导入发表记录会替换 Publications 表，其他数据表不受影响。是否继续？'
));
importIfFile.addEventListener('change', () => uploadExcel(
  importIfFile,
  '/api/import_impact_factors',
  '导入影响因子库会替换隐藏的 Impact Factors 表。是否继续？'
));


loadTables().then(refreshAutoExportStatus).then(refreshPublicationDirtyCount);
