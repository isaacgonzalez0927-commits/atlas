import {
  loadClients,
  upsertClient,
  deleteClient,
  getClient,
  CLIENT_STATUSES,
  REQUEST_STATUSES,
  ASSET_KEYS,
  assetCompletion,
  missingAssets,
  allRequests,
  allNotes,
  addRequest,
  updateRequest,
  addNote,
  updateNote,
  updateAssets,
  dashboardMetrics,
  recentActivity,
  initStore,
  checkHealth,
  verifyAuth,
  clearAuthCode,
  getAuthCode,
  exportBackup,
  importBackup,
  fetchDashboard,
  fetchLeadHistory,
  fetchLeadStats,
  fetchLeadLearning,
  fetchStorageStatus,
} from './store.js';
import {
  renderLeadsPage,
  bindLeadsPage,
  initLeadsPageData,
} from './leads.js';
import { withIcon } from './icons.js';

const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];

let modalCallback = null;
let _booted = false;

function showLoading() {
  const main = $('#main-content');
  if (main) main.innerHTML = '<div class="loading">Loading…</div>';
}

function showLoginScreen(authRequired) {
  const el = $('#login-screen');
  if (el) {
    el.classList.add('show');
    const hint = $('#login-hint');
    if (hint) {
      hint.textContent = authRequired
        ? 'Enter your Atlas access code to continue.'
        : 'Starting Atlas…';
    }
    const form = $('#login-form');
    if (form) form.style.display = authRequired ? '' : 'none';
  }
  $('#app-shell')?.classList.add('hidden');
}

function hideLoginScreen() {
  $('#login-screen')?.classList.remove('show');
  $('#app-shell')?.classList.remove('hidden');
}

function showError(msg) {
  const el = $('#login-error');
  if (el) {
    el.textContent = msg;
    el.style.display = msg ? 'block' : 'none';
  }
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s ?? '';
  return d.innerHTML;
}

function fmtDate(d) {
  if (!d) return '—';
  try {
    return new Date(d + (d.length === 10 ? 'T12:00:00' : '')).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    });
  } catch {
    return d;
  }
}

