'use strict';

function kpiStatusClass(status) {
  if (status === 'critical') return 'status-crit';
  if (status === 'warning') return 'status-warn';
  return 'status-ok';
}

function kpiStatusBadge(status) {
  if (status === 'critical') return `<span class="sev sev-critical">위험</span>`;
  if (status === 'warning') return `<span class="sev sev-warning">주의</span>`;
  return `<span class="sev sev-ok">정상</span>`;
}

function kpiValueColor(status) {
  if (status === 'critical') return 'color:var(--danger)';
  if (status === 'warning') return 'color:var(--warn)';
  return '';
}

function kpiCard(kpi) {
  if (!kpi) return '';

  const cls = kpiStatusClass(kpi.status);
  const pct = kpi.target ? Math.min(100, Math.round((kpi.value / kpi.target) * 100)) : null;

  return `
    <div class="kpi-card ${cls}">
      <div class="kpi-label">
        <span class="kpi-label-main">${esc(kpi.label)}</span>
        ${kpi.meta ? `<span class="meta-tag meta-${kpi.meta.split('/')[0]}">${esc(kpi.meta)}</span>` : ''}
      </div>

      <div class="kpi-value-row">
        <span class="kpi-value" style="${kpiValueColor(kpi.status)}">${fmtNum(kpi.value)}</span>
        <span class="kpi-unit">${esc(kpi.unit)}</span>
      </div>

      ${pct != null ? `
        <div class="kpi-progress">
          <div class="kpi-progress-fill" style="width:${pct}%"></div>
        </div>
        <div class="kpi-progress-labels">
          <span>목표 ${fmtNum(kpi.target)}</span>
          <span>${pct}%</span>
        </div>
      ` : `
        <div style="margin-top:4px;">
          ${kpiStatusBadge(kpi.status)}
        </div>
      `}

    </div>
  `;
}
