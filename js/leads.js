/** Atlas Leads — generation, outcomes, convert to client. */

import {
  generateLeads,
  pollLeadJob,
  fetchLeadOutcomes,
  logLeadOutcome,
  convertLeadToClient,
  fetchFloridaCities,
  isDemoMode,
} from './store.js';
import { getDemoLeads } from './demo.js';
import { withIcon } from './icons.js';

const OUTCOMES = [
  { value: '', label: 'Not Called' },
  { value: 'no_answer', label: 'No Answer' },
  { value: 'not_interested', label: 'Not Interested' },
  { value: 'callback', label: 'Call Back' },
  { value: 'preview', label: 'Preview' },
  { value: 'client', label: 'Client' },
];

const SITE_LABELS = {
  dead: 'Dead',
  none: 'No Website',
  working: 'Working',
};

let _leads = [];
let _outcomesByPhone = {};
let _pollTimer = null;

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s ?? '';
  return d.innerHTML;
}

function phoneKey(phone) {
  const d = (phone || '').replace(/\D/g, '');
  return d.length >= 10 ? d.slice(-10) : d;
}

function siteBadge(status) {
  const label = SITE_LABELS[status] || status || '—';
  const cls = status === 'dead' ? 'badge-waiting' : status === 'none' ? 'badge-submitted' : 'badge-complete';
  return `<span class="badge badge-${cls}">${esc(label)}</span>`;
}

function scoreCell(lead) {
  const base = lead.score ?? '—';
  const delta = lead.learn_delta;
  if (delta) {
    const sign = delta > 0 ? '+' : '';
    return `${base} <span class="muted" style="font-size:0.8rem">(${sign}${delta})</span>`;
  }
  return `${base}`;
}

function outcomeSelect(lead, selected) {
  const opts = OUTCOMES.map((o) =>
    `<option value="${o.value}" ${o.value === selected ? 'selected' : ''}>${esc(o.label)}</option>`
  ).join('');
  return `<select class="lead-outcome" data-phone="${esc(lead.phone)}">${opts}</select>`;
}

function leadRow(lead, outcome) {
  const called = outcome && outcome !== '';
  return `
    <tr class="${called ? 'lead-called' : ''}">
      <td><strong>${esc(lead.name)}</strong></td>
      <td>${esc(lead.city || '—')}</td>
      <td><a href="tel:${esc(lead.phone)}">${esc(lead.phone)}</a></td>
      <td>${siteBadge(lead.site_status)}</td>
      <td>${scoreCell(lead)}</td>
      <td class="muted" style="max-width:200px;font-size:0.8rem">${esc(lead.reason || '')}</td>
      <td>${outcomeSelect(lead, outcome)}</td>
      <td>
        <button class="btn btn-primary btn-sm" data-convert="${esc(lead.phone)}">${withIcon('userPlus', 'Convert')}</button>
      </td>
    </tr>`;
}

function leadCard(lead, outcome) {
  const called = outcome && outcome !== '';
  return `
    <div class="list-card lead-card ${called ? 'lead-called' : ''}">
      <div class="list-card-head">
        <strong>${esc(lead.name)}</strong>
        ${siteBadge(lead.site_status)}
      </div>
      <div class="list-card-meta">${esc(lead.city || '—')} · Score ${scoreCell(lead)}</div>
      <div class="list-card-meta"><a href="tel:${esc(lead.phone)}">${esc(lead.phone)}</a></div>
      ${lead.reason ? `<div class="lead-reason">${esc(lead.reason)}</div>` : ''}
      ${lead.opener ? `<div class="lead-opener">"${esc(lead.opener)}"</div>` : ''}
      <div class="lead-actions">
        ${outcomeSelect(lead, outcome)}
        <button class="btn btn-primary btn-sm" data-convert="${esc(lead.phone)}">${withIcon('userPlus', 'Convert to Client')}</button>
      </div>
    </div>`;
}

function getOutcomeForLead(lead) {
  const key = phoneKey(lead.phone);
  const rec = _outcomesByPhone[key];
  return rec?.outcome || '';
}

export function renderLeadsPage(cities = []) {
  const cityOpts = cities.map((c) => `<option value="${esc(c)}">${esc(c)}</option>`).join('');
  const rows = _leads.length
    ? _leads.map((l) => leadRow(l, getOutcomeForLead(l))).join('')
    : '';
  const cards = _leads.length
    ? _leads.map((l) => leadCard(l, getOutcomeForLead(l))).join('')
    : '';

  return `
    <div class="page-header">
      <h1>Leads</h1>
      <p>Generate call lists, log outcomes, convert wins to clients</p>
    </div>

    <div class="panel leads-controls">
      <div class="leads-form">
        <div class="field">
          <label>Search mode</label>
          <select id="lead-mode">
            <option value="random">Whole Florida</option>
            <option value="city">Pick a city</option>
          </select>
        </div>
        <div class="field" id="lead-city-wrap" style="display:none">
          <label>City</label>
          <select id="lead-city"><option value="">Select city…</option>${cityOpts}</select>
        </div>
        <div class="field">
          <label>Industry</label>
          <select id="lead-industry">
            <option value="hvac">HVAC</option>
          </select>
        </div>
        <div class="field">
          <label>Website filter</label>
          <select id="lead-site-filter">
            <option value="all">All opportunities</option>
            <option value="dead">Dead website only</option>
            <option value="none">No website only</option>
          </select>
        </div>
        <div class="field">
          <label>Count</label>
          <select id="lead-count">
            <option value="10">10</option>
            <option value="15">15</option>
            <option value="20" selected>20</option>
            <option value="30">30</option>
          </select>
        </div>
        <button class="btn btn-primary" id="btn-generate-leads" type="button">${withIcon('zap', 'Generate Leads')}</button>
      </div>
      <div id="lead-status" class="lead-status muted"></div>
    </div>

    <div class="panel" id="leads-results">
      ${_leads.length ? `
        <div class="btn-row" style="margin-bottom:12px">
          <span style="color:var(--muted);font-size:0.85rem">${_leads.length} leads ready</span>
        </div>
        <table class="desktop-table leads-table">
          <thead>
            <tr>
              <th>Business</th><th>City</th><th>Phone</th><th>Website</th>
              <th>Score</th><th>Reason</th><th>Outcome</th><th></th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
        <div class="mobile-list">${cards}</div>
      ` : '<div class="empty">Generate a call list to get started.</div>'}
    </div>`;
}