function fmtDateTime(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function statusBadge(status, map, prefix) {
  const label = map[status] || status;
  const cls = `${prefix}-${status.replace(/_/g, '-')}`;
  return `<span class="badge badge-${cls}">${esc(label)}</span>`;
}

function clientStatusBadge(s) {
  const map = { onboarding: 'onboarding', waiting_on_client: 'waiting', building: 'building', live: 'live' };
  return `<span class="badge badge-${map[s] || 'onboarding'}">${esc(CLIENT_STATUSES[s] || s)}</span>`;
}

function requestStatusBadge(s) {
  const map = { submitted: 'submitted', in_progress: 'progress', complete: 'complete' };
  return `<span class="badge badge-${map[s] || 'submitted'}">${esc(REQUEST_STATUSES[s] || s)}</span>`;
}

function openModal(title, bodyHtml, onSave) {
  $('#modal-title').textContent = title;
  $('#modal-body').innerHTML = bodyHtml;
  $('#modal-backdrop').classList.add('show');
  modalCallback = onSave;
}

function closeModal() {
  $('#modal-backdrop').classList.remove('show');
  modalCallback = null;
}

function clientFormFields(c = {}) {
  const opts = Object.entries(CLIENT_STATUSES)
    .map(([k, v]) => `<option value="${k}" ${c.status === k ? 'selected' : ''}>${esc(v)}</option>`)
    .join('');
  return `
    <div class="form-grid">
      <div class="field"><label>Business Name</label><input name="businessName" value="${esc(c.businessName || '')}" required></div>
      <div class="field"><label>Contact Name</label><input name="contactName" value="${esc(c.contactName || '')}"></div>
      <div class="field"><label>Email</label><input name="email" type="email" value="${esc(c.email || '')}"></div>
      <div class="field"><label>Phone</label><input name="phone" value="${esc(c.phone || '')}"></div>
      <div class="field"><label>Website</label><input name="website" value="${esc(c.website || '')}" placeholder="https://"></div>
      <div class="field"><label>Status</label><select name="status">${opts}</select></div>
      <div class="field"><label>Date Signed</label><input name="dateSigned" type="date" value="${esc(c.dateSigned || '')}"></div>
    </div>`;
}

function readClientForm(form) {
  const fd = new FormData(form);
  return {
    businessName: fd.get('businessName')?.toString().trim() || '',
    contactName: fd.get('contactName')?.toString().trim() || '',
    email: fd.get('email')?.toString().trim() || '',
    phone: fd.get('phone')?.toString().trim() || '',
    website: fd.get('website')?.toString().trim() || '',
    status: fd.get('status')?.toString() || 'onboarding',
    dateSigned: fd.get('dateSigned')?.toString() || new Date().toISOString().slice(0, 10),
  };
}

function renderDashboardHtml(dash) {
  const clients = dash?.clients || {};
  const leads = dash?.leads || {};
  const feed = recentActivity(loadClients());

  return `
    <div class="page-header">
      <h1>Dashboard</h1>
      <p>Ascend operations at a glance</p>
    </div>
    <div class="grid">
      <div class="card"><div class="num">${leads.total ?? 0}</div><div class="lbl">Total Leads Called</div></div>
      <div class="card"><div class="num">${leads.previews ?? 0}</div><div class="lbl">Previews</div></div>
      <div class="card"><div class="num">${leads.clients ?? 0}</div><div class="lbl">Clients Won</div></div>
      <div class="card"><div class="num">${leads.conversion_rate ?? 0}%</div><div class="lbl">Conversion Rate</div></div>
      <div class="card"><div class="num">${clients.open_requests ?? 0}</div><div class="lbl">Open Updates</div></div>
      <div class="card"><div class="num">${clients.active ?? 0}</div><div class="lbl">Active Clients</div></div>
    </div>
    <div class="panel">
      <h2>Recent Calls</h2>
      ${(dash?.recent_calls || []).length ? (dash.recent_calls).map((c) => `
        <div class="feed-item">
          <div>${esc(c.business_name)} — ${esc(c.outcome_label || c.outcome)}</div>
          <div class="feed-time">${esc(c.city || '')} · Score ${c.score ?? '—'}</div>
        </div>`).join('') : '<div class="empty">Call outcomes will appear here as Sebastien logs leads.</div>'}
    </div>
    <div class="panel">
      <h2>Recent Activity</h2>
      ${feed.length ? feed.map((e) => `
        <div class="feed-item">
          <div>${esc(e.text)}</div>
          <div class="feed-time">${fmtDate(e.at)}</div>
        </div>`).join('') : '<div class="empty">Client activity will show here.</div>'}
    </div>`;
}

function renderAnalyticsHtml(stats, learning) {
  const topInterest = (stats?.top_cities_interest || []).slice(0, 5);
  const topClose = (stats?.top_cities_close || []).slice(0, 5);

  return `
    <div class="page-header">
      <h1>Analytics</h1>
      <p>Lead performance and learning insights</p>
    </div>
    <div class="grid">
      <div class="card"><div class="num">${stats?.total_calls ?? 0}</div><div class="lbl">Total Calls Logged</div></div>
      <div class="card"><div class="num">${stats?.dead_interest ?? 0}%</div><div class="lbl">Dead Site Interest</div></div>
      <div class="card"><div class="num">${stats?.no_interest ?? 0}%</div><div class="lbl">No Site Interest</div></div>
      <div class="card"><div class="num">${learning?.active ? 'On' : 'Off'}</div><div class="lbl">Learning Active</div></div>
    </div>
    <div class="panel">
      <h2>Top Cities — Interest Rate</h2>
      ${topInterest.length ? `<table class="desktop-table"><thead><tr><th>City</th><th>Calls</th><th>Rate</th></tr></thead><tbody>
        ${topInterest.map((r) => `<tr><td>${esc(r.city)}</td><td>${r.calls}</td><td>${r.rate}%</td></tr>`).join('')}
      </tbody></table>` : '<div class="empty">Need more logged calls for city stats.</div>'}
    </div>
    <div class="panel">
      <h2>Top Cities — Close Rate</h2>
      ${topClose.length ? `<table class="desktop-table"><thead><tr><th>City</th><th>Calls</th><th>Rate</th></tr></thead><tbody>
        ${topClose.map((r) => `<tr><td>${esc(r.city)}</td><td>${r.calls}</td><td>${r.rate}%</td></tr>`).join('')}
      </tbody></table>` : '<div class="empty">Need more logged calls for close stats.</div>'}
    </div>
    <div class="panel">
      <h2>Learning System</h2>
      <p style="color:var(--muted);font-size:0.85rem;line-height:1.5">
        ${learning?.active
    ? `Learning from ${learning.total_calls} calls. Outcomes adjust future lead scores.`
    : `Learning activates after ${learning?.min_calls ?? 10} logged calls.`}
        ${learning?.openai_enabled ? ` OpenAI refinement available after ${learning.openai_min_calls} calls.` : ''}
      </p>
    </div>`;
}

function renderSettingsHtml(storage) {
  return `
    <div class="page-header">
      <h1>Settings</h1>
      <p>Backup, storage, and more</p>
    </div>
    <div class="panel">
      <h2>Quick Links</h2>
      <div class="btn-row">
        <a class="btn btn-ghost btn-sm" href="#/assets">${withIcon('assets', 'Assets')}</a>
        <a class="btn btn-ghost btn-sm" href="#/notes">${withIcon('notes', 'Notes')}</a>
        <a class="btn btn-ghost btn-sm" href="#/analytics">${withIcon('analytics', 'Analytics')}</a>
      </div>
    </div>
    <div class="panel">
      <h2>Backup</h2>
      <p style="color:var(--muted);font-size:0.85rem;line-height:1.5;margin-bottom:14px;">
        Export includes clients, call outcomes, and lead history.
      </p>
      <div class="btn-row" style="margin-bottom:0;">
        <button class="btn btn-primary btn-sm" id="btn-export-backup">${withIcon('export', 'Export Backup')}</button>
        <button class="btn btn-ghost btn-sm" id="btn-import-backup">${withIcon('import', 'Import Backup')}</button>
      </div>
    </div>
    <div class="panel">
      <h2>Storage</h2>
      <div class="info-grid">
        <div><span class="muted">Clients</span><br>${storage?.clients_in_db ?? '—'}</div>
        <div><span class="muted">Calls logged</span><br>${storage?.calls_in_db ?? '—'}</div>
        <div><span class="muted">Remote backup</span><br>${esc(storage?.remote || 'none')}</div>
        <div><span class="muted">Data directory</span><br><span style="font-size:0.75rem">${esc(storage?.data_dir || '')}</span></div>
      </div>
    </div>`;
}

function renderClientsList() {
  const clients = loadClients().sort((a, b) => (b.dateSigned || '').localeCompare(a.dateSigned || ''));

  const tableRows = clients.length ? clients.map((c) => `
    <tr>
      <td><a href="#/clients/${c.id}">${esc(c.businessName)}</a></td>
      <td>${esc(c.contactName)}</td>
      <td>${clientStatusBadge(c.status)}</td>
      <td>${fmtDate(c.dateSigned)}</td>
      <td><button class="btn btn-ghost btn-sm" data-edit-client="${c.id}">${withIcon('edit', 'Edit')}</button>
          <button class="btn btn-danger btn-sm" data-delete-client="${c.id}">${withIcon('delete', 'Delete')}</button></td>
    </tr>`).join('') : '<tr><td colspan="5" class="empty">No clients yet — tap Add Client to start.</td></tr>';

  const mobileCards = clients.length ? clients.map((c) => `
    <div class="list-card">
      <div class="list-card-top">
        <a href="#/clients/${c.id}" class="list-card-title">${esc(c.businessName)}</a>
        ${clientStatusBadge(c.status)}
      </div>
      <div class="list-card-meta">${esc(c.contactName)} · Signed ${fmtDate(c.dateSigned)}</div>
      <div class="list-card-actions">
        <a href="#/clients/${c.id}" class="btn btn-primary btn-sm">${withIcon('view', 'View')}</a>
        <button class="btn btn-ghost btn-sm" data-edit-client="${c.id}">${withIcon('edit', 'Edit')}</button>
        <button class="btn btn-danger btn-sm" data-delete-client="${c.id}">${withIcon('delete', 'Delete')}</button>
      </div>
    </div>`).join('') : '<div class="empty">No clients yet — tap Add Client to start.</div>';

  return `
    <div class="page-header">
      <h1>Clients</h1>
      <p>Manage signed clients and project status</p>
    </div>
    <div class="btn-row">
      <button class="btn btn-primary" id="btn-add-client">${withIcon('plus', 'Add Client')}</button>
    </div>
    <div class="panel desktop-table table-wrap">
      <table>
        <thead>
          <tr>
            <th>Business</th>
            <th>Contact</th>
            <th>Status</th>
            <th>Signed</th>
            <th></th>
          </tr>
        </thead>
        <tbody>${tableRows}</tbody>
      </table>
    </div>
    <div class="mobile-list list-cards">${mobileCards}</div>`;
}

function renderAssetsPage() {
  const clients = loadClients();

  if (!clients.length) {
    return `
      <div class="page-header">
        <h1>Assets</h1>
        <p>Per-client asset checklist and completion</p>
      </div>
      <div class="empty panel">Add a client first, then track their assets here.</div>`;
  }

  return `
    <div class="page-header">
      <h1>Assets</h1>
      <p>Per-client asset checklist and completion</p>
    </div>
    <div class="grid" style="grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));">
      ${clients.map((c) => {
        const { pct } = assetCompletion(c.assets);
        const missing = missingAssets(c.assets);
        return `
          <div class="card" style="text-align:left;">
            <div style="font-weight:700;margin-bottom:4px;"><a href="#/clients/${c.id}/assets">${esc(c.businessName)}</a></div>
            <div class="progress-bar"><div class="progress-fill" style="width:${pct}%"></div></div>
            <div style="font-size:0.85rem;color:var(--accent);font-weight:600;">${pct}% complete</div>
            ${missing.length
              ? `<div style="font-size:0.78rem;color:var(--muted);margin-top:8px;">Missing: ${esc(missing.join(', '))}</div>`
              : '<div style="font-size:0.78rem;color:var(--green);margin-top:8px;">All assets received</div>'}
          </div>`;
      }).join('')}
    </div>`;
}

function renderRequestsPage() {
  const clients = loadClients();
  const requests = allRequests(clients);

  const tableRows = requests.length ? requests.map((r) => `
    <tr>
      <td><a href="#/clients/${r.clientId}/requests">${esc(r.clientName)}</a></td>
      <td>${esc(r.title)}</td>
      <td>${requestStatusBadge(r.status)}</td>
      <td>${fmtDate(r.dateSubmitted)}</td>
      <td><button class="btn btn-ghost btn-sm" data-update-request="${r.clientId}:${r.id}">${withIcon('updates', 'Update')}</button></td>
    </tr>`).join('') : '<tr><td colspan="5" class="empty">No requests yet.</td></tr>';

  const mobileCards = requests.length ? requests.map((r) => `
    <div class="list-card">
      <div class="list-card-top">
        <span class="list-card-title">${esc(r.title)}</span>
        ${requestStatusBadge(r.status)}
      </div>
      <div class="list-card-meta">
        <a href="#/clients/${r.clientId}/requests">${esc(r.clientName)}</a>
        · ${fmtDate(r.dateSubmitted)}
      </div>
      <div class="list-card-actions">
        <button class="btn btn-ghost btn-sm" data-update-request="${r.clientId}:${r.id}">${withIcon('updates', 'Update Status')}</button>
      </div>
    </div>`).join('') : '<div class="empty">No requests yet.</div>';

  return `
    <div class="page-header">
      <h1>Updates</h1>
      <p>Client website change requests</p>
    </div>
    <div class="btn-row">
      <button class="btn btn-primary" id="btn-add-request">${withIcon('plus', 'Create Request')}</button>
    </div>
    <div class="panel desktop-table table-wrap">
      <table>
        <thead>
          <tr>
            <th>Client</th>
            <th>Title</th>
            <th>Status</th>
            <th>Submitted</th>
            <th></th>
          </tr>
        </thead>
        <tbody>${tableRows}</tbody>
      </table>
    </div>
    <div class="mobile-list list-cards">${mobileCards}</div>`;
}

function renderNotesPage() {
  const clients = loadClients();
  const notes = allNotes(clients);

  return `
    <div class="page-header">
      <h1>Notes</h1>
      <p>Internal notes per client</p>
    </div>
    <div class="btn-row">
      <button class="btn btn-primary" id="btn-add-note">${withIcon('plus', 'Add Note')}</button>
    </div>
    <div class="panel">
      ${notes.length ? notes.map((n) => `
        <div class="note-item">
          <div class="note-meta">
            <a href="#/clients/${n.clientId}/notes">${esc(n.clientName)}</a>
            · ${fmtDateTime(n.updatedAt)}
            <button class="btn btn-ghost btn-sm" style="margin-left:8px;" data-edit-note="${n.clientId}:${n.id}">${withIcon('edit', 'Edit')}</button>
          </div>
          <div class="note-body">${esc(n.text)}</div>
        </div>`).join('') : '<div class="empty">No notes yet</div>'}
    </div>`;
}

function renderAssetChecklist(client, editable = true) {
  const { pct } = assetCompletion(client.assets);
  const missing = missingAssets(client.assets);
  return `
    <div style="margin-bottom:16px;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span style="font-weight:600;color:var(--accent);">${pct}% complete</span>
        ${missing.length ? `<span style="font-size:0.8rem;color:var(--muted);">Missing: ${esc(missing.join(', '))}</span>` : ''}
      </div>
      <div class="progress-bar"><div class="progress-fill" style="width:${pct}%"></div></div>
    </div>
    ${ASSET_KEYS.map(({ key, label }) => `
      <div class="asset-row">
        <span>${esc(label)}</span>
        ${editable
          ? `<input type="checkbox" class="asset-check" data-asset-key="${key}" ${client.assets?.[key] ? 'checked' : ''}>`
          : `<span class="badge ${client.assets?.[key] ? 'badge-live' : 'badge-waiting'}">${client.assets?.[key] ? '✓' : '—'}</span>`}
      </div>`).join('')}`;
}

function renderClientDetail(id, tab = 'overview') {
  const client = getClient(id);
  if (!client) {
    return `<div class="empty">Client not found. <a href="#/clients">Back to clients</a></div>`;
  }

  const { pct } = assetCompletion(client.assets);
  const openReqs = (client.requests || []).filter((r) => r.status !== 'complete');
  const recentNotes = [...(client.notes || [])].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)).slice(0, 3);

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'assets', label: 'Assets' },
    { id: 'requests', label: 'Requests' },
    { id: 'notes', label: 'Notes' },
  ];

  let tabContent = '';

  if (tab === 'overview') {
    tabContent = `
      <div class="grid" style="grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); margin-bottom:20px;">
        <div class="card"><div class="num">${pct}%</div><div class="lbl">Assets</div></div>
        <div class="card"><div class="num">${openReqs.length}</div><div class="lbl">Open Requests</div></div>
        <div class="card"><div class="num">${(client.notes || []).length}</div><div class="lbl">Notes</div></div>
      </div>
      <div class="panel">
        <h2>Client Information</h2>
        <div class="info-grid">
          <div><div class="info-label">Contact</div><div class="info-value">${esc(client.contactName) || '—'}</div></div>
          <div><div class="info-label">Email</div><div class="info-value">${esc(client.email) || '—'}</div></div>
          <div><div class="info-label">Phone</div><div class="info-value">${esc(client.phone) || '—'}</div></div>
          <div><div class="info-label">Website</div><div class="info-value">${client.website ? `<a href="${esc(client.website)}" target="_blank" rel="noopener">${esc(client.website)}</a>` : '—'}</div></div>
          <div><div class="info-label">Status</div><div class="info-value">${clientStatusBadge(client.status)}</div></div>
          <div><div class="info-label">Date Signed</div><div class="info-value">${fmtDate(client.dateSigned)}</div></div>
        </div>
        <div class="btn-row" style="margin-top:16px;">
          <button class="btn btn-ghost btn-sm" id="btn-edit-client-detail">${withIcon('edit', 'Edit Client')}</button>
          <button class="btn btn-danger btn-sm" id="btn-delete-client-detail">${withIcon('delete', 'Delete Client')}</button>
        </div>
      </div>
      ${openReqs.length ? `
        <div class="panel">
          <h2>Open Requests</h2>
          ${openReqs.map((r) => `
            <div class="feed-item">
              <div>${esc(r.title)} ${requestStatusBadge(r.status)}</div>
              <div class="feed-time">${esc(r.description)}</div>
            </div>`).join('')}
        </div>` : ''}
      ${recentNotes.length ? `
        <div class="panel">
          <h2>Recent Notes</h2>
          ${recentNotes.map((n) => `
            <div class="note-item">
              <div class="note-meta">${fmtDateTime(n.updatedAt)}</div>
              <div class="note-body">${esc(n.text)}</div>
            </div>`).join('')}
        </div>` : ''}`;
  } else if (tab === 'assets') {
    tabContent = `<div class="panel"><h2>Asset Checklist</h2>${renderAssetChecklist(client)}</div>`;
  } else if (tab === 'requests') {
    const reqs = [...(client.requests || [])].sort((a, b) => (b.dateSubmitted || '').localeCompare(a.dateSubmitted || ''));
    tabContent = `
      <div class="btn-row"><button class="btn btn-primary btn-sm" id="btn-add-request-client">${withIcon('plus', 'New Request')}</button></div>
      <div class="panel">
        ${reqs.length ? reqs.map((r) => `
          <div class="feed-item">
            <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;">
              <strong>${esc(r.title)}</strong>
              ${requestStatusBadge(r.status)}
            </div>
            <div class="feed-time">${fmtDate(r.dateSubmitted)}</div>
            <p style="margin-top:8px;color:var(--muted);font-size:0.88rem;">${esc(r.description)}</p>
            <button class="btn btn-ghost btn-sm" data-update-request="${client.id}:${r.id}" style="margin-top:8px;">${withIcon('updates', 'Update Status')}</button>
          </div>`).join('') : '<div class="empty">No requests for this client</div>'}
      </div>`;
  } else if (tab === 'notes') {
    const notes = [...(client.notes || [])].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
    tabContent = `
      <div class="btn-row"><button class="btn btn-primary btn-sm" id="btn-add-note-client">${withIcon('plus', 'Add Note')}</button></div>
      <div class="panel">
        ${notes.length ? notes.map((n) => `
          <div class="note-item">
            <div class="note-meta">
              ${fmtDateTime(n.updatedAt)}
              <button class="btn btn-ghost btn-sm" data-edit-note="${client.id}:${n.id}">${withIcon('edit', 'Edit')}</button>
            </div>
            <div class="note-body">${esc(n.text)}</div>
          </div>`).join('') : '<div class="empty">No notes yet</div>'}
      </div>`;
  }

  return `
    <a href="#/clients" class="back-link">← All Clients</a>
    <div class="page-header">
      <h1>${esc(client.businessName)}</h1>
      <p>${clientStatusBadge(client.status)} · Signed ${fmtDate(client.dateSigned)}</p>
    </div>
    <div class="tabs">
      ${tabs.map((t) => `
        <button class="tab ${t.id === tab ? 'active' : ''}" data-tab="${t.id}">${t.label}</button>`).join('')}
    </div>
    ${tabContent}`;
}

