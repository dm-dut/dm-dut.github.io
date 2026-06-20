let tables = [];
let currentTable = null;
let currentRows = [];
let editingRow = null;

const tableTabs = document.querySelector('#tableTabs');
const currentTitle = document.querySelector('#currentTitle');
const currentHint = document.querySelector('#currentHint');
const searchInput = document.querySelector('#searchInput');
const addBtn = document.querySelector('#addBtn');
const dataTable = document.querySelector('#dataTable');
const modal = document.querySelector('#modal');
const modalTitle = document.querySelector('#modalTitle');
const recordForm = document.querySelector('#recordForm');
const saveBtn = document.querySelector('#saveBtn');
const cancelBtn = document.querySelector('#cancelBtn');
const closeModal = document.querySelector('#closeModal');
const importFile = document.querySelector('#importFile');
const autoExportStatus = document.querySelector('#autoExportStatus');

async function api(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}


async function refreshAutoExportStatus() {
  try {
    const status = await api('/api/auto_export_status');
    if (!autoExportStatus) return;
    if (status.exists) {
      autoExportStatus.textContent = `自动导出已开启：${status.modified_at} 已更新 auto_exported_content.xlsx`;
    } else {
      autoExportStatus.textContent = '自动导出已开启：尚未生成 Excel 文件';
    }
  } catch (e) {
    if (autoExportStatus) autoExportStatus.textContent = '自动导出状态读取失败';
  }
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function isLongField(name) {
  return /content|title|note|item|organization|link|description|abstract/i.test(name);
}

async function loadTables() {
  tables = await api('/api/tables');
  tableTabs.innerHTML = '';
  tables.forEach((t, index) => {
    const btn = document.createElement('button');
    btn.className = `tab tab-${index % 7}`;
    btn.textContent = t.sheet_name;
    btn.onclick = () => selectTable(t.table_name);
    tableTabs.appendChild(btn);
    if (index === 0) currentTable = t;
  });
  if (currentTable) selectTable(currentTable.table_name);
}

function setActiveTab() {
  [...tableTabs.children].forEach((btn, index) => {
    btn.classList.toggle('active', tables[index]?.table_name === currentTable?.table_name);
  });
}

async function selectTable(tableName) {
  currentTable = tables.find(t => t.table_name === tableName);
  setActiveTab();
  searchInput.value = '';
  currentTitle.textContent = currentTable.sheet_name;
  currentHint.textContent = `${currentTable.columns.length} 个字段 · 保持 Excel 原始顺序`;
  await loadRows();
}

async function loadRows() {
  const q = encodeURIComponent(searchInput.value.trim());
  currentRows = await api(`/api/rows/${currentTable.table_name}?q=${q}`);
  renderTable();
  currentHint.textContent = `${currentTable.columns.length} 个字段 · ${currentRows.length} 条记录 · 保持 Excel 原始顺序`;
}

function renderTable() {
  const cols = currentTable.columns;
  dataTable.querySelector('thead').innerHTML = `
    <tr><th class="row-index">序号</th>${cols.map(c => `<th>${escapeHtml(c)}</th>`).join('')}<th class="row-actions">操作</th></tr>
  `;
  const tbody = dataTable.querySelector('tbody');
  if (!currentRows.length) {
    tbody.innerHTML = `<tr><td colspan="${cols.length + 2}" class="empty-cell">暂无数据</td></tr>`;
    return;
  }
  tbody.innerHTML = currentRows.map((row, index) => `
    <tr>
      <td class="row-index">${index + 1}</td>
      ${cols.map(c => `<td>${escapeHtml(row[c])}</td>`).join('')}
      <td class="row-actions">
        <button class="small-btn" onclick="openEdit(${row.id})">编辑</button>
        <button class="small-btn danger" onclick="deleteRow(${row.id})">删除</button>
      </td>
    </tr>
  `).join('');
}

function openAdd() {
  editingRow = null;
  modalTitle.textContent = `新增记录 - ${currentTable.sheet_name}`;
  renderForm({});
  modal.classList.remove('hidden');
}

function openEdit(id) {
  editingRow = currentRows.find(r => r.id === id);
  modalTitle.textContent = `编辑记录 - ${currentTable.sheet_name}`;
  renderForm(editingRow);
  modal.classList.remove('hidden');
}

function renderForm(row) {
  recordForm.innerHTML = currentTable.columns.map(col => {
    const value = escapeHtml(row[col] ?? '');
    const full = isLongField(col) ? ' full' : '';
    const input = isLongField(col)
      ? `<textarea name="${escapeHtml(col)}">${value}</textarea>`
      : `<input name="${escapeHtml(col)}" value="${value}" />`;
    return `<div class="field${full}"><label>${escapeHtml(col)}</label>${input}</div>`;
  }).join('');
}

async function saveRow() {
  const formData = new FormData(recordForm);
  const payload = {};
  currentTable.columns.forEach(col => payload[col] = formData.get(col) || '');

  if (editingRow) {
    await api(`/api/rows/${currentTable.table_name}/${editingRow.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  } else {
    await api(`/api/rows/${currentTable.table_name}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  }
  closeEditor();
  await loadRows();
  await refreshAutoExportStatus();
}

function closeEditor() {
  modal.classList.add('hidden');
}

async function deleteRow(id) {
  if (!confirm('确定删除这条记录吗？')) return;
  await api(`/api/rows/${currentTable.table_name}/${id}`, { method: 'DELETE' });
  await loadRows();
  await refreshAutoExportStatus();
}

let timer = null;
searchInput.addEventListener('input', () => {
  clearTimeout(timer);
  timer = setTimeout(loadRows, 250);
});
addBtn.addEventListener('click', openAdd);
saveBtn.addEventListener('click', saveRow);
cancelBtn.addEventListener('click', closeEditor);
closeModal.addEventListener('click', closeEditor);
modal.addEventListener('click', e => { if (e.target === modal) closeEditor(); });

importFile.addEventListener('change', async () => {
  const file = importFile.files[0];
  if (!file) return;
  if (!confirm('导入 Excel 会覆盖当前本地数据库内容，建议先导出备份。是否继续？')) {
    importFile.value = '';
    return;
  }
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch('/api/import', { method: 'POST', body: fd });
  if (!res.ok) {
    alert('导入失败');
    return;
  }
  importFile.value = '';
  await loadTables();
  await refreshAutoExportStatus();
  alert('导入完成，Excel 自动导出文件已同步更新');
});

loadTables().then(refreshAutoExportStatus);

const runJsonBtn = document.querySelector('#runJsonBtn');
const runTexBtn = document.querySelector('#runTexBtn');
const runAllBtn = document.querySelector('#runAllBtn');
const toolStatus = document.querySelector('#toolStatus');
const generatedFiles = document.querySelector('#generatedFiles');

async function refreshGeneratedFiles() {
  if (!generatedFiles) return;
  try {
    const files = await api('/api/files');
    if (!files.length) {
      generatedFiles.textContent = '暂无文件';
      return;
    }
    generatedFiles.innerHTML = files.map(f =>
      `<a href="${escapeHtml(f.url)}" title="${escapeHtml(f.modified_at)}">${escapeHtml(f.name)}</a>`
    ).join('');
  } catch (e) {
    generatedFiles.textContent = '文件列表读取失败';
  }
}

async function runTask(task, label) {
  if (toolStatus) toolStatus.textContent = `${label}：执行中...`;
  try {
    const res = await fetch(`/api/run/${task}`, { method: 'POST' });
    const payload = await res.json();
    if (!res.ok || !payload.ok) {
      const msg = payload.stderr || payload.error || '执行失败';
      throw new Error(msg);
    }
    if (toolStatus) toolStatus.textContent = `${label}：完成。${payload.stdout || ''}`;
    await refreshGeneratedFiles();
  } catch (e) {
    if (toolStatus) toolStatus.textContent = `${label}：失败。${e.message}`;
    alert(`${label}失败：${e.message}`);
  }
}

if (runJsonBtn) runJsonBtn.addEventListener('click', () => runTask('json', '生成 JSON'));
if (runTexBtn) runTexBtn.addEventListener('click', () => runTask('tex', '生成 TeX'));
if (runAllBtn) runAllBtn.addEventListener('click', () => runTask('json_tex', '全部生成'));

refreshGeneratedFiles();