async function refreshOutcomes() {
  const data = await fetchLeadOutcomes();
  _outcomesByPhone = data.by_phone || {};
}

function leadByPhone(phone) {
  const key = phoneKey(phone);
  return _leads.find((l) => phoneKey(l.phone) === key);
}

async function onOutcomeChange(select) {
  const phone = select.dataset.phone;
  const outcome = select.value;
  const lead = leadByPhone(phone);
  if (!lead || !outcome) return;

  select.disabled = true;
  try {
    await logLeadOutcome({
      business_name: lead.name,
      phone: lead.phone,
      score: lead.score,
      site_status: lead.site_status,
      address: lead.address,
      outcome,
    });
    await refreshOutcomes();
    select.closest('tr, .lead-card')?.classList.add('lead-called');
  } catch (err) {
    if (err.message === 'demo_mode') {
      alert('Preview mode — turn off in Settings to log real outcomes.');
    } else {
      alert('Could not save outcome.');
    }
    select.value = getOutcomeForLead(lead);
  } finally {
    select.disabled = false;
  }
}

async function onConvert(phone) {
  const lead = leadByPhone(phone);
  if (!lead) return;
  if (!confirm(`Create client "${lead.name}" and mark outcome as Client?`)) return;
  try {
    await convertLeadToClient(lead);
    await refreshOutcomes();
    const sel = document.querySelector(`.lead-outcome[data-phone="${CSS.escape(phone)}"]`);
    if (sel) sel.value = 'client';
    alert(`"${lead.name}" added to Clients.`);
  } catch (err) {
    if (err.message === 'demo_mode') {
      alert('Preview mode — turn off in Settings to convert leads.');
    } else {
      alert('Could not convert lead.');
    }
  }
}

export async function bindLeadsPage(onRefresh) {
  const modeEl = document.getElementById('lead-mode');
  const cityWrap = document.getElementById('lead-city-wrap');
  modeEl?.addEventListener('change', () => {
    if (cityWrap) cityWrap.style.display = modeEl.value === 'city' ? '' : 'none';
  });

  document.getElementById('btn-generate-leads')?.addEventListener('click', async () => {
    const btn = document.getElementById('btn-generate-leads');
    const status = document.getElementById('lead-status');
    if (!btn || !status) return;

    const mode = document.getElementById('lead-mode')?.value || 'random';
    const city = document.getElementById('lead-city')?.value || '';
    if (mode === 'city' && !city) {
      alert('Pick a city first.');
      return;
    }

    btn.disabled = true;
    status.textContent = 'Starting search…';

    try {
      const exclude = JSON.parse(localStorage.getItem('atlas_lead_phones') || '[]');
      const { job_id } = await generateLeads({
        mode,
        city,
        count: parseInt(document.getElementById('lead-count')?.value || '20', 10),
        site_filter: document.getElementById('lead-site-filter')?.value || 'all',
        industry: document.getElementById('lead-industry')?.value || 'hvac',
        exclude_phones: exclude,
      });

      if (_pollTimer) clearInterval(_pollTimer);
      _pollTimer = setInterval(async () => {
        try {
          const job = await pollLeadJob(job_id);
          status.textContent = job.message || job.status;
          if (job.status === 'done') {
            clearInterval(_pollTimer);
            _pollTimer = null;
            _leads = job.leads || [];
            const keys = new Set(exclude.map(phoneKey));
            _leads.forEach((l) => keys.add(phoneKey(l.phone)));
            localStorage.setItem('atlas_lead_phones', JSON.stringify([...keys]));
            await refreshOutcomes();
            btn.disabled = false;
            onRefresh();
          } else if (job.status === 'error') {
            clearInterval(_pollTimer);
            _pollTimer = null;
            status.textContent = job.error || 'Generation failed';
            btn.disabled = false;
          }
        } catch {
          clearInterval(_pollTimer);
          _pollTimer = null;
          status.textContent = 'Lost connection while generating.';
          btn.disabled = false;
        }
      }, 2000);
    } catch (err) {
      if (err.message === 'demo_mode') {
        status.textContent = 'Preview mode — turn off in Settings to generate leads.';
      } else {
        status.textContent = err.message || 'Could not start generation.';
      }
      btn.disabled = false;
    }
  });

  document.querySelectorAll('.lead-outcome').forEach((sel) => {
    sel.addEventListener('change', () => onOutcomeChange(sel));
  });

  document.querySelectorAll('[data-convert]').forEach((btn) => {
    btn.addEventListener('click', () => onConvert(btn.dataset.convert));
  });
}

export async function initLeadsPageData() {
  let cities = [];
  try {
    cities = await fetchFloridaCities();
  } catch { /* ignore */ }

  if (isDemoMode()) {
    _leads = getDemoLeads();
    try {
      await refreshOutcomes();
    } catch { /* ignore */ }
    return cities;
  }

  _leads = [];
  try {
    await refreshOutcomes();
  } catch { /* ignore */ }
  return cities;
}

export function clearLeadsSession() {
  _leads = [];
}