function parseRoute() {
  const hash = location.hash.slice(1) || '/';
  const parts = hash.split('/').filter(Boolean);
  return parts;
}

function setActiveNav(route) {
  const page = route[0] || 'dashboard';
  const morePages = new Set(['settings', 'assets', 'notes', 'analytics']);
  $$('[data-nav]').forEach((a) => {
    const nav = a.dataset.nav;
    const active = nav === page
      || (nav === 'clients' && page === 'clients')
      || (nav === 'settings' && morePages.has(page));
    a.classList.toggle('active', active);
  });
}

async function render() {
  if (!_booted) return;
  const route = parseRoute();
  const main = $('#main-content');
  setActiveNav(route);

  try {
    if (!route.length || route[0] === 'dashboard') {
      main.innerHTML = '<div class="loading">Loading dashboard…</div>';
      const dash = await fetchDashboard();
      main.innerHTML = renderDashboardHtml(dash);
    } else if (route[0] === 'leads') {
      const cities = await initLeadsPageData();
      main.innerHTML = renderLeadsPage(cities);
      await bindLeadsPage(() => render());
    } else if (route[0] === 'clients' && route.length === 1) {
      main.innerHTML = renderClientsList();
      bindClientsList();
    } else if (route[0] === 'clients' && route.length >= 2) {
      const tab = route[2] || 'overview';
      main.innerHTML = renderClientDetail(route[1], tab);
      bindClientDetail(route[1], tab);
    } else if (route[0] === 'assets') {
      main.innerHTML = renderAssetsPage();
    } else if (route[0] === 'requests') {
      main.innerHTML = renderRequestsPage();
      bindRequestsPage();
    } else if (route[0] === 'notes') {
      main.innerHTML = renderNotesPage();
      bindNotesPage();
    } else if (route[0] === 'analytics') {
      main.innerHTML = '<div class="loading">Loading analytics…</div>';
      const [stats, learning] = await Promise.all([
        fetchLeadStats(),
        fetchLeadLearning(),
      ]);
      main.innerHTML = renderAnalyticsHtml(stats, learning);
    } else if (route[0] === 'settings') {
      const storage = await fetchStorageStatus();
      main.innerHTML = renderSettingsHtml(storage);
      bindBackupButtons();
    } else {
      const dash = await fetchDashboard();
      main.innerHTML = renderDashboardHtml(dash);
    }
  } catch {
    main.innerHTML = '<div class="empty panel">Could not load this page. Check your connection.</div>';
  }
  window.scrollTo(0, 0);
}

