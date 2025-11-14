// === State & Constants ===
// Central in-memory state for current session. The backend is stateless
// aside from logs; the browser holds selection, pagination, and token.
let TOKEN = null;
const API = 'http://127.0.0.1:5000/api';
const PAGE_SIZE = 15;
let ALL_FILES = [];
let CURRENT_PAGE = 1;
const SELECTED = new Set();

// Activity status handling: lightweight UI feedback loop with animated dots
// and global button disabling while a request is in flight.
let activityTimer = null;
function setBusy(disabled) {
  ['connect-form','bulk-download-btn','check-new-btn','refresh-btn','disconnect-btn','select-all-files-btn','clear-selection-btn'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    if (el.tagName === 'FORM') {
      Array.from(el.elements).forEach(inp => inp.disabled = disabled);
    } else {
      el.disabled = disabled;
    }
  });
}

function showActivity(msg, state='info') {
  const bar = document.getElementById('activity-bar');
  const msgSpan = document.getElementById('activity-message');
  const dots = document.getElementById('activity-dots');
  if (!bar || !msgSpan || !dots) return;
  msgSpan.textContent = msg;
  dots.textContent = '';
  bar.className = 'alert py-2 px-3 small mb-3';
  if (state==='error') bar.classList.add('activity-error');
  else if (state==='success') bar.classList.add('activity-success');
  else bar.classList.add('activity-info');
  bar.classList.remove('d-none');
  bar.style.display = '';
  let dotCount = 0;
  if (activityTimer) clearInterval(activityTimer);
  activityTimer = setInterval(() => {
    dotCount = (dotCount + 1) % 4;
    dots.textContent = '.'.repeat(dotCount);
  }, 500);
  setBusy(true);
}

function hideActivity(finalState='success') {
  const bar = document.getElementById('activity-bar');
  if (!bar) return;
  if (activityTimer) {
    clearInterval(activityTimer);
    activityTimer = null;
  }
  // Show final state briefly with static style
  if (finalState==='error') {
    bar.classList.remove('activity-info','activity-success');
    bar.classList.add('activity-error');
  } else if (finalState==='success') {
    bar.classList.remove('activity-info','activity-error');
    bar.classList.add('activity-success');
  } else {
    bar.classList.remove('activity-error','activity-success');
    bar.classList.add('activity-info');
  }
  setTimeout(() => { if (bar) bar.style.display='none'; }, 800);
  setBusy(false);
}

// === Helpers ===
// Pure UI helpers for pagination & connection indicators.
function setConnected(connected, pwd='') {
  ['disconnect-btn','refresh-btn','bulk-download-btn','check-new-btn','select-all-files-btn','clear-selection-btn'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.disabled = !connected;
  });
  const statusEl = document.getElementById('status');
  if (statusEl) statusEl.textContent = connected ? `Connected (pwd: ${pwd})` : 'Not connected';
  const pwdEl = document.getElementById('pwd');
  if (pwdEl) pwdEl.value = pwd || '';
}

async function api(path, opts={}) {
  const res = await fetch(`${API}${path}`, {
    headers: { ...(opts.headers || {}) },
    ...opts,
  });
  const contentType = res.headers.get('content-type') || '';
  let bodyData = null;
  if (contentType.includes('application/json')) {
    try { bodyData = await res.json(); } catch(_) { bodyData = null; }
  } else {
    bodyData = await res.text();
  }
  if (!res.ok) {
    const msg = `HTTP ${res.status}: ${(bodyData && bodyData.error) || (typeof bodyData==='string'? bodyData : JSON.stringify(bodyData))}`;
    const err = new Error(msg);
    err.body = bodyData;
    throw err;
  }
  return bodyData;
}

