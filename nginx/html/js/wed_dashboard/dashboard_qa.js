'use strict';

/* ============================================================
   QA 레이아웃
   - qa API bundle을 품질관리 화면 카드/목록/상세 트리거로 변환한다
   - 추세 비교, 재검 우선순위, 품질 이슈 요약이 핵심 축이다
   ============================================================ */
function qaLayout(bundle) {
  // 품질 화면은 "이상 신호를 빨리 읽고 상세로 내려가는 흐름"이 중요하므로
  // 카드형 요약 + 상세 모달 진입 요소를 한 번에 만든다.
  const noticeMessage = bundle.notice?.message || '';
  const noticeKey = bundle.notice?.key || 'qa-notice';
  const isPeriodMode = isPeriodCompareMode(bundle);
  const dayModeLabel = getRequestedDayModeLabel(bundle);
  const currentLine = normalizeLineLabel(bundle.meta?.line || '');
  const eventTitle = currentLine
    ? (isPeriodMode ? `기간 이벤트 — ${esc(currentLine)}` : `최근 이벤트 — ${esc(currentLine)}`)
    : (isPeriodMode ? '기간 이벤트 — 품질관리' : '최근 이벤트 — 품질관리');
  const kpis = toArr(bundle.kpis);
  const defects = toArr(bundle.topDefects);
  const recheck = toArr(bundle.recheckQueue);
  const issues = toArr(bundle.issues);
  const trend = toArr(bundle.defectTrend);
  const hint = bundle.hint;

  const total = defects.reduce((s, d) => s + Number(d.count || 0), 0);

  // 재검 목록은 카드 우측 스택에서 먼저 노출하므로
  // preview 개수만 잘라서 렌더한다.
  const recheckPreview = recheck.slice(0, 4);
  const recheckItems = recheckPreview.map(r => `
    <button class="recheck-item" type="button">
      <div class="recheck-tooltip">
        <div class="tt-title">${esc(r.lotId)}</div>
        <div class="tt-row"><span class="tt-label">불량 유형</span><span class="tt-val">${esc(r.defectClass)}</span></div>
        <div class="tt-row"><span class="tt-label">불량 수</span><span class="tt-val">${r.count}건</span></div>
        <div class="tt-row"><span class="tt-label">원인</span><span class="tt-val">${esc(r.cause)}</span></div>
        <div class="tt-row"><span class="tt-label">우선순위</span><span class="tt-val">${esc(r.priority)}</span></div>
      </div>

      <div class="recheck-lot">
        <span>${esc(r.lotId)}</span>
        ${sevBadge(r.severity)}
      </div>

      <div class="recheck-defect">${esc(r.defectClass)} — ${r.count}건</div>
      <div class="recheck-meta">${esc(r.queuedAt)} 등록</div>
    </button>
  `).join('');

  const issueItems = issues.map(iss => `
    <div class="qa-cause-item" role="group" aria-label="품질 이슈 항목">
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:2px">
        ${sevBadge(iss.severity)}
        <span style="font-size:12px;font-weight:600">${esc(iss.title)}</span>
      </div>
      <div style="font-size:11px;color:var(--muted)">${esc(iss.time)} · ${esc(iss.id)}</div>
    </div>
  `).join('');

  // 추세 요약 카드는 단순히 차트만 보여주지 않고
  // 현재값 / 이전 대비 / 평균 대비 / 임계 여유폭을 같이 계산해 요약한다.
  const latest = trend.length ? trend[trend.length - 1].actual : null;
  const latestTime = trend.length ? trend[trend.length - 1].time : null;
  const prev = trend.length >= 2 ? trend[trend.length - 2].actual : null;
  const prevTime = trend.length >= 2 ? trend[trend.length - 2].time : null;
  const avg = trend.length ? +(trend.reduce((s, r) => s + r.actual, 0) / trend.length).toFixed(2) : null;
  const hourWindow = trend.slice(-6);
  const hourStart = hourWindow.length ? hourWindow[0].actual : null;
  const trendThreshold = 4.0;
  const diffPrev = latest != null && prev != null ? (latest - prev).toFixed(2) : null;
  const diffAvg = latest != null && avg != null ? (latest - avg).toFixed(2) : null;
  const hourDelta = latest != null && hourStart != null ? +(latest - hourStart).toFixed(2) : null;
  const thresholdGap = latest != null ? +(latest - trendThreshold).toFixed(2) : null;
  const hourTrendLabel = hourDelta == null
    ? (isPeriodMode ? '선택 기간 기준 데이터 없음' : '최근 1시간 기준 데이터 없음')
    : hourDelta > 0.05
      ? (isPeriodMode ? '선택 기간 상승세 유지' : '최근 1시간 상승세 유지')
      : hourDelta < -0.05
        ? (isPeriodMode ? '선택 기간 하락세 유지' : '최근 1시간 하락세 유지')
        : (isPeriodMode ? '선택 기간 보합 유지' : '최근 1시간 보합 유지');
  const thresholdLabel = thresholdGap == null
    ? '임계 기준 확인 필요'
    : thresholdGap >= 0
      ? `임계 초과 +${thresholdGap.toFixed(2)}%p`
      : `임계까지 ${Math.abs(thresholdGap).toFixed(2)}%p`;
  const currentTooltip = latestTime
    ? `
      <div class="trend-stat-tooltip__title">현재 기준</div>
      <div class="trend-stat-tooltip__row"><span>시점</span><strong>${esc(latestTime)}</strong></div>
      <div class="trend-stat-tooltip__row"><span>불량률</span><strong>${latest != null ? esc(latest + '%') : '-'}</strong></div>
    `
    : `<div class="trend-stat-tooltip__empty">기준 시점 데이터 없음</div>`;
  const prevTooltip = latestTime && prevTime
    ? `
      <div class="trend-stat-tooltip__title">전일 대비 기준</div>
      <div class="trend-stat-tooltip__row"><span>비교 구간</span><strong>${esc(prevTime)} → ${esc(latestTime)}</strong></div>
      <div class="trend-stat-tooltip__row"><span>변화량</span><strong>${diffPrev != null ? esc((diffPrev > 0 ? '+' : '') + diffPrev + '%p') : '-'}</strong></div>
      <div class="trend-stat-tooltip__row"><span>현재 불량률</span><strong>${latest != null ? esc(latest + '%') : '-'}</strong></div>
    `
    : `<div class="trend-stat-tooltip__empty">비교 기준 데이터 없음</div>`;
  const avgTooltip = trend.length
    ? `
      <div class="trend-stat-tooltip__title">주간 평균 기준</div>
      <div class="trend-stat-tooltip__row"><span>평균 포인트</span><strong>${trend.length}개</strong></div>
      <div class="trend-stat-tooltip__row"><span>평균값</span><strong>${avg != null ? esc(avg + '%') : '-'}</strong></div>
      <div class="trend-stat-tooltip__row"><span>현재 대비</span><strong>${diffAvg != null ? esc((diffAvg > 0 ? '+' : '') + diffAvg + '%p') : '-'}</strong></div>
    `
    : `<div class="trend-stat-tooltip__empty">평균 기준 데이터 없음</div>`;

  return `
    ${renderNoticeBar(noticeMessage, noticeKey)}

    <div class="qa-kpi-grid">
      ${kpis.map(k => kpiCard(k)).join('')}
    </div>

    ${hint ? `
      <div class="hint-banner warn">
        <span class="hint-tag">QA 알림</span>
        <span>${esc(hint.value)}</span>
      </div>
    ` : ''}

    ${periodComparePanel(bundle, '품질 기간 비교')}

    <div class="layout-split-qa">
      <div class="layout-stack">
        <div class="qa-top-row">
          <div class="card qa-top-card">
            <div class="card-header">
              <span class="card-title">${isPeriodMode ? '기간 불량 원인 기여도 (6종)' : '불량 원인 기여도 (6종)'}</span>
              <span class="badge badge-danger">위험</span>
            </div>

            <div class="chart-wrap qa-cause-chart">
              <canvas id="qaBarChart"></canvas>
            </div>
          </div>

          <div class="card qa-top-card qa-trend-card">
            <div class="card-header">
              <span class="card-title">${isPeriodMode ? '기간별 불량률 추세 요약' : '불량률 추세 요약'}</span>
              <button
                type="button"
                class="badge badge-muted"
                onclick="openQaTrendModal()"
                style="background:transparent; cursor:pointer;"
              >
                상세보기
              </button>
            </div>

            <div class="trend-stats">
              <div class="trend-stat">
                <span class="trend-stat-label">현재</span>
                <span class="trend-stat-val ${latest != null && latest >= 4 ? 'trend-up' : ''}">
                  ${latest != null ? latest + '%' : '-'}
                </span>
                <div class="trend-stat-tooltip">${currentTooltip}</div>
              </div>

              <div class="trend-stat">
                <span class="trend-stat-label">${isPeriodMode ? '이전 일자 대비' : '전일 대비'}</span>
                <span class="trend-stat-val ${diffPrev != null && diffPrev > 0 ? 'trend-up' : 'trend-down'}">
                  ${diffPrev != null ? (diffPrev > 0 ? '+' : '') + diffPrev + '%p' : '-'}
                </span>
                <div class="trend-stat-tooltip">${prevTooltip}</div>
              </div>

              <div class="trend-stat">
                <span class="trend-stat-label">${isPeriodMode ? '선택 기간 평균 대비' : '주간 평균 대비'}</span>
                <span class="trend-stat-val ${diffAvg != null && diffAvg > 0 ? 'trend-up' : 'trend-down'}">
                  ${diffAvg != null ? (diffAvg > 0 ? '+' : '') + diffAvg + '%p' : '-'}
                </span>
                <div class="trend-stat-tooltip">${avgTooltip}</div>
              </div>
            </div>

            <div class="qa-trend-summary-note">
              <span class="qa-trend-summary-note__label">추세 상태</span>
              <strong class="qa-trend-summary-note__value">
                ${thresholdLabel}
              </strong>
              <span class="qa-trend-summary-note__meta">
                ${hourTrendLabel}
              </span>
              <span class="qa-trend-summary-note__meta">
                ${latestTime
                  ? `${esc(latestTime)} 기준 · ${isPeriodMode ? '기간별' : '시간대별'} 추세 반영`
                  : `${isPeriodMode ? '기간별' : '시간대별'} 추세 반영`}
              </span>
            </div>
          </div>
        </div>

        ${eventCard(eventTitle, dayModeLabel, bundle.events)}
      </div>

      <div class="qa-side-stack">
        <div class="card">
          <div class="card-header">
            <span class="card-title">재검 우선순위</span>
            <div style="display:flex;align-items:center;gap:8px">
              <span class="badge badge-warn">${recheck.length}건</span>
            </div>
          </div>
          ${recheckItems || '<p class="empty-msg">재검 없음</p>'}
        </div>

        <div class="card qa-issue-summary-card">
          <div class="card-header">
            <span class="card-title">품질 이슈 요약</span>
          </div>
          ${issueItems || '<p class="empty-msg">이슈 없음</p>'}
        </div>
      </div>
    </div>
  `;
}