async function startApp() {
  showLoading();
  try {
    await initStore();
    _booted = true;
    hideLoginScreen();
    await render();
  } catch (err) {
    if (err.message === 'unauthorized') {
      clearAuthCode();
      const health = await checkHealth();
      showLoginScreen(health.auth_required);
    } else {
      $('#main-content').innerHTML = '<div class="empty panel">Could not connect to Atlas. Is the server running?</div>';
    }
  }
}

function serverErrorHtml(reason) {
  const port = window.location.port || '5001';
  const host = window.location.hostname;
  const localUrl = `http://${host === 'localhost' || host === '127.0.0.1' ? 'localhost' : host}:${port}`;

  if (reason === 'file_protocol') {
    return `
      <div class="empty panel">
        <p><strong>Atlas must run through the server.</strong></p>
        <p style="margin-top:12px;color:var(--muted);">Don't open the HTML file directly. In Terminal:</p>
        <pre style="margin-top:12px;padding:12px;background:rgba(0,0,0,0.3);border-radius:10px;overflow-x:auto;font-size:0.8rem;">cd atlas
python3 app.py</pre>
        <p style="margin-top:12px;">Then open <a href="http://localhost:5001">http://localhost:5001</a></p>
      </div>`;
  }

  if (reason === 'no_api') {
    return `
      <div class="empty panel">
        <p><strong>Backend not deployed yet.</strong></p>
        <p style="margin-top:12px;color:var(--muted);line-height:1.5;">
          This URL is serving files only — the Flask API isn't running.
          On Render, create a <strong>Web Service</strong> (Python), not a Static Site.
        </p>
        <p style="margin-top:12px;color:var(--muted);">Build: <code>pip install -r requirements.txt</code><br>
        Start: <code>gunicorn app:app</code><br>
        Env: <code>ATLAS_CODE</code> = your password</p>
      </div>`;
  }

  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    return `
      <div class="empty panel">
        <p><strong>Server not running.</strong></p>
        <p style="margin-top:12px;color:var(--muted);">Start Atlas in Terminal:</p>
        <pre style="margin-top:12px;padding:12px;background:rgba(0,0,0,0.3);border-radius:10px;overflow-x:auto;font-size:0.8rem;">cd atlas
python3 app.py</pre>
        <p style="margin-top:12px;">Then open <a href="${localUrl}">${localUrl}</a></p>
        <p style="margin-top:8px;color:var(--muted);font-size:0.85rem;">(Not port 8765 — that old server has no API.)</p>
      </div>`;
  }

  return `
    <div class="empty panel">
      <p><strong>Could not reach Atlas server.</strong></p>
      <p style="margin-top:12px;color:var(--muted);line-height:1.5;">
        Render may still be waking up (free tier — wait 30s and refresh),
        or the service needs to be a Python Web Service with the latest code pushed.
      </p>
    </div>`;
}