function updatePaginationBar() {
  const totalPages = Math.max(1, Math.ceil(ALL_FILES.length / PAGE_SIZE));
  if (CURRENT_PAGE > totalPages) CURRENT_PAGE = totalPages;
  const pi = document.getElementById('page-info');
  if (pi) pi.textContent = `Page ${CURRENT_PAGE}/${totalPages}`;
  const prev = document.getElementById('prev-page');
  if (prev) prev.disabled = CURRENT_PAGE === 1;
  const next = document.getElementById('next-page');
  if (next) next.disabled = CURRENT_PAGE === totalPages;
  const ti = document.getElementById('total-info');
  if (ti) ti.textContent = `${ALL_FILES.length} files`;
}

function renderFileList() {
  updatePaginationBar();
  const start = (CURRENT_PAGE - 1) * PAGE_SIZE;
  const pageFiles = ALL_FILES.slice(start, start + PAGE_SIZE);
  const tbody = document.getElementById('files-tbody');
  tbody.innerHTML = '';
  pageFiles.forEach(f => {
    const checked = SELECTED.has(f.name) ? 'checked' : '';
    const disabled = f.downloaded ? 'disabled' : '';
    const tr = document.createElement('tr');
    if (!f.matches_pattern) tr.classList.add('invalid-row');
    tr.innerHTML = `
      <td><input type="checkbox" class="file-check" data-name="${f.name}" ${checked} ${disabled}></td>
      <td>${f.name}</td>
      <td>${f.matches_pattern ? 'Yes' : 'No'}</td>
      <td>${f.downloaded ? 'Yes' : 'No'}</td>`;
    tbody.appendChild(tr);
  });
  const master = document.getElementById('master-page-check');
  if (master) {
    const pageSelectable = pageFiles.filter(f => !f.downloaded);
    master.checked = pageSelectable.length > 0 && pageSelectable.every(f => SELECTED.has(f.name));
    master.indeterminate = !master.checked && pageSelectable.some(f => SELECTED.has(f.name));
  }
}

// === Core Actions ===
// Network-facing operations interacting with the Flask API.
async function doList() {
  if (!TOKEN) return;
  showActivity('Retrieving file list, please wait');
  const listResp = await api('/list', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: TOKEN })
  });
  setConnected(true, listResp.pwd || '');
  const j = await api('/list-files', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: TOKEN })
  });
  ALL_FILES = j.files || [];
  // Prune any selections that are no longer in the list (downloaded or invalid and thus hidden)
  const currentNames = new Set(ALL_FILES.map(f => f.name));
  Array.from(SELECTED).forEach(n => { if (!currentNames.has(n)) SELECTED.delete(n); });
  CURRENT_PAGE = 1;
  renderFileList();
  hideActivity('success');
}

async function bulkDownload(selectedNames) {
  if (!selectedNames.length) { alert('No files selected'); return; }
  showActivity('Downloading & validating selected files');
  const res = await api('/bulk-download', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: TOKEN, files: selectedNames, skipDownloaded: true })
  });
  // Build user-friendly sentence output
  const lines = [];
  res.results.forEach((r, idx) => {
    const num = idx + 1;
    if (r.skipped && r.reason === 'already_downloaded') {
      lines.push(`${num}. ${r.name} skipped (already downloaded).`);
    } else if (r.skipped && r.reason === 'previously_invalid') {
      lines.push(`${num}. ${r.name} skipped (previously invalid).`);
    } else if (r.error) {
      lines.push(`${num}. ${r.name} error: ${r.error}`);
    } else if (r.valid) {
      lines.push(`${num}. ${r.name} downloaded successfully (${r.rows} rows).`);
    } else {
      const issues = (r.issues && r.issues.length) ? r.issues.join(', ') : 'unknown issues';
      lines.push(`${num}. ${r.name} invalid (${issues}).`);
    }
  });
  document.getElementById('bulk-output').value = lines.join('\n');
  // summary footer
  const summaryEl = document.getElementById('results-summary');
  if (summaryEl) {
    const validCount = res.results.filter(r=>r.valid).length;
    const invalidCount = res.results.filter(r=>r.valid===false && !r.skipped && !r.error).length;
    const skippedCount = res.results.filter(r=>r.skipped).length;
    const errorCount = res.results.filter(r=>r.error).length;
    summaryEl.textContent = `Valid: ${validCount} | Invalid: ${invalidCount} | Skipped: ${skippedCount} | Errors: ${errorCount}`;
  }
  // Update selection: remove those that validated OK; keep invalid for potential re-download
  res.results.forEach(r => {
    if (r.valid) SELECTED.delete(r.name); else if (!r.error) SELECTED.add(r.name);
  });
  await doList();
  renderFileList();
  hideActivity('success');
}

