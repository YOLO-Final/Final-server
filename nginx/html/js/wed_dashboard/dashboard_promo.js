'use strict';

/* ============================================================
   PROMO 레이아웃
   - 현장 공용 송출 화면 전용 렌더 함수
   - 발표/전광판처럼 멀리서 읽는 시나리오를 기준으로
     정보 밀도보다 한눈에 읽히는 구조를 우선한다
   ============================================================ */
function promoLayout(bundle) {
  const isPeriodMode = isPeriodCompareMode(bundle);
  const kpis = toArr(bundle.kpis);
  const weekRows = toArr(bundle.promoWeekProduction);
  const lines = toArr(bundle.promoLines);
  const defects = toArr(bundle.promoTopDefects);
  const alarms = toArr(bundle.promoCurrentAlarms);
  const compare = toArr(bundle.promoMonthlyCompare);
  const ticker = toArr(bundle.promoTicker);
  const defectTotal = defects.reduce((sum, item) => sum + Number(item.count || 0), 0);
  const unresolvedAlarmCount = alarms.length;
  const alarmBadgeClass = unresolvedAlarmCount > 0 ? 'badge-danger' : 'badge-green';

  const lineItems = lines.map((row) => {
    const toneClass = row.status === 'run' ? 'is-run' : row.status === 'down' ? 'is-down' : 'is-warn';
    const badgeClass = row.status === 'run' ? 'badge-green' : row.status === 'down' ? 'badge-danger' : 'badge-warn';
    const oeeColorClass = row.oeeStatus === 'ok' ? 'is-good' : row.oeeStatus === 'critical' ? 'is-danger' : 'is-warn';
    const subMetric = row.stopTime
      ? `<div class="promo-line-metric"><span class="promo-line-metric__label">정지</span><span class="promo-line-metric__val promo-line-metric__val--danger">${esc(row.stopTime)}</span></div>`
      : `<div class="promo-line-metric"><span class="promo-line-metric__label">불량률</span><span class="promo-line-metric__val ${row.defectRate === '1.8%' ? 'promo-line-metric__val--good' : row.defectRate === '4.8%' ? 'promo-line-metric__val--danger' : ''}">${esc(row.defectRate || '-')}</span></div>`;

    return `
      <div class="promo-line-item ${toneClass}">
        <div class="promo-line-dot ${toneClass}"></div>
        <div class="promo-line-name">${esc(row.line)}</div>
        <span class="badge ${badgeClass}">${esc(row.badge)}</span>
        <div class="promo-line-metrics">
          <div class="promo-line-metric"><span class="promo-line-metric__label">생산</span><span class="promo-line-metric__val">${fmtNum(row.output)}</span></div>
          ${subMetric}
        </div>
        <div class="promo-line-oee">
          <div class="promo-line-oee__track"><div class="promo-line-oee__fill ${oeeColorClass}" style="width:${Math.max(0, Math.min(Number(row.oee) || 0, 100))}%"></div></div>
          <div class="promo-line-oee__label ${oeeColorClass}">OEE ${row.oee}%</div>
        </div>
      </div>
    `;
  }).join('');

  const defectRows = defects.map((row) => {
    const total = defects.reduce((sum, item) => sum + Number(item.count || 0), 0) || 1;
    const width = Math.round((Number(row.count || 0) / total) * 100);
    return `
      <div class="promo-qual-row">
        <span class="promo-qual-name">${esc(row.name)}</span>
        <div class="promo-qual-bar-wrap"><div class="promo-qual-bar" style="width:${width}%;background:${row.color}"></div></div>
        <span class="promo-qual-count">${row.count}건</span>
      </div>
    `;
  }).join('');

  const alarmRows = alarms.map((row) => {
    const sevClassName = row.severity === 'critical' ? 'crit' : 'warn';
    const sevBadgeHtml = row.severity === 'critical'
      ? '<span class="promo-alarm-sev is-critical">CRITICAL</span>'
      : '<span class="promo-alarm-sev is-warning">WARNING</span>';
    return `
      <div class="promo-alarm-item ${sevClassName}">
        ${sevBadgeHtml}
        <span class="promo-alarm-line">${esc(row.line)}</span>
        <span class="promo-alarm-msg">${esc(row.message)}</span>
        <span class="promo-alarm-time">${esc(row.time)}</span>
      </div>
    `;
  }).join('');

  const alarmContent = alarmRows || `
    <div class="promo-alarm-empty">
      <div class="promo-alarm-empty__value">0건</div>
      <div class="promo-alarm-empty__label">현재 미해결 알람 없음</div>
      <div class="promo-alarm-empty__meta">운영 상태가 안정적으로 유지되고 있습니다.</div>
    </div>
  `;

  const compareCards = compare.map((row) => `
    <div class="promo-compare-card">
      <div class="promo-compare-card__label">${esc(row.label)}</div>
      <div class="promo-compare-card__value ${row.tone === 'up' && row.label !== '불량률' ? 'is-good' : row.tone === 'down' ? 'is-danger' : ''}">${esc(row.value)}</div>
      <div class="promo-compare-card__diff ${row.tone === 'up' && row.label !== '불량률' ? 'is-good' : row.tone === 'down' ? 'is-danger' : ''}">${esc(row.diff)}</div>
    </div>
  `).join('');

  const tickerText = ticker.length
    ? `✦ ${ticker.join('    ✦ ')}`
    : '운영 공지 없음';
  const compareBadgeLabel = getPromoCompareBadgeLabel(bundle);
  const dayModeLabel = getRequestedDayModeLabel(bundle);

  return `
    <div class="promo-broadcast">
      <div class="promo-kpi-grid">
        ${kpis.map(k => kpiCard(k)).join('')}
      </div>

      ${periodComparePanel(bundle, '공용 송출 기간 비교')}

      <div class="promo-mid-grid">
        <div class="card promo-card">
          <div class="card-header">
            <span class="card-title">${isPeriodMode ? '선택 기간 일별 생산량' : '이번 주 일별 생산량'}</span>
            <span class="badge badge-blue">${isPeriodMode ? '기간' : '주간'}</span>
          </div>
          <div class="chart-wrap promo-week-chart">
            <canvas id="promoWeekChart"></canvas>
          </div>
        </div>

        <div class="card promo-card">
          <div class="card-header">
            <span class="card-title">라인별 가동 현황</span>
            <span class="badge badge-green">실시간</span>
          </div>
          <div class="promo-line-list">
            ${lineItems}
          </div>
        </div>
      </div>

      <div class="promo-bottom-grid">
        <div class="card promo-card">
          <div class="card-header">
            <span class="card-title">불량 유형 Top 5</span>
            <span class="badge badge-danger">${isPeriodMode ? `기간 총 ${fmtNum(defectTotal)}건` : `${dayModeLabel} 총 ${fmtNum(defectTotal)}건`}</span>
          </div>
          <div class="promo-qual-list">${defectRows}</div>
        </div>

        <div class="card promo-card">
          <div class="card-header">
            <span class="card-title">현재 알람</span>
            <span class="badge ${alarmBadgeClass}">미해결 ${unresolvedAlarmCount}건</span>
          </div>
          <div class="promo-alarm-list">${alarmContent}</div>
        </div>

        <div class="card promo-card">
          <div class="card-header">
            <span class="card-title">${isPeriodMode ? '기간 비교' : '전월 대비'}</span>
            <span class="badge badge-muted">${esc(compareBadgeLabel)}</span>
          </div>
          <div class="promo-compare-grid">${compareCards}</div>
        </div>
      </div>

      <div class="promo-ticker">
        <div class="promo-ticker__tag">공지</div>
        <div class="promo-ticker__inner">
          <div class="promo-ticker__text">${esc(tickerText)}</div>
        </div>
      </div>
    </div>
  `;
}
