/** Atlas V0 — API client + in-memory cache (syncs across devices). */

const AUTH_KEY = 'atlas_auth_code';
const LEGACY_STORAGE_KEY = 'ascend_atlas_data';

export const CLIENT_STATUSES = {
  onboarding: 'Onboarding',
  waiting_on_client: 'Waiting On Client',
  building: 'Building',
  live: 'Live',
};

export const REQUEST_STATUSES = {
  submitted: 'Submitted',
  in_progress: 'In Progress',
  complete: 'Complete',
};

export const ASSET_KEYS = [
  { key: 'logo', label: 'Logo' },
  { key: 'photos', label: 'Photos' },
  { key: 'phone', label: 'Phone Number' },
  { key: 'email', label: 'Email' },
  { key: 'services', label: 'Services' },
  { key: 'about', label: 'About Us Content' },
];

let _clients = [];

export function getAuthCode() {
  return localStorage.getItem(AUTH_KEY) || sessionStorage.getItem(AUTH_KEY) || '';
}

export function setAuthCode(code) {
  localStorage.setItem(AUTH_KEY, code);
  sessionStorage.removeItem(AUTH_KEY);
}

export function clearAuthCode() {
  localStorage.removeItem(AUTH_KEY);
  sessionStorage.removeItem(AUTH_KEY);
}

async function api(method, path, body) {
  const headers = { 'Content-Type': 'application/json' };
  const code = getAuthCode();
  if (code) headers['X-Atlas-Code'] = code;

  const res = await fetch(path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    clearAuthCode();
    throw new Error('unauthorized');
  }

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `request_failed_${res.status}`);
  }
  return data;
}

export async function checkHealth() {
  if (window.location.protocol === 'file:') {
    throw new Error('file_protocol');
  }
  let res;
  try {
    res = await fetch('/api/health');
  } catch {
    throw new Error('network');
  }
  if (res.status === 404) {
    throw new Error('no_api');
  }
  if (!res.ok) {
    throw new Error('health_failed');
  }
  return res.json();
}

export async function verifyAuth(code) {
  setAuthCode(code);
  try {
    await api('GET', '/api/clients');
    return true;
  } catch {
    clearAuthCode();
    return false;
  }
}