async function checkNewFiles() {
  showActivity('Checking for new files');
  const res = await api('/new-files', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: TOKEN })
  });
  const nf = document.getElementById('new-files');
  if (nf) nf.textContent = res.new.join(', ') || 'None';
  hideActivity('success');
}

async function connect(evt) {
  evt.preventDefault();
  const host = document.getElementById('host').value.trim();
  const port = Number(document.getElementById('port').value);
  const user = document.getElementById('user').value.trim();
  const password = document.getElementById('password').value;
  try {
    showActivity('Connecting to FTP server');
    const j = await api('/connect', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ host, port, user, password }) });
    TOKEN = j.token;
    try { await doList(); } catch(_) {}
    hideActivity('success');
  } catch (err) {
    hideActivity('error');
    alert('Connect failed: ' + err.message + '\nEnsure backend (Flask) is running on 127.0.0.1:5000 and FTP server on provided host/port.');
  }
}

async function disconnect() {
  if (!TOKEN) return;
  try {
    await api('/disconnect', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: TOKEN }) });
  } catch(_) {}
  TOKEN = null;
  setConnected(false);
  ALL_FILES = [];
  SELECTED.clear();
  renderFileList();
}

// === Event Wiring ===
// Hook DOM events after initial load; keeps HTML minimal and logic centralized.
window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('connect-form').addEventListener('submit', connect);
  document.getElementById('disconnect-btn').addEventListener('click', disconnect);
  document.getElementById('refresh-btn').addEventListener('click', doList);
  document.getElementById('bulk-download-btn').addEventListener('click', () => {
    bulkDownload(Array.from(SELECTED.values()));
  });
  document.getElementById('check-new-btn').addEventListener('click', checkNewFiles);
  const prev = document.getElementById('prev-page');
  const next = document.getElementById('next-page');
  if (prev) prev.addEventListener('click', () => { if (CURRENT_PAGE>1){CURRENT_PAGE--; renderFileList(); }});
  if (next) next.addEventListener('click', () => { const totalPages=Math.max(1,Math.ceil(ALL_FILES.length/PAGE_SIZE)); if (CURRENT_PAGE<totalPages){CURRENT_PAGE++; renderFileList(); }});
  const master = document.getElementById('master-page-check');
  if (master) master.addEventListener('change', e => {
    const start = (CURRENT_PAGE - 1) * PAGE_SIZE;
    const pageFiles = ALL_FILES.slice(start, start + PAGE_SIZE).filter(f => !f.downloaded);
    if (e.target.checked) pageFiles.forEach(f => SELECTED.add(f.name)); else pageFiles.forEach(f => SELECTED.delete(f.name));
    renderFileList();
  });
  document.getElementById('files-tbody').addEventListener('change', e => {
    if (e.target.classList.contains('file-check')) {
      const name = e.target.getAttribute('data-name');
      if (e.target.checked) SELECTED.add(name); else SELECTED.delete(name);
      renderFileList();
    }
  });
  const selectAllBtn = document.getElementById('select-all-files-btn');
  if (selectAllBtn) selectAllBtn.addEventListener('click', () => { ALL_FILES.filter(f=>!f.downloaded).forEach(f=>SELECTED.add(f.name)); renderFileList(); });
  const clearBtn = document.getElementById('clear-selection-btn');
  if (clearBtn) clearBtn.addEventListener('click', () => { SELECTED.clear(); renderFileList(); });
});
