/** Lightweight SVG charts for the Atlas dashboard — no external deps. */

const OUTCOME_COLORS = {
  client: 'var(--green)',
  preview: 'var(--accent)',
  callback: 'var(--blue)',
  not_interested: 'var(--red)',
  no_answer: 'var(--stripe-muted)',
};

const PIPELINE_COLORS = {
  live: 'var(--green)',
  building: 'var(--blue)',
  waiting_on_client: 'var(--amber)',
  onboarding: 'var(--accent)',
};

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s ?? '';
  return d.innerHTML;
}

function emptyChart(msg) {
  return `<div class="chart-empty">${esc(msg)}</div>`;
}

/** Donut chart — outcome breakdown. */
export function renderDonutChart(items, { title = 'Call Outcomes', centerLabel = 'calls' } = {}) {
  if (!items?.length) {
    return `<div class="chart-panel"><h3>${esc(title)}</h3>${emptyChart('Log call outcomes to see this chart.')}</div>`;
  }

  const total = items.reduce((sum, d) => sum + d.value, 0);
  const size = 160;
  const stroke = 28;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  const segments = items.map((item) => {
    const pct = item.value / total;
    const len = pct * circumference;
    const dash = `${len} ${circumference - len}`;
    const seg = `<circle class="chart-donut-seg" cx="${size / 2}" cy="${size / 2}" r="${radius}"
      fill="none" stroke="${OUTCOME_COLORS[item.key] || 'var(--accent)'}"
      stroke-width="${stroke}" stroke-dasharray="${dash}"
      stroke-dashoffset="${-offset}" transform="rotate(-90 ${size / 2} ${size / 2})" />`;
    offset += len;
    return seg;
  }).join('');

  const legend = items.map((item) => `
    <div class="chart-legend-item">
      <span class="chart-legend-swatch" style="background:${OUTCOME_COLORS[item.key] || 'var(--accent)'}"></span>
      <span class="chart-legend-label">${esc(item.label)}</span>
      <span class="chart-legend-value">${item.value}</span>
    </div>`).join('');

  return `
    <div class="chart-panel">
      <h3>${esc(title)}</h3>
      <div class="chart-donut-wrap">
        <svg class="chart-donut" viewBox="0 0 ${size} ${size}" aria-hidden="true">
          <circle cx="${size / 2}" cy="${size / 2}" r="${radius}" fill="none"
            stroke="var(--border)" stroke-width="${stroke}" />
          ${segments}
        </svg>
        <div class="chart-donut-center">
          <div class="chart-donut-total">${total}</div>
          <div class="chart-donut-sub">${esc(centerLabel)}</div>
        </div>
      </div>
      <div class="chart-legend">${legend}</div>
    </div>`;
}

/** Vertical bar chart — calls per week with client wins overlay. */
export function renderBarChart(weeks, { title = 'Calls per Week' } = {}) {
  if (!weeks?.length) {
    return `<div class="chart-panel chart-panel-wide"><h3>${esc(title)}</h3>${emptyChart('Weekly trends appear after calls are logged.')}</div>`;
  }

  const maxVal = Math.max(1, ...weeks.map((w) => w.calls));
  const chartH = 120;
  const bars = weeks.map((w) => {
    const totalH = Math.round((w.calls / maxVal) * chartH);
    const clientH = w.calls && w.clients
      ? Math.max(3, Math.round((w.clients / w.calls) * totalH))
      : 0;
    const callsH = Math.max(0, totalH - clientH);
    return `
      <div class="chart-bar-col" title="${esc(w.label)}: ${w.calls} calls, ${w.clients} clients">
        <div class="chart-bar-stack" style="height:${chartH}px">
          <div class="chart-bar chart-bar-calls" style="height:${callsH}px"></div>
          ${clientH ? `<div class="chart-bar chart-bar-clients" style="height:${clientH}px"></div>` : ''}
        </div>
        <div class="chart-bar-label">${esc(w.label)}</div>
      </div>`;
  }).join('');

  return `
    <div class="chart-panel chart-panel-wide">
      <h3>${esc(title)}</h3>
      <div class="chart-bar-meta">
        <span><span class="chart-legend-swatch chart-legend-swatch-inline" style="background:var(--accent)"></span> Calls</span>
        <span><span class="chart-legend-swatch chart-legend-swatch-inline" style="background:var(--green)"></span> Clients won</span>
      </div>
      <div class="chart-bars">${bars}</div>
    </div>`;
}

/** Horizontal bar chart — client pipeline by status. */
export function renderPipelineChart(items, { title = 'Client Pipeline' } = {}) {
  if (!items?.length) {
    return `<div class="chart-panel"><h3>${esc(title)}</h3>${emptyChart('Add clients to see pipeline breakdown.')}</div>`;
  }

  const maxVal = Math.max(1, ...items.map((d) => d.value));
  const rows = items.map((item) => {
    const pct = Math.round((item.value / maxVal) * 100);
    const color = PIPELINE_COLORS[item.key] || 'var(--accent)';
    return `
      <div class="chart-hbar-row">
        <div class="chart-hbar-label">${esc(item.label)}</div>
        <div class="chart-hbar-track">
          <div class="chart-hbar-fill" style="width:${pct}%;background:${color}"></div>
        </div>
        <div class="chart-hbar-value">${item.value}</div>
      </div>`;
  }).join('');

  return `
    <div class="chart-panel">
      <h3>${esc(title)}</h3>
      <div class="chart-hbars">${rows}</div>
    </div>`;
}

export function renderDashboardCharts(charts = {}) {
  return `
    <div class="chart-grid">
      ${renderBarChart(charts.calls_by_week)}
      ${renderDonutChart(charts.outcomes)}
      ${renderPipelineChart(charts.client_pipeline)}
    </div>`;
}
