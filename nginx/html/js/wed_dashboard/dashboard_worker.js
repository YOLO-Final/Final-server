'use strict';

/* ============================================================
   WORKER 레이아웃
   - worker API bundle을 "작업자 전용 카드 구조"로 바꾸는 렌더 함수
   - 데이터 계산은 최소화하고, 화면에서 바로 읽을 수 있는 HTML 조합에 집중한다
   ============================================================ */
function workerLayout(bundle) {
  // worker 화면은 "현재 라인 즉시 판단"이 목적이므로
  // 번들에서 필요한 조각만 꺼내 카드 단위로 바로 렌더한다.
  const noticeMessage = bundle.notice?.message || '';
  const noticeKey = bundle.notice?.key || 'worker-notice';
  const isPeriodMode = isPeriodCompareMode(bundle);
  const dayModeLabel = getRequestedDayModeLabel(bundle);
  const kpis = toArr(bundle.kpis);
  const grid = toArr(bundle.statusGrid);
  const lineTemperature = bundle.lineTemperature || null;
  const equipGrid = [...grid].slice(0, 4);
  while (equipGrid.length < 4) {
    equipGrid.push({
      id: '-',
      type: '데이터 없음',
      status: 'idle',
      opr: '-',
      ng: '-',
      detail: null,
    });
  }
  const currentLine = normalizeLineLabel(bundle.meta?.line || '');
  const queue = toArr(bundle.actionQueue);
  const queuePreview = queue.slice(0, 4);
  const notices = toArr(bundle.globalNotices);
  const noticePreview = notices.slice(0, 4);
  const hint = bundle.hint;
  const ngTypes = toArr(bundle.ngTypes);
  const total = ngTypes.reduce((s, d) => s + Number(d.count || 0), 0);

  // 설비 상태 카드는 항상 4칸 레이아웃을 유지한다.
  // 데이터가 모자란 경우에도 빈 카드로 채워 화면 밀림을 막는다.
  const equipCards = equipGrid.map(eq => {
    const rawStatus = String(eq.status || '').toLowerCase();
    const visualStatus = rawStatus;
    const cls = `eq-${visualStatus}`;
    const stCls = `status-${visualStatus}`;
    const statusText = visualStatus.toUpperCase();
    const detail = eq.detail || {};
    const abnormalReason = detail['정지사유'] || detail['대기사유'] || detail['이상사유'] || '';
    const statusMemo =
      detail['상태메모']
      || (rawStatus === 'idle' ? '대기 중' : '')
      || (rawStatus === 'maint' ? '점검 중' : '')
      || '-';
    const displayedReason =
      abnormalReason
      || (rawStatus === 'idle' ? '대기 사유 확인 필요' : '')
      || (rawStatus === 'maint' ? '점검 사유 확인 필요' : '');
    const shouldShowReason = ['idle', 'down', 'maint'].includes(rawStatus) && displayedReason;
    const tooltipRows = [
      `
        <div class="tt-row">
          <span class="tt-label">마지막 갱신</span>
          <span class="tt-val">${esc(eq.time || '-')}</span>
        </div>
      `,
      `
        <div class="tt-row">
          <span class="tt-label">상태 메모</span>
          <span class="tt-val">${esc(statusMemo)}</span>
        </div>
      `,
      shouldShowReason ? `
        <div class="tt-row">
          <span class="tt-label">사유</span>
          <span class="tt-val">${esc(displayedReason)}</span>
        </div>
      ` : '',
    ].join('');

    return `
      <div class="equip-card ${cls}">
        <div class="equip-head">
          <span class="equip-name">${esc(eq.id)}</span>
          <span class="badge ${stCls}">${statusText}</span>
        </div>

        <div class="equip-type">${esc(eq.type)}</div>

        <div class="equip-metrics mt-8">
          <span class="equip-metric-label">가동률</span>
          <span class="equip-metric-val">${esc(eq.opr)}</span>
          <span class="equip-metric-label">NG</span>
          <span class="equip-metric-val">${esc(eq.ng)}</span>
        </div>

        <div class="equip-tooltip">
          <div class="tt-title">${esc(eq.id)} 상세</div>
          ${tooltipRows}
        </div>
      </div>
    `;
  }).join('');

  const queueItems = queuePreview.map(a => `
    <div class="action-queue-item" role="group" aria-label="액션 큐 항목">
      <div class="aq-body">
        <div class="aq-title">${esc(a.target)} ${sevBadge(a.severity)}</div>
        <div class="aq-sub">${esc(a.reason)}</div>
        <div class="aq-meta">${esc(a.time)} 발생</div>
      </div>
    </div>
  `).join('');

  const noticeItems = noticePreview.map(n => `
    <div class="action-queue-item action-queue-item--notice" role="group" aria-label="공지 항목">
      <div class="aq-body">
        <div class="aq-title"><span>${esc(n.meta || '-')}</span><span class="badge badge-blue">공지</span></div>
        <div class="aq-sub">${esc(n.text || '-')}</div>
      </div>
    </div>
  `).join('');

  const pieLegend = ngTypes.map(d => `
    <div class="pie-legend-item">
      <div class="pie-dot" style="background:${d.color}"></div>
      <span>${esc(d.name)} <span class="pie-count">${d.count}건</span></span>
    </div>
  `).join('');

  const tempCurrent = Number(lineTemperature?.current);
  const tempWarning = Number(lineTemperature?.warning);
  const tempCritical = Number(lineTemperature?.critical);
  const tempSeverity =
    Number.isFinite(tempCritical) && tempCurrent >= tempCritical ? '위험'
    : Number.isFinite(tempWarning) && tempCurrent >= tempWarning ? '주의'
    : '정상';
  const tempSeverityClass =
    tempSeverity === '위험' ? 'badge-danger'
    : tempSeverity === '주의' ? 'badge-warn'
    : 'badge-green';
  const tempSummaryCards = `
    <div class="pie-summary-card">
      <div class="pie-summary-card__label">현재 온도</div>
      <div class="pie-summary-card__value">${Number.isFinite(tempCurrent) ? `${tempCurrent.toFixed(1)}°C` : '-'}</div>
      <div class="pie-summary-card__meta">${esc(lineTemperature?.line || '-')} / ${esc(String(lineTemperature?.status || '-').toUpperCase())}</div>
    </div>
    <div class="pie-summary-card">
      <div class="pie-summary-card__label">상태 신호</div>
      <div class="pie-summary-card__value"><span class="badge ${tempSeverityClass}">${tempSeverity}</span></div>
      <div class="pie-summary-card__meta">주의 ${Number.isFinite(tempWarning) ? `${tempWarning}°C` : '-'} / 위험 ${Number.isFinite(tempCritical) ? `${tempCritical}°C` : '-'}</div>
    </div>
  `;

  const hintText = hint
    ? `${esc(hint.value)}${hint.confidence != null ? ` · 신뢰도 ${Math.round(hint.confidence * 100)}%` : ''}`
    : '';

  return `
    ${renderNoticeBar(noticeMessage, noticeKey)}

    <div class="worker-kpi-grid">
      ${kpis.map(k => kpiCard(k)).join('')}
    </div>

    ${hint ? `
      <div class="hint-banner ${hint.severity === 'warn' ? 'warn' : ''}">
        <span class="hint-tag">${hint.severity === 'warn' ? 'QA 알림' : 'ML 힌트'}</span>
        <span>${hintText}</span>
      </div>
    ` : ''}

    ${periodComparePanel(bundle, '작업자 기간 비교')}

    <div class="layout-split">
      <div class="layout-stack">
        <div class="card">
          <div class="card-header">
            <span class="card-title">라인 × 설비 상태</span>
            <span class="badge badge-green">내 라인</span>
          </div>
          <div class="equip-grid">${equipCards}</div>
        </div>

        <div class="worker-analysis-grid">
          <div class="card">
            <div class="card-header">
              <span class="card-title">${isPeriodMode ? '기간별 NG 추세' : `${dayModeLabel} NG 추세`}</span>
              <span class="badge badge-danger">${isPeriodMode ? '일별 기준' : `${dayModeLabel} 기준`}</span>
            </div>
            <div class="chart-wrap chart-h-200">
              <canvas id="workerNgSparkline"></canvas>
            </div>
          </div>

          <div class="card worker-ngtypes-card">
            <div class="card-header">
              <span class="card-title">NG 유형 분석 (6종)</span>
              <span class="badge badge-danger">총 ${total}건</span>
            </div>

            <div class="pie-wrap">
              <div class="pie-main">
                <div class="pie-box">
                  <canvas id="workerNgPie"></canvas>
                  <div class="pie-center">
                    <span class="pie-total">${total}</span>
                    <span class="pie-unit-text">건</span>
                  </div>
                </div>

                <div class="pie-legend pie-grow">
                  ${pieLegend}
                </div>
              </div>
            </div>
          </div>

          <div class="card worker-temp-card">
            <div class="card-header">
              <span class="card-title">온도 상태</span>
              <span class="badge ${tempSeverityClass}">${tempSeverity}</span>
            </div>

            <div class="pie-summary pie-summary--standalone">
              ${tempSummaryCards}
            </div>
          </div>
        </div>

        ${eventCard(
          isPeriodMode ? `기간 이벤트 — ${esc(currentLine || '-')}` : `최근 이벤트 — ${esc(currentLine || '-')}`,
          getRequestedDayModeLabel(bundle),
          bundle.events
        )}
      </div>

      <div class="layout-stack sticky-card worker-side-stack">
        <div class="card queue-card">
          <div class="card-header">
            <span class="card-title">액션 큐</span>
            <div style="display:flex;align-items:center;gap:8px;">
              <span class="badge badge-danger">${queue.length}건</span>
            </div>
          </div>
          ${queueItems || '<p class="empty-msg">조치 항목 없음</p>'}
        </div>

        <div class="card queue-card queue-card--notice">
          <div class="card-header">
            <span class="card-title">공지</span>
            <div style="display:flex;align-items:center;gap:8px;">
              <span class="badge badge-blue">${notices.length}건</span>
            </div>
          </div>
          ${noticeItems || '<p class="empty-msg">공지 없음</p>'}
        </div>
      </div>
    </div>
  `;
}