async function boot() {
  try {
    const health = await checkHealth();
    if (health.auth_required && !getAuthCode()) {
      showLoginScreen(true);
      return;
    }
    await startApp();
  } catch (err) {
    const main = $('#main-content');
    if (main) {
      hideLoginScreen();
      $('#app-shell')?.classList.remove('hidden');
      main.innerHTML = serverErrorHtml(err.message);
    }
  }
}

function showClientModal(existing) {
  openModal(existing ? 'Edit Client' : 'Add Client', '', async () => {
    const f = $('#modal-body form');
    const data = readClientForm(f);
    if (!data.businessName) return false;
    try {
      await upsertClient(existing ? { ...data, id: existing.id } : data);
      closeModal();
      await render();
      return true;
    } catch {
      alert('Could not save client. Check your connection.');
      return false;
    }
  });
  $('#modal-body').innerHTML = `<form>${clientFormFields(existing)}</form>`;
}

function showRequestModal(clientId = null, existing = null) {
  const clients = loadClients();
  const clientOpts = clients.map((c) =>
    `<option value="${c.id}" ${(clientId || existing?.clientId) === c.id ? 'selected' : ''}>${esc(c.businessName)}</option>`
  ).join('');
  const statusOpts = Object.entries(REQUEST_STATUSES)
    .map(([k, v]) => `<option value="${k}" ${existing?.status === k ? 'selected' : ''}>${esc(v)}</option>`)
    .join('');

  openModal(existing ? 'Update Request' : 'Create Request', '', async () => {
    const f = $('#modal-body form');
    const fd = new FormData(f);
    const cid = (existing ? existing.clientId : fd.get('clientId')?.toString()) || '';
    const title = fd.get('title')?.toString().trim();
    if (!cid || !title) return false;
    try {
      if (existing) {
        await updateRequest(cid, existing.id, {
          title,
          description: fd.get('description')?.toString().trim() || '',
          status: fd.get('status')?.toString() || 'submitted',
        });
      } else {
        await addRequest(cid, {
          title,
          description: fd.get('description')?.toString().trim() || '',
          status: fd.get('status')?.toString() || 'submitted',
        });
      }
      closeModal();
      await render();
      return true;
    } catch {
      alert('Could not save request.');
      return false;
    }
  });

  $('#modal-body').innerHTML = `
    <form>
      <div class="form-grid" style="grid-template-columns:1fr;">
        <div class="field"><label>Client</label><select name="clientId" ${existing ? 'disabled' : ''}>${clientOpts}</select></div>
        <div class="field"><label>Request Title</label><input name="title" value="${esc(existing?.title || '')}" required></div>
        <div class="field"><label>Description</label><textarea name="description">${esc(existing?.description || '')}</textarea></div>
        <div class="field"><label>Status</label><select name="status">${statusOpts}</select></div>
      </div>
    </form>`;
}

