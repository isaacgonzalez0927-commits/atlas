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
  return sessionStorage.getItem(AUTH_KEY) || '';
}

export function setAuthCode(code) {
  sessionStorage.setItem(AUTH_KEY, code);
}

export function clearAuthCode() {
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
  return api('GET', '/api/health');
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
