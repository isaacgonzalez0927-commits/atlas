/** Atlas V0 — localStorage data layer (Ascend client OS). */

const STORAGE_KEY = 'ascend_atlas_data';

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

function uid() {
  return crypto.randomUUID?.() || `id-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function emptyAssets() {
  const a = {};
  ASSET_KEYS.forEach(({ key }) => { a[key] = false; });
  return a;
}

export function loadClients() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch (_) { /* ignore */ }
  return [];
}

export function saveClients(clients) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(clients));
}

export function getClient(id) {
  return loadClients().find((c) => c.id === id) || null;
}

export function upsertClient(data) {
  const clients = loadClients();
  if (data.id) {
    const i = clients.findIndex((c) => c.id === data.id);
    if (i >= 0) {
      clients[i] = { ...clients[i], ...data };
      saveClients(clients);
      return clients[i];
    }
  }
  const client = {
    id: uid(),
    businessName: '',
    contactName: '',
    email: '',
    phone: '',
    website: '',
    status: 'onboarding',
    dateSigned: new Date().toISOString().slice(0, 10),
    assets: emptyAssets(),
    requests: [],
    notes: [],
    ...data,
  };
  clients.push(client);
  saveClients(clients);
  return client;
}

export function deleteClient(id) {
  saveClients(loadClients().filter((c) => c.id !== id));
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

export function addRequest(clientId, req) {
  const clients = loadClients();
  const c = clients.find((x) => x.id === clientId);
  if (!c) return null;
  const item = {
    id: uid(),
    title: req.title || '',
    description: req.description || '',
    status: req.status || 'submitted',
    dateSubmitted: new Date().toISOString().slice(0, 10),
  };
  c.requests = c.requests || [];
  c.requests.push(item);
  saveClients(clients);
  return item;
}

export function updateRequest(clientId, requestId, patch) {
  const clients = loadClients();
  const c = clients.find((x) => x.id === clientId);
  if (!c) return;
  const r = (c.requests || []).find((x) => x.id === requestId);
  if (r) Object.assign(r, patch);
  saveClients(clients);
}

export function addNote(clientId, text) {
  const clients = loadClients();
  const c = clients.find((x) => x.id === clientId);
  if (!c) return null;
  const now = new Date().toISOString();
  const note = { id: uid(), text, createdAt: now, updatedAt: now };
  c.notes = c.notes || [];
  c.notes.push(note);
  saveClients(clients);
  return note;
}

export function updateNote(clientId, noteId, text) {
  const clients = loadClients();
  const c = clients.find((x) => x.id === clientId);
  if (!c) return;
  const n = (c.notes || []).find((x) => x.id === noteId);
  if (n) {
    n.text = text;
    n.updatedAt = new Date().toISOString();
  }
  saveClients(clients);
}

export function updateAssets(clientId, assets) {
  const clients = loadClients();
  const c = clients.find((x) => x.id === clientId);
  if (c) {
    c.assets = { ...c.assets, ...assets };
    saveClients(clients);
  }
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