function showNoteModal(clientId = null, existing = null) {
  const clients = loadClients();
  const clientOpts = clients.map((c) =>
    `<option value="${c.id}" ${(clientId || existing?.clientId) === c.id ? 'selected' : ''}>${esc(c.businessName)}</option>`
  ).join('');

  openModal(existing ? 'Edit Note' : 'Add Note', '', async () => {
    const f = $('#modal-body form');
    const fd = new FormData(f);
    const cid = fd.get('clientId')?.toString();
    const text = fd.get('text')?.toString().trim();
    if (!cid || !text) return false;
    try {
      if (existing) {
        await updateNote(cid, existing.id, text);
      } else {
        await addNote(cid, text);
      }
      closeModal();
      await render();
      return true;
    } catch {
      alert('Could not save note.');
      return false;
    }
  });

  $('#modal-body').innerHTML = `
    <form>
      <div class="form-grid" style="grid-template-columns:1fr;">
        ${existing ? '' : `<div class="field"><label>Client</label><select name="clientId">${clientOpts}</select></div>`}
        ${existing ? `<input type="hidden" name="clientId" value="${existing.clientId}">` : ''}
        <div class="field"><label>Note</label><textarea name="text" required>${esc(existing?.text || '')}</textarea></div>
      </div>
    </form>`;
}