function readLegacyLocalStorage() {
  try {
    const raw = localStorage.getItem(LEGACY_STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch (_) { /* ignore */ }
  return [];
}

export async function initStore() {
  _clients = await api('GET', '/api/clients');

  if (_clients.length === 0) {
    const legacy = readLegacyLocalStorage();
    if (legacy.length) {
      try {
        await api('POST', '/api/migrate', { clients: legacy });
        localStorage.removeItem(LEGACY_STORAGE_KEY);
        _clients = await api('GET', '/api/clients');
      } catch (_) { /* server may already have data */ }
    }
  }
  return _clients;
}

export async function refreshClients() {
  _clients = await api('GET', '/api/clients');
  return _clients;
}

/** Sync read from cache — call after initStore / refreshClients. */
export function loadClients() {
  return _clients;
}

export function getClient(id) {
  return _clients.find((c) => c.id === id) || null;
}

export async function upsertClient(data) {
  if (data.id) {
    const client = await api('PUT', `/api/clients/${data.id}`, data);
    await refreshClients();
    return client;
  }
  const client = await api('POST', '/api/clients', data);
  await refreshClients();
  return client;
}

export async function deleteClient(id) {
  await api('DELETE', `/api/clients/${id}`);
  await refreshClients();
}

export function assetCompletion(assets) {
  const total = ASSET_KEYS.length;
  const done = ASSET_KEYS.filter(({ key }) => assets?.[key]).length;
  return { done, total, pct: Math.round((done / total) * 100) };
}

export function missingAssets(assets) {
  return ASSET_KEYS.filter(({ key }) => !assets?.[key]).map(({ label }) => label);
}

export function allRequests(clients) {
  const out = [];
  clients.forEach((c) => {
    (c.requests || []).forEach((r) => {
      out.push({ ...r, clientId: c.id, clientName: c.businessName });
    });
  });
  return out.sort((a, b) => (b.dateSubmitted || '').localeCompare(a.dateSubmitted || ''));
}

export function allNotes(clients) {
  const out = [];
  clients.forEach((c) => {
    (c.notes || []).forEach((n) => {
      out.push({ ...n, clientId: c.id, clientName: c.businessName });
    });
  });
  return out.sort((a, b) => (b.updatedAt || '').localeCompare(a.updatedAt || ''));
}

export async function addRequest(clientId, req) {
  const item = await api('POST', `/api/clients/${clientId}/requests`, req);
  await refreshClients();
  return item;
}

export async function updateRequest(clientId, requestId, patch) {
  const item = await api('PUT', `/api/clients/${clientId}/requests/${requestId}`, patch);
  await refreshClients();
  return item;
}

export async function addNote(clientId, text) {
  const note = await api('POST', `/api/clients/${clientId}/notes`, { text });
  await refreshClients();
  return note;
}

export async function updateNote(clientId, noteId, text) {
  const note = await api('PUT', `/api/clients/${clientId}/notes/${noteId}`, { text });
  await refreshClients();
  return note;
}

export async function updateAssets(clientId, assets) {
  await api('PATCH', `/api/clients/${clientId}/assets`, assets);
  await refreshClients();
}

export function dashboardMetrics(clients) {
  const requests = allRequests(clients);
  return {
    totalClients: clients.length,
    activeProjects: clients.filter((c) => c.status === 'building').length,
    waitingOnClient: clients.filter((c) => c.status === 'waiting_on_client').length,
    openRequests: requests.filter((r) => r.status !== 'complete').length,
  };
}

export function recentActivity(clients, limit = 12) {
  const events = [];
  clients.forEach((c) => {
    events.push({
      at: c.dateSigned,
      text: `${c.businessName} signed`,
      type: 'client',
    });
    (c.notes || []).forEach((n) => {
      events.push({
        at: n.updatedAt,
        text: `Note on ${c.businessName}`,
        type: 'note',
      });
    });
    (c.requests || []).forEach((r) => {
      events.push({
        at: r.dateSubmitted,
        text: `Request: ${r.title} (${c.businessName})`,
        type: 'request',
      });
    });
  });
  return events
    .filter((e) => e.at)
    .sort((a, b) => b.at.localeCompare(a.at))
    .slice(0, limit);
}

export async function exportBackup() {
  const data = await api('GET', '/api/export');
  const json = JSON.stringify(data, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const date = new Date().toISOString().slice(0, 10);
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `atlas-backup-${date}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function importBackup(file) {
  const text = await file.text();
  const parsed = JSON.parse(text);
  const clients = Array.isArray(parsed) ? parsed : (parsed.clients || []);
  const payload = { clients };
  if (parsed.calls) payload.calls = parsed.calls;
  if (parsed.reports) payload.reports = parsed.reports;
  if (parsed.generated_history) payload.generated_history = parsed.generated_history;
  if (!clients.length && !payload.calls) throw new Error('no_data');
  await api('POST', '/api/restore', payload);
  await refreshClients();
}

// ---------------------------------------------------------------------------
// Leads (Nexus engine)
// ---------------------------------------------------------------------------

export async function fetchDashboard() {
  return api('GET', '/api/dashboard');
}

export async function fetchFloridaCities() {
  return api('GET', '/api/leads/cities');
}

export async function generateLeads(body) {
  return api('POST', '/api/leads/generate', body);
}

export async function pollLeadJob(jobId) {
  return api('GET', `/api/leads/status/${jobId}`);
}

export async function fetchLeadOutcomes() {
  return api('GET', '/api/leads/outcomes');
}

export async function logLeadOutcome(data) {
  return api('POST', '/api/leads/log-outcome', data);
}

export async function convertLeadToClient(lead) {
  const result = await api('POST', '/api/leads/convert-to-client', {
    business_name: lead.name,
    phone: lead.phone,
    website: lead.website,
    score: lead.score,
    site_status: lead.site_status,
    address: lead.address,
  });
  await refreshClients();
  return result;
}

export async function fetchLeadHistory(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return api('GET', `/api/leads/history${qs ? `?${qs}` : ''}`);
}

export async function fetchLeadStats() {
  return api('GET', '/api/leads/stats');
}

export async function fetchLeadLearning() {
  return api('GET', '/api/leads/learning');
}

export async function fetchStorageStatus() {
  return api('GET', '/api/storage');
}
