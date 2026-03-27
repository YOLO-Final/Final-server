'use strict';

/* ============================================================
   MANAGER 레이아웃
   - manager API bundle을 운영 리스크/OEE/즉시 조치 중심 관리자 화면으로 변환한다
   - 관리자 탭은 "라인 간 비교"와 "조치 우선순위"가 핵심이므로
     비교형 카드와 요약 리스트 비중이 크다
   ============================================================ */
function managerLayout(bundle) {
  // 관리자 화면은 기간 모드 여부에 따라 제목/배지 표현만 바꾸고
  // 실제 카드 구조는 최대한 동일하게 유지한다.
  const noticeMessage = bundle.notice?.message || '';
  const noticeKey = bundle.notice?.key || 'manager-notice';
  const kpis = toArr(bundle.kpis);
  const risk = bundle.riskOverall;
  const lines = toArr(bundle.riskLines);
  const pending = toArr(bundle.pendingActions);
  const alarms = toArr(bundle.activeAlarms);
  const alarmPreview = alarms.slice(0, 5);
  const lineOee = toArr(bundle.managerLineOee);
  const isPeriodMode = isPeriodCompareMode(bundle);
  const dayModeLabel = getRequestedDayModeLabel(bundle);
  const currentLine = normalizeLineLabel(bundle.meta?.line || '');
  const eventTitle = currentLine
    ? (isPeriodMode ? `기간 이벤트 — ${esc(currentLine)}` : `최근 이벤트 — ${esc(currentLine)}`)
    : (isPeriodMode ? '기간 이벤트 — 전체 라인' : '최근 이벤트 — 전체 라인');

  const riskItems = lines.map(l => {
    const score = Math.min(100, Math.max(0, l.riskScore));
    return `
      <button class="risk-item" type="button">
        <div class="risk-item__body">
          <span class="risk-summary"><strong class="risk-line-inline">${esc(l.lineId)}</strong> <span class="risk-summary-sep">·</span> ${esc(l.summary)}</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px">
          ${sevBadge(l.severity)}
          <span class="risk-score">R${score}</span>
        </div>
      </button>
    `;
  }).join('');

  const actionItems = pending.map(a => `
    <div class="action-queue-item" role="group" aria-label="즉시 조치 항목">
      <div class="aq-body">
        <div class="manager-action-head">
          <span class="aq-num">${a.priority}</span>
          <span class="manager-action-title">${esc(a.title)}</span>
          <span class="aq-count-inline">${a.count}건</span>
        </div>
        <div class="aq-sub manager-action-sub">${esc(a.summary)}</div>
      </div>
    </div>
  `).join('');

  const alarmRows = alarmPreview.map(a => `
    <tr>
      <td>${sevBadge(a.severity)}</td>
      <td style="font-family:var(--mono);font-size:11px;color:var(--accent)">${esc(a.alarmId)}</td>
      <td>${esc(a.line)}</td>
      <td>${esc(a.equip)}</td>
      <td><span class="ack-${a.ack}">${a.ack.toUpperCase()}</span></td>
      <td style="font-family:var(--mono);font-size:11px">${esc(a.time)}</td>
    </tr>
  `).join('');

  const lineCards = lines.map(l => {
    const score = Math.min(100, Math.max(0, l.riskScore));
    const fillCls = l.severity === 'critical' ? 'crit' : l.severity === 'warning' ? 'warn' : 'ok';

    return `
      <button class="line-risk-card" type="button">
        <div class="line-risk-head">
          <span class="line-risk-id">${esc(l.lineId)}</span>
          <span class="line-risk-summary">${esc(l.summary)}</span>
          <span class="line-risk-score">R${score}</span>
        </div>
        <div class="line-risk-bar">
          <div class="line-risk-fill ${fillCls}" style="width:${score}%"></div>
        </div>
      </button>
    `;
  }).join('');

  const managerOeeItems = lineOee.map((row) => {
    // 라인별 OEE는 목표선(target)과 현재값(actual)을 같이 보여줘야 하므로
    // fill bar와 target marker를 한 항목 안에서 같이 그린다.
    const actual = Number(row.actual) || 0;
    const target = Number(row.target) || 85;
    const fillClass = actual >= target ? 'is-good' : actual >= 70 ? 'is-warn' : 'is-danger';
    return `
      <div class="manager-oee-item">
        <span class="manager-oee-item__label">${esc(row.line)}</span>
        <div class="manager-oee-item__track">
          <div class="manager-oee-item__fill ${fillClass}" style="width:${Math.max(0, Math.min(actual, 100))}%"></div>
          <div class="manager-oee-item__target" style="left:${Math.max(0, Math.min(target, 100))}%"></div>
        </div>
        <span class="manager-oee-item__value">${actual}%</span>
      </div>
    `;
  }).join('');

  return `
    ${renderNoticeBar(noticeMessage, noticeKey)}

    <div class="manager-kpi-grid">
      ${kpis.map(k => kpiCard(k)).join('')}
    </div>

    ${periodComparePanel(bundle, '관리자 기간 비교')}

    <div class="manager-section-label">차트 분석</div>

    <div class="grid-3 manager-chart-grid">
      <div class="card manager-chart-card">
        <div class="card-header">
          <span class="card-title">라인별 OEE</span>
          <span class="badge badge-info">목표 85%</span>
        </div>
        <div class="manager-oee-list">
          ${managerOeeItems || '<p class="empty-msg">라인 OEE 데이터 없음</p>'}
        </div>
      </div>

      <div class="card manager-chart-card">
        <div class="card-header">
          <span class="card-title">${isPeriodMode ? '기간별 생산량' : '시간대별 생산량'}</span>
          <span class="badge badge-soft">${isPeriodMode ? '일별 계획 vs 실적' : '계획 vs 실적'}</span>
        </div>
        <div class="chart-wrap manager-chart-area">
          <canvas id="managerProductionChart"></canvas>
        </div>
      </div>

      <div class="card manager-chart-card">
        <div class="card-header">
          <span class="card-title">${isPeriodMode ? '기간별 불량률 추세' : '전체 불량률 추세'}</span>
          <span class="badge badge-danger">임계 4.0%</span>
        </div>
        <div class="chart-wrap manager-chart-area">
          <canvas id="managerDefectChart"></canvas>
        </div>
      </div>
    </div>

    <div class="manager-section-label">운영 현황</div>

    <div class="grid-3 manager-ops-grid">
      <div class="card">
        <div class="card-header">
          <span class="card-title manager-card-title-nowrap">운영 리스크 현황</span>
        </div>

        ${risk ? `
          <div class="risk-overall">
            ${sevBadge(risk.severity)}
            <span style="font-size:12px">${esc(risk.reason)}</span>
          </div>
        ` : ''}

        ${riskItems}
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title manager-card-title-nowrap">즉시 조치 Top 3</span>
        </div>
        ${actionItems ? `<div class="manager-action-grid">${actionItems}</div>` : '<p class="empty-msg">조치 없음</p>'}
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">미해결 알람</span>
          ${alarms.length > 5 ? `<button class="text-link" type="button" onclick="openManagerAlarmModal()">전체보기</button>` : ''}
        </div>
        <div class="manager-alarm-table-wrap">
          <table class="alarm-table">
            <thead>
              <tr>
                <th>심각도</th>
                <th>알람ID</th>
                <th>라인</th>
                <th>설비</th>
                <th>ACK</th>
                <th>시각</th>
              </tr>
            </thead>
            <tbody>${alarmRows || '<tr><td colspan="6" class="empty-msg">미해결 알람 없음</td></tr>'}</tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <span class="card-title">라인별 리스크 우선순위</span>
      </div>
      <div class="line-risk-grid">${lineCards}</div>
    </div>

    ${eventCard(eventTitle, dayModeLabel, bundle.events)}
  `;
}