function bindClientsList() {
  $('#btn-add-client')?.addEventListener('click', () => showClientModal());
  $$('[data-edit-client]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const c = getClient(btn.dataset.editClient);
      if (c) showClientModal(c);
    });
  });
  $$('[data-delete-client]').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      e.stopPropagation();
      const c = getClient(btn.dataset.deleteClient);
      if (c) await confirmDeleteClient(c);
    });
  });
}

async function confirmDeleteClient(client) {
  const name = client.businessName || 'this client';
  if (!confirm(`Delete "${name}"? All requests and notes for this client will be removed. This cannot be undone.`)) {
    return;
  }
  try {
    await deleteClient(client.id);
    location.hash = '#/clients';
    await render();
  } catch {
    alert('Could not delete client. Check your connection.');
  }
}

function bindRequestsPage() {
  $('#btn-add-request')?.addEventListener('click', () => showRequestModal());
  $$('[data-update-request]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const [cid, rid] = btn.dataset.updateRequest.split(':');
      const c = getClient(cid);
      const r = c?.requests?.find((x) => x.id === rid);
      if (r) showRequestModal(cid, { ...r, clientId: cid });
    });
  });
}

function bindNotesPage() {
  $('#btn-add-note')?.addEventListener('click', () => showNoteModal());
  $$('[data-edit-note]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const [cid, nid] = btn.dataset.editNote.split(':');
      const c = getClient(cid);
      const n = c?.notes?.find((x) => x.id === nid);
      if (n) showNoteModal(cid, { ...n, clientId: cid });
    });
  });
}

function bindClientDetail(clientId, tab) {
  $$('[data-tab]').forEach((btn) => {
    btn.addEventListener('click', () => {
      location.hash = `#/clients/${clientId}/${btn.dataset.tab}`;
    });
  });

  $('#btn-edit-client-detail')?.addEventListener('click', () => {
    const c = getClient(clientId);
    if (c) showClientModal(c);
  });

  $('#btn-delete-client-detail')?.addEventListener('click', async () => {
    const c = getClient(clientId);
    if (c) await confirmDeleteClient(c);
  });

  $$('.asset-check').forEach((cb) => {
    cb.addEventListener('change', async () => {
      const key = cb.dataset.assetKey;
      try {
        await updateAssets(clientId, { [key]: cb.checked });
      } catch {
        cb.checked = !cb.checked;
        alert('Could not update asset.');
      }
    });
  });

  $('#btn-add-request-client')?.addEventListener('click', () => showRequestModal(clientId));
  $('#btn-add-note-client')?.addEventListener('click', () => showNoteModal(clientId));

  $$('[data-update-request]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const [cid, rid] = btn.dataset.updateRequest.split(':');
      const c = getClient(cid);
      const r = c?.requests?.find((x) => x.id === rid);
      if (r) showRequestModal(cid, { ...r, clientId: cid });
    });
  });

  $$('[data-edit-note]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const [cid, nid] = btn.dataset.editNote.split(':');
      const c = getClient(cid);
      const n = c?.notes?.find((x) => x.id === nid);
      if (n) showNoteModal(cid, { ...n, clientId: cid });
    });
  });
}

function bindBackupButtons() {
  $('#btn-export-backup')?.addEventListener('click', async () => {
    try {
      await exportBackup();
    } catch {
      alert('Export failed. Check your connection.');
    }
  });

  $('#btn-import-backup')?.addEventListener('click', () => {
    $('#import-file')?.click();
  });
}

function init() {
  window.addEventListener('hashchange', () => render());

  $('#modal-save')?.addEventListener('click', async () => {
    if (modalCallback) await modalCallback();
  });
  $('#modal-cancel')?.addEventListener('click', closeModal);
  $('#modal-backdrop')?.addEventListener('click', (e) => {
    if (e.target.id === 'modal-backdrop') closeModal();
  });

  document.body.addEventListener('click', (e) => {
    const link = e.target.closest('[data-nav]');
    if (link) window.scrollTo(0, 0);
  });

  $('#login-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    showError('');
    const code = $('#login-code')?.value?.trim() || '';
    if (!code) return;
    const ok = await verifyAuth(code);
    if (!ok) {
      showError('Invalid access code.');
      return;
    }
    await startApp();
  });

  boot();

  bindBackupButtons();

  $('#sidebar-export')?.addEventListener('click', async () => {
    try {
      await exportBackup();
    } catch {
      alert('Export failed.');
    }
  });

  $('#sidebar-import')?.addEventListener('click', () => {
    $('#import-file')?.click();
  });

  $('#import-file')?.addEventListener('change', async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    const count = loadClients().length;
    const msg = count
      ? `Replace all data (${count} client(s)) with this backup? Calls and lead history will also be replaced.`
      : 'Import all data from this backup file?';
    if (!confirm(msg)) return;
    try {
      await importBackup(file);
      await render();
      alert('Backup restored successfully.');
    } catch {
      alert('Import failed. Make sure the file is a valid Atlas backup (.json).');
    }
  });
}

init();
