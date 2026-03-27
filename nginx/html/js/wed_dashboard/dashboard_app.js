/* ============================================================
   dashboard_app.js — Smart Factory Dashboard 메인 앱
   ============================================================ */
'use strict';

/*
 * Scope note
 * - This file renders the browser-based web_dashboard UI.
 * - It assumes authentication from web_login.html / web_login.js.
 * - It should be read together with dashboard_api.js, not with js/dashboard.js.
 *
 * Separation of concerns:
 * - js/dashboard.js: PyQt/on-device screen flow
 * - js/wed_dashboard/dashboard_app.js: browser web dashboard flow
 */

/* ── 유틸 ── */
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;'
}[c]));

const toArr = v => Array.isArray(v) ? v : [];
const fmtNum = v => v != null ? Number(v).toLocaleString('ko-KR') : '-';
const normalizeLineLabel = value => String(value || '').toUpperCase().replace(/\s+/g, '-');

const sevClass = s => {
  const v = String(s || '').toLowerCase();
  if (v === 'critical') return 'sev-critical';
  if (v === 'warning') return 'sev-warning';
  if (v === 'info') return 'sev-info';
  return 'sev-ok';
};

const sevBadge = s => `<span class="sev ${sevClass(s)}">${String(s || '').toUpperCase()}</span>`;
const badgeHtml = (text, cls = 'badge-muted') => `<span class="badge ${cls}">${esc(text)}</span>`;

function statusTokenHtml(value) {
  const token = String(value || '').trim().toLowerCase();
  if (!token) return '-';

  if (['run', 'idle', 'down', 'maint'].includes(token)) {
    return `<span class="detail-token status-${token}">${esc(token.toUpperCase())}</span>`;
  }

  if (['pass', 'ok', 'success', 'closed', 'complete', 'completed', 'resolved', 'done', 'acked'].includes(token)) {
    return badgeHtml(String(value).toUpperCase(), 'badge-green');
  }

  if (['fail', 'ng', 'reject', 'error', 'active', 'open'].includes(token)) {
    return badgeHtml(String(value).toUpperCase(), 'badge-danger');
  }

  if (['pending', 'hold', 'queued', 'queue', 'wait', 'waiting', 'in_progress'].includes(token)) {
    return badgeHtml(String(value).toUpperCase(), 'badge-warn');
  }

  return badgeHtml(String(value).toUpperCase(), 'badge-muted');
}

function priorityTokenHtml(value) {
  const raw = String(value || '').trim();
  const token = raw.toLowerCase();
  const numeric = Number(raw);

  if (!raw) return '-';
  if (!Number.isNaN(numeric)) {
    if (numeric <= 1) return badgeHtml(`P${numeric}`, 'badge-danger');
    if (numeric === 2) return badgeHtml(`P${numeric}`, 'badge-warn');
    return badgeHtml(`P${numeric}`, 'badge-blue');
  }

  if (['urgent', 'high', 'critical'].includes(token)) return badgeHtml(raw.toUpperCase(), 'badge-danger');
  if (['medium', 'normal'].includes(token)) return badgeHtml(raw.toUpperCase(), 'badge-warn');
  if (['low'].includes(token)) return badgeHtml(raw.toUpperCase(), 'badge-blue');
  return badgeHtml(raw.toUpperCase(), 'badge-muted');
}

function ackTokenHtml(value) {
  const token = String(value || '').trim().toLowerCase();
  if (!token) return '-';
  if (['yes', 'y', 'ack', 'acked', 'done', 'complete', 'completed'].includes(token)) return badgeHtml('ACK', 'badge-green');
  if (['pending', 'hold', 'waiting'].includes(token)) return badgeHtml(token.toUpperCase(), 'badge-warn');
  if (['no', 'n', 'open', 'unacked', 'active'].includes(token)) return badgeHtml(token.toUpperCase(), 'badge-danger');
  return badgeHtml(token.toUpperCase(), 'badge-muted');
}

function detailValueHtml(key, value) {
  const rawKey = String(key || '').trim().toLowerCase();
  const rawValue = value === undefined || value === null || value === '' ? '' : value;

  if (!rawValue) return '-';
  if (typeof rawValue === 'object') return esc(JSON.stringify(rawValue));

  if (rawKey === 'severity') return sevBadge(rawValue);
  if (rawKey.includes('ack')) return ackTokenHtml(rawValue);
  if (rawKey === 'priority') return priorityTokenHtml(rawValue);
  if (['status', 'queue_status', 'result_status', 'ack_status'].includes(rawKey)) return statusTokenHtml(rawValue);

  return esc(String(rawValue));
}
const NOTICE_STORAGE_KEY = 'wed_dashboard_notice_hidden_v1';
const DASHBOARD_AUTO_REFRESH_MS = 3 * 1000;

let dashboardAutoRefreshTimer = null;
let dashboardRenderPromise = null;

function isWorkerScopedUser(user) {
  const role = String(user?.role || '').trim().toLowerCase();
  return role === 'worker' || role === 'operator';
}

function stopDashboardAutoRefresh() {
  if (dashboardAutoRefreshTimer) {
    window.clearInterval(dashboardAutoRefreshTimer);
    dashboardAutoRefreshTimer = null;
  }
}

function startDashboardAutoRefresh() {
  stopDashboardAutoRefresh();
  dashboardAutoRefreshTimer = window.setInterval(() => {
    if (document.hidden || !hasDashboardSession()) return;
    renderCurrentTab({ preserveScroll: true }).catch((error) => {
      console.error('[dashboard] auto refresh failed:', error);
    });
  }, DASHBOARD_AUTO_REFRESH_MS);
}

/* ── 상단 필터바 초기화 ── */
function initFilterBar() {
  const factoryEl = document.getElementById('filterFactory');
  const lineEl = document.getElementById('filterLine');
  const shiftEl = document.getElementById('filterShift');
  const periodEl = document.getElementById('filterPeriod');
  const applyBtn = document.getElementById('filterApply');
  const filterBar = document.querySelector('.filter-bar');

  if (!factoryEl || !lineEl || !shiftEl || !periodEl || !applyBtn) return;

  const user = getSessionUser();
  const userRole = String(user?.role || '').trim().toLowerCase();

  if (DASH_STATE.selectedFilters?.factory) factoryEl.value = DASH_STATE.selectedFilters.factory;
  if (DASH_STATE.selectedFilters?.line) lineEl.value = DASH_STATE.selectedFilters.line;
  if (DASH_STATE.selectedFilters?.shift) shiftEl.value = DASH_STATE.selectedFilters.shift;
  if (DASH_STATE.selectedFilters?.period) periodEl.value = DASH_STATE.selectedFilters.period;

  if (userRole === 'worker' || userRole === 'operator') {
    lineEl.disabled = true;
    lineEl.title = '작업자는 본인 배정 라인으로 자동 조회됩니다.';
    DASH_STATE.selectedFilters = {
      ...(DASH_STATE.selectedFilters || {}),
      factory: '',
      line: '',
      shift: '',
      period: '',
    };
    if (filterBar instanceof HTMLElement) {
      filterBar.style.display = 'none';
    }
    return;
  }

  const syncFilters = () => {
    DASH_STATE.selectedFilters = {
      factory: String(factoryEl.value || '').trim(),
      line: String(lineEl.value || '').trim(),
      shift: String(shiftEl.value || '').trim(),
      period: String(periodEl.value || '').trim(),
    };
  };

  [factoryEl, lineEl, shiftEl, periodEl].forEach((el) => {
    el.addEventListener('change', () => {
      syncFilters();
      renderCurrentTab();
    });
  });

  applyBtn.addEventListener('click', () => {
    syncFilters();
    renderCurrentTab();
  });
}

/* ============================================================
   앱 초기화
   ============================================================ */
document.addEventListener('DOMContentLoaded', () => {
  if (!hasDashboardSession()) {
    window.location.href = '/web_login.html';
    return;
  }

  const sidebarEl = document.getElementById('sidebar');
  const syncSidebarForViewport = () => {
    if (!sidebarEl) return;
    const shouldMini = window.innerWidth <= 900;
    sidebarEl.classList.toggle('mini', shouldMini);
    DASH_STATE.sidebarMini = shouldMini;
  };
  syncSidebarForViewport();
  window.addEventListener('resize', syncSidebarForViewport);

  /* ── 시계 ── */
  function tick() {
    const n = new Date();
    const p = v => String(v).padStart(2, '0');
    const days = ['일', '월', '화', '수', '목', '금', '토'];

    document.getElementById('headerTime').textContent =
      `${p(n.getHours())}:${p(n.getMinutes())}:${p(n.getSeconds())}`;

    document.getElementById('headerDate').textContent =
      `${n.getFullYear()}.${n.getMonth() + 1}.${n.getDate()} (${days[n.getDay()]})`;
  }

  tick();
  setInterval(tick, 1000);

  /* ── 사이드바 토글 ── */
  document.getElementById('sbToggle').addEventListener('click', () => {
    const sb = document.getElementById('sidebar');
    sb.classList.toggle('mini');
    DASH_STATE.sidebarMini = sb.classList.contains('mini');
  });

  /* ── 다크모드 ── */
  document.getElementById('themeBtn').addEventListener('click', () => {
    document.body.classList.toggle('theme-dark');
    DASH_STATE.isDark = document.body.classList.contains('theme-dark');
    document.getElementById('themeBtn').textContent = DASH_STATE.isDark ? '☀' : '🌙';
    renderCurrentTab();
  });

  document.getElementById('promoModeBtn')?.addEventListener('click', (e) => {
    e.stopPropagation();
    if (DASH_STATE.currentTab === 'promo') {
      document.body.classList.add('is-promo-tab');
      if (!document.fullscreenElement && document.documentElement.requestFullscreen) {
        document.documentElement.requestFullscreen().catch(() => {});
      }
    }
  });

  /* ── 알림 팝업 ── */
  document.getElementById('notifBtn').addEventListener('click', e => {
    e.stopPropagation();
    document.getElementById('notifPopup').classList.toggle('open');
  });

  document.addEventListener('click', e => {
    const popup = document.getElementById('notifPopup');
    if (popup && !e.target.closest('.notif-wrapper')) popup.classList.remove('open');
  });

  document.addEventListener('click', () => {
    if (DASH_STATE.currentTab === 'promo' && document.body.classList.contains('is-promo-tab')) {
      document.body.classList.remove('is-promo-tab');
      if (document.fullscreenElement && document.exitFullscreen) {
        document.exitFullscreen().catch(() => {});
      }
    }
  });

  document.addEventListener('fullscreenchange', () => {
    if (!document.fullscreenElement) {
      document.body.classList.remove('is-promo-tab');
    }
  });

  document.getElementById('notifReadAll')?.addEventListener('click', () => {
    document.querySelectorAll('.notif-item').forEach(el => {
      el.classList.add('read');
      el.querySelector('.notif-dot-sm')?.classList.add('read');
    });
    document.getElementById('notifDot')?.remove();
  });

  /* ── 달력 ── */
  initCalendar();
  initFilterBar();
  applySessionUserProfile();
  applyRoleTabAccess();

  /* ── 사이드바 네비 ── */
  document.querySelectorAll('.sb-item[data-tab]').forEach(el => {
    el.addEventListener('click', () => switchTab(el.dataset.tab));
  });

  /* ── 로그아웃 ── */
  document.getElementById('logoutBtn').addEventListener('click', async () => {
    if (confirm('로그아웃 하시겠습니까?')) {
      stopDashboardAutoRefresh();
      await DASHBOARD_API.logout();
      clearDashboardSession();
      redirectToWebLogin();
    }
  });

  startDashboardAutoRefresh();

  /* ── 초기 탭 ── */
  switchTab(getDefaultTabForRole());
});

/* ── 탭 전환 ── */
async function switchTab(tab) {
  const normalizedTab = String(tab || '').trim();
  const role = getDashboardRole();
  const fallbackTab = getDefaultTabForRole(role);
  if (!isTabAllowed(normalizedTab, role)) {
    tab = fallbackTab;
  } else {
    tab = normalizedTab;
  }

  DASH_STATE.currentTab = tab;
  document.body.classList.toggle('is-worker-screen', tab === 'worker');
  document.body.classList.toggle('is-qa-screen', tab === 'qa');
  document.body.classList.toggle('is-manager-screen', tab === 'manager');
  document.body.classList.toggle('is-promo-tab', tab === 'promo');
  document.body.classList.toggle('is-promo-screen', tab === 'promo');

  document.querySelectorAll('.sb-item[data-tab]').forEach(el => {
    el.classList.toggle('active', el.dataset.tab === tab);
  });

  const names = {
    worker: '작업자',
    qa: '품질(QA)',
    manager: '관리자',
    promo: '공용 송출'
  };

  document.getElementById('breadcrumb').textContent = names[tab] || tab;

  await renderCurrentTab();
}

/* ── 탭 데이터 로드 / 메인 렌더 진입점 ── */
async function renderCurrentTab({ preserveScroll = false } = {}) {
  if (dashboardRenderPromise) {
    return dashboardRenderPromise;
  }

  dashboardRenderPromise = (async () => {
    const tab = DASH_STATE.currentTab;
    CHARTS.destroyAll();
    const content = document.getElementById('mainContent');
    if (!content) return;

    const scrollContainer = document.querySelector('.content-scroll');
    const previousScrollTop = preserveScroll && scrollContainer ? scrollContainer.scrollTop : null;

    const queryParams = {};
    if (DASH_STATE.selectedDateRange?.from && DASH_STATE.selectedDateRange?.to) {
      const fromDate = new Date(DASH_STATE.selectedDateRange.from);
      const toDate = new Date(DASH_STATE.selectedDateRange.to);
      const dayMs = 24 * 60 * 60 * 1000;
      const rangeDays = Math.floor((toDate - fromDate) / dayMs) + 1;

      if (!Number.isNaN(rangeDays) && rangeDays > 31) {
        const clampedFrom = new Date(toDate);
        clampedFrom.setDate(toDate.getDate() - 30);
        const toIso = (d) => {
          const y = d.getFullYear();
          const m = String(d.getMonth() + 1).padStart(2, '0');
          const day = String(d.getDate()).padStart(2, '0');
          return `${y}-${m}-${day}`;
        };
        DASH_STATE.selectedDateRange = {
          from: toIso(clampedFrom),
          to: toIso(toDate),
        };
        queryParams.date_from = DASH_STATE.selectedDateRange.from;
        queryParams.date_to = DASH_STATE.selectedDateRange.to;
      } else {
        queryParams.date_from = DASH_STATE.selectedDateRange.from;
        queryParams.date_to = DASH_STATE.selectedDateRange.to;
      }
    } else if (DASH_STATE.selectedFilters?.period) {
      const now = new Date();
      const toIso = (d) => {
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${y}-${m}-${day}`;
      };

      if (DASH_STATE.selectedFilters.period === 'yesterday') {
        const y = new Date(now);
        y.setDate(now.getDate() - 1);
        const ymd = toIso(y);
        queryParams.date_from = ymd;
        queryParams.date_to = ymd;
      } else if (DASH_STATE.selectedFilters.period === 'weekly') {
        const start = new Date(now);
        start.setDate(now.getDate() - 6);
        queryParams.date_from = toIso(start);
        queryParams.date_to = toIso(now);
      }
    }
    const sessionUser = getSessionUser();
    const isWorkerScoped = isWorkerScopedUser(sessionUser);

    if (!isWorkerScoped && DASH_STATE.selectedFilters?.factory) {
      queryParams.factory = DASH_STATE.selectedFilters.factory;
    }
    if (!isWorkerScoped && DASH_STATE.selectedFilters?.line) {
      queryParams.line = DASH_STATE.selectedFilters.line;
    }
    if (!isWorkerScoped && DASH_STATE.selectedFilters?.shift) {
      queryParams.shift = DASH_STATE.selectedFilters.shift;
    }
    if (!isWorkerScoped && DASH_STATE.selectedFilters?.period) {
      queryParams.period = DASH_STATE.selectedFilters.period;
    }

    let bundle;
    try {
      bundle = await DASHBOARD_API.fetchBundle(tab, queryParams);
    } catch (error) {
      console.error('[dashboard] failed to load bundle:', error);
      const errorText = String(error?.message || '').trim() || '잠시 후 다시 시도해주세요.';
      content.innerHTML = `
        <div class="empty-msg" style="padding:24px;">
          데이터를 불러오지 못했습니다. ${esc(errorText)}
        </div>
      `;
      return;
    }

    DASH_STATE.currentBundle = bundle;

    if (tab === 'worker') content.innerHTML = workerLayout(bundle);
    else if (tab === 'qa') content.innerHTML = qaLayout(bundle);
    else if (tab === 'manager') content.innerHTML = managerLayout(bundle);
    else if (tab === 'promo') content.innerHTML = promoLayout(bundle);
    else content.innerHTML = '<p class="empty-msg">준비 중</p>';

    requestAnimationFrame(() => {
      if (preserveScroll && scrollContainer && previousScrollTop != null) {
        scrollContainer.scrollTop = previousScrollTop;
      }

      if (tab === 'worker') {
        CHARTS.renderNgTrend(
          'workerNgSparkline',
          bundle.ngTrend,
          DASHBOARD_THRESHOLDS.resolveThreshold('worker_recent_10m_ng')
        );
        CHARTS.renderNgPie('workerNgPie', bundle.ngTypes);
      }

      if (tab === 'qa') {
        CHARTS.renderQaBar('qaBarChart', bundle.topDefects);
      }

      if (tab === 'manager') {
        CHARTS.renderManagerProduction('managerProductionChart', bundle.managerProductionTrend);
        CHARTS.renderManagerDefectTrend('managerDefectChart', bundle.managerDefectTrend, 4.0);
      }

      if (tab === 'promo') {
        CHARTS.renderPromoWeekChart('promoWeekChart', bundle.promoWeekProduction);
      }
    });

    content.querySelectorAll('[data-close-notice]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const key = btn.getAttribute('data-close-notice') || '';
        if (key) saveHiddenNotice(key);
        btn.closest('.notice-bar')?.remove();
      });
    });
  })();

  try {
    return await dashboardRenderPromise;
  } finally {
    dashboardRenderPromise = null;
  }
}

/* ── QA / Worker / Manager 목록형 모달 ── */
window.openIssueModal = function(data) {
  if (typeof data === 'string') {
    try {
      data = JSON.parse(data);
    } catch (e) {
      return;
    }
  }

  const content = document.getElementById('detailModalContent');
  const modal = document.getElementById('detailModal');
  if (!content || !modal) return;

  content.innerHTML = `
    <p class="modal-title">${esc(modalTitle('품질 이슈 상세 정보'))}</p>
    <div class="modal-row"><span class="modal-label">이슈 ID</span><span class="modal-val">${esc(data.id)}</span></div>
    <div class="modal-row"><span class="modal-label">이슈명</span><span class="modal-val">${esc(data.title)}</span></div>
    <div class="modal-row"><span class="modal-label">추정 원인</span><span class="modal-val">${esc(data.cause)}</span></div>
    <div class="modal-row"><span class="modal-label">관련 설비</span><span class="modal-val">${esc(data.equip)}</span></div>
    <div class="modal-row"><span class="modal-label">심각도</span><span class="modal-val">${sevBadge(data.severity)}</span></div>
    <div class="modal-row"><span class="modal-label">조치 사항</span><span class="modal-val">${esc(data.action)}</span></div>
    <div class="modal-row"><span class="modal-label">담당자</span><span class="modal-val">${esc(data.owner)}</span></div>
  `;

  modal.classList.add('open');
};

window.openQaTrendModal = function() {
  const bundle = DASH_STATE.currentBundle || {};
  const trend = toArr(bundle.defectTrend);
  const latest = trend.length ? trend[trend.length - 1].actual : null;
  const latestTime = trend.length ? trend[trend.length - 1].time : null;
  const avg = trend.length ? +(trend.reduce((s, r) => s + r.actual, 0) / trend.length).toFixed(2) : null;
  const threshold = 4.0;
  const content = document.getElementById('detailModalContent');
  const modal = document.getElementById('detailModal');
  if (!content || !modal) return;

  content.innerHTML = `
    <div class="qa-trend-detail">
      <p class="modal-title">${esc(modalTitle('불량률 추세 상세 보기'))}</p>
      <div class="qa-trend-detail__meta">
        <div class="modal-row"><span class="modal-label">최신 시점</span><span class="modal-val">${latestTime ? esc(latestTime) : '-'}</span></div>
        <div class="modal-row"><span class="modal-label">현재 불량률</span><span class="modal-val">${latest != null ? esc(latest + '%') : '-'}</span></div>
        <div class="modal-row"><span class="modal-label">주간 평균</span><span class="modal-val">${avg != null ? esc(avg + '%') : '-'}</span></div>
        <div class="modal-row"><span class="modal-label">임계 기준</span><span class="modal-val">${threshold}%</span></div>
      </div>
      <div class="qa-trend-detail__chart">
        <canvas id="qaTrendDetailChart"></canvas>
      </div>
    </div>
  `;

  modal.classList.add('open');
  requestAnimationFrame(() => {
    CHARTS.renderQaTrendDetail('qaTrendDetailChart', trend, threshold);
  });
};


window.openQaRecheckModal = function() {
  const bundle = DASH_STATE.currentBundle || {};
  const recheck = toArr(bundle.recheckQueue);
  const content = document.getElementById('detailModalContent');
  const modal = document.getElementById('detailModal');
  if (!content || !modal) return;

  const cards = recheck.map((item) => `
    <button class="summary-list-card" type="button"
      onclick="openDashboardDetailModal({
        screen: 'qa',
        detailId: 'qa.reinspection.queue',
        targetType: 'lot',
        targetId: '${esc(item.lotId || '')}'
      }, '재검 상세 정보')">
      <div class="summary-list-card__head">
        <strong>${esc(item.defectClass || '오류 정보 없음')}</strong>
        <span class="summary-list-card__meta">${esc(item.lotId || '-')}</span>
      </div>
      <div class="summary-list-card__body">
        <div class="summary-list-card__row"><span>현재 상태</span><span>${sevBadge(item.severity || 'info')} <span class="detail-token status-${String(item.status || 'queued').toLowerCase()}">${esc(String(item.status || 'queued').toUpperCase())}</span></span></div>
        <div class="summary-list-card__row"><span>영향</span><span>${esc(item.cause || `${Number(item.count || 0)}건 재검 필요`)}</span></div>
      </div>
    </button>
  `).join('');

  content.innerHTML = `
    <div class="qa-recheck-detail">
      <p class="modal-title">${esc(modalTitle('재검 우선순위 상세 목록'))}</p>
      <div class="manager-alarm-detail__summary">
        <span>현재 재검 대기</span>
        <strong>${recheck.length}건</strong>
      </div>
      <div class="summary-list-wrap">
        ${cards || '<p class="empty-msg">재검 없음</p>'}
      </div>
    </div>
  `;

  modal.classList.add('open');
};
window.openWorkerQueueModal = function() {
  const bundle = DASH_STATE.currentBundle || {};
  const queue = toArr(bundle.actionQueue);
  const content = document.getElementById('detailModalContent');
  const modal = document.getElementById('detailModal');
  if (!content || !modal) return;

  const cards = queue.map((item) => `
    <div class="summary-list-card summary-list-card--static">
      <div class="summary-list-card__head">
        <strong>${esc(item.target || '대상 정보 없음')}</strong>
        <span class="summary-list-card__meta">${esc(item.time || '-')}</span>
      </div>
      <div class="summary-list-card__body">
        <div class="summary-list-card__row"><span>현재 상태</span><span>${sevBadge(item.severity || 'info')}</span></div>
        <div class="summary-list-card__row"><span>영향</span><span>${esc(item.reason || '확인 필요')}</span></div>
      </div>
    </div>
  `).join('');

  content.innerHTML = `
    <div class="manager-alarm-detail">
      <p class="modal-title">${esc(modalTitle('액션 큐 상세 목록'))}</p>
      <div class="manager-alarm-detail__summary">
        <span>현재 액션 큐</span>
        <strong>${queue.length}건</strong>
      </div>
      <div class="summary-list-wrap">
        ${cards || '<p class="empty-msg">액션 큐 없음</p>'}
      </div>
    </div>
  `;

  modal.classList.add('open');
};


window.openWorkerNoticeModal = function() {
  const bundle = DASH_STATE.currentBundle || {};
  const notices = toArr(bundle.globalNotices);
  const content = document.getElementById('detailModalContent');
  const modal = document.getElementById('detailModal');
  if (!content || !modal) return;

  const cards = notices.map((item, idx) => `
    <div class="summary-list-card summary-list-card--static">
      <div class="summary-list-card__head">
        <strong>${esc(item.meta || `공지 ${idx + 1}`)}</strong>
        <span class="summary-list-card__meta">공지</span>
      </div>
      <div class="summary-list-card__body">
        <div class="summary-list-card__row"><span>현재 상태</span><span><span class="detail-token status-info">공지</span></span></div>
        <div class="summary-list-card__row"><span>영향</span><span>${esc(item.text || '내용 없음')}</span></div>
      </div>
    </div>
  `).join('');

  content.innerHTML = `
    <div class="manager-alarm-detail">
      <p class="modal-title">${esc(modalTitle('공지 상세 목록'))}</p>
      <div class="manager-alarm-detail__summary">
        <span>현재 공지</span>
        <strong>${notices.length}건</strong>
      </div>
      <div class="summary-list-wrap">
        ${cards || '<p class="empty-msg">공지 없음</p>'}
      </div>
    </div>
  `;

  modal.classList.add('open');
};


window.openManagerAlarmModal = function() {
  const bundle = DASH_STATE.currentBundle || {};
  const alarms = toArr(bundle.activeAlarms);
  const content = document.getElementById('detailModalContent');
  const modal = document.getElementById('detailModal');
  if (!content || !modal) return;

  const alarmCards = alarms.map((alarm) => `
    <button class="summary-list-card" type="button"
      onclick="openDashboardDetailModal({
        screen: 'manager',
        detailId: 'common.alarm.detail',
        targetType: 'alarm',
        targetId: '${esc(alarm.alarmId || '')}'
      }, '알람 상세 정보')">
      <div class="summary-list-card__head">
        <strong>${esc(alarm.cause || alarm.alarmId || '알람')}</strong>
        <span class="summary-list-card__meta">${esc(alarm.line || '-')} · ${esc(alarm.equip || '-')}</span>
      </div>
      <div class="summary-list-card__body">
        <div class="summary-list-card__row"><span>현재 상태</span><span>${sevBadge(alarm.severity)} <span class="ack-${alarm.ack}">${esc(String(alarm.ack || '').toUpperCase())}</span></span></div>
        <div class="summary-list-card__row"><span>영향</span><span>${esc(alarm.time || '-')} 발생</span></div>
      </div>
    </button>
  `).join('');

  content.innerHTML = `
    <div class="manager-alarm-detail">
      <p class="modal-title">${esc(modalTitle('미해결 알람 상세 목록'))}</p>
      <div class="manager-alarm-detail__summary">
        <span>현재 미해결 알람</span>
        <strong>${alarms.length}건</strong>
      </div>
      <div class="summary-list-wrap">
        ${alarmCards || '<p class="empty-msg">미해결 알람 없음</p>'}
      </div>
    </div>
  `;

  modal.classList.add('open');
};

/* ── 공통 detail API 모달 ── */
window.openDashboardDetailModal = async function(params, title = '상세 정보') {
  const content = document.getElementById('detailModalContent');
  const modal = document.getElementById('detailModal');
  if (!content || !modal) return;

  content.innerHTML = `<p class="modal-title">${esc(title)}</p><p class="empty-msg">상세 데이터를 불러오는 중...</p>`;
  modal.classList.add('open');

  try {
    const detail = await DASHBOARD_API.fetchDetail(params);
    const detailLabelMap = {
      ack_status: 'ACK 상태',
      alarm_code: '알람 코드',
      created_at: '생성 시각',
      defect_type: '불량 유형',
      defect_qty: '불량 수량',
      equip_code: '설비',
      handled_at: '처리 시각',
      handled_by: '처리자',
      inspection_type: '검사 유형',
      line_code: '라인',
      lot_id: 'LOT',
      model_code: '모델',
      note: '메모',
      occurred_at: '발생 시각',
      queue_status: '재검 상태',
      recorded_at: '기록 시각',
      request_type: '요청 유형',
      result_status: '판정',
      severity: '심각도',
      status: '상태',
      summary: '요약',
      total_checked_qty: '검사 수량',
      user_name: '담당자',
    };

    const humanizeKey = (key) => {
      if (!key) return '-';
      if (detailLabelMap[key]) return detailLabelMap[key];
      if (/[가-힣]/.test(key)) return key;
      return String(key)
        .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
        .replace(/[_-]+/g, ' ')
        .trim()
        .replace(/\b\w/g, (char) => char.toUpperCase());
    };

    const summaryRows = toArr(detail.summary);
    const logRows = toArr(detail.logs);
    const relatedRows = toArr(detail.relatedItems);

    const firstMeaningfulValue = (rows, keys = []) => {
      for (const row of rows) {
        for (const key of keys) {
          const value = row?.[key];
          if (value !== undefined && value !== null && String(value).trim()) {
            return String(value).trim();
          }
        }
      }
      return '';
    };

    const findTopIssue = (rows = []) => {
      const counts = new Map();
      const issueKeys = ['defect_type', 'defect_code', 'alarm_code', 'request_type', 'title', 'message'];

      rows.forEach((row) => {
        const issue = firstMeaningfulValue([row], issueKeys);
        if (!issue) return;
        counts.set(issue, (counts.get(issue) || 0) + 1);
      });

      let topIssue = '';
      let topCount = 0;
      counts.forEach((count, issue) => {
        if (count > topCount) {
          topIssue = issue;
          topCount = count;
        }
      });

      if (!topIssue) return '특이 오류 없음';
      return topCount > 1 ? `${topIssue} ${topCount}건` : topIssue;
    };

    const summarizeCurrentState = () => {
      const state = firstMeaningfulValue(
        [...summaryRows, ...logRows, ...relatedRows],
        ['queue_status', 'status', 'result_status', 'ack_status', 'severity'],
      );
      return state || '상태 정보 없음';
    };

    const summarizeImpact = () => {
      const impact = firstMeaningfulValue(
        [...summaryRows, ...logRows, ...relatedRows],
        ['cause_text', 'summary', 'note', 'message', 'meta_text'],
      );
      return impact || '영향 정보 없음';
    };

    const renderRows = (rows, emptyText) => rows.length ? `
      <div class="modal-detail-grid">
        ${rows.map((row) => `
          <div class="modal-detail-block">
            ${Object.entries(row).map(([key, value]) => `
              <div class="modal-row">
                <span class="modal-label">${esc(humanizeKey(key))}</span>
                <span class="modal-val">${detailValueHtml(key, value)}</span>
              </div>
            `).join('')}
          </div>
        `).join('')}
      </div>
    ` : `<p class="empty-msg">${emptyText}</p>`;

    content.innerHTML = `
      <div class="modal-detail-shell">
        <p class="modal-title">${esc(title)}</p>
        <div class="modal-detail-meta">
          <span class="modal-detail-chip">대상 ${esc(detail.targetType || '-')}</span>
          <span class="modal-detail-chip">${esc(detail.targetId || '-')}</span>
          <span class="modal-detail-chip modal-detail-chip--muted">${esc(detail.screen || '-')}</span>
        </div>

        <section class="modal-detail-section">
          <p class="modal-detail-section-title">핵심 요약</p>
          <div class="modal-summary-strip">
            <div class="modal-summary-card">
              <span class="modal-summary-card__label">가장 많이 발생한 항목</span>
              <strong class="modal-summary-card__value">${esc(findTopIssue([...summaryRows, ...logRows, ...relatedRows]))}</strong>
            </div>
            <div class="modal-summary-card">
              <span class="modal-summary-card__label">현재 상태</span>
              <strong class="modal-summary-card__value">${detailValueHtml('status', summarizeCurrentState())}</strong>
            </div>
            <div class="modal-summary-card">
              <span class="modal-summary-card__label">영향</span>
              <strong class="modal-summary-card__value modal-summary-card__value--text">${esc(summarizeImpact())}</strong>
            </div>
          </div>
        </section>

        <section class="modal-detail-section">
          <p class="modal-detail-section-title">기본 데이터</p>
          ${renderRows(summaryRows.slice(0, 1), '요약 데이터 없음')}
        </section>

        <section class="modal-detail-section">
          <p class="modal-detail-section-title">핵심 로그</p>
          ${renderRows(logRows.slice(0, 3), '로그 없음')}
        </section>

        <section class="modal-detail-section">
          <p class="modal-detail-section-title">연관 항목</p>
          ${renderRows(relatedRows.slice(0, 2), '관련 항목 없음')}
        </section>
      </div>
    `;
  } catch (error) {
    content.innerHTML = `
      <p class="modal-title">${esc(title)}</p>
      <p class="empty-msg">상세 데이터를 불러오지 못했습니다.</p>
      <div class="modal-row"><span class="modal-label">오류</span><span class="modal-val">${esc(error?.message || 'unknown error')}</span></div>
    `;
  }
};

/* ── 달력 ── */
function initCalendar() {
  const MN = ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월'];
  const now = new Date();

  let calY = now.getFullYear();
  let calM = now.getMonth();
  let calFrom = null;
  let calTo = null;

  const toDateKey = (dateObj) => {
    if (!(dateObj instanceof Date)) return '';
    const y = dateObj.getFullYear();
    const m = String(dateObj.getMonth() + 1).padStart(2, '0');
    const d = String(dateObj.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  };

  const toDate = (y, m, d) => new Date(y, m, d, 0, 0, 0, 0);

  const formatBannerDate = (dateObj) => {
    if (!(dateObj instanceof Date)) return '';
    return `${dateObj.getFullYear()}년 ${MN[dateObj.getMonth()]} ${dateObj.getDate()}일`;
  };

  const resetToRealtimeToday = () => {
    const today = new Date();
    calY = today.getFullYear();
    calM = today.getMonth();
    calFrom = null;
    calTo = null;
    DASH_STATE.selectedDate = null;
    DASH_STATE.selectedDateRange = null;
    document.getElementById('calConfirm').disabled = true;
    document.getElementById('calPopup').classList.remove('open');
    document.getElementById('dateBanner').classList.remove('show');
    renderCurrentTab();
  };

  function render() {
    document.getElementById('calMonth').textContent = `${calY}년 ${MN[calM]}`;

    const first = new Date(calY, calM, 1).getDay();
    const total = new Date(calY, calM + 1, 0).getDate();
    const prev = new Date(calY, calM, 0).getDate();

    let h = '';

    for (let i = 0; i < first; i++) {
      h += `<div class="cal-cell other">${prev - first + i + 1}</div>`;
    }

    for (let d = 1; d <= total; d++) {
      const cellDate = toDate(calY, calM, d);
      const isT = calY === now.getFullYear() && calM === now.getMonth() && d === now.getDate();
      const isStart = calFrom && toDateKey(calFrom) === toDateKey(cellDate);
      const isEnd = calTo && toDateKey(calTo) === toDateKey(cellDate);
      const isSingle = isStart && isEnd;
      const isInRange = calFrom && calTo && cellDate >= calFrom && cellDate <= calTo;
      h += `<div class="cal-cell${isT ? ' today' : ''}${isInRange ? ' in-range' : ''}${isStart ? ' range-start' : ''}${isEnd ? ' range-end' : ''}${isSingle ? ' selected' : ''}" data-d="${d}">${d}</div>`;
    }

    document.getElementById('calDays').innerHTML = h;

    document.querySelectorAll('.cal-cell[data-d]').forEach(el => {
      el.addEventListener('click', e => {
        e.stopPropagation();
        const clickedDate = toDate(calY, calM, +el.dataset.d);

        if (!calFrom || (calFrom && calTo)) {
          calFrom = clickedDate;
          calTo = null;
        } else {
          if (clickedDate < calFrom) {
            calTo = calFrom;
            calFrom = clickedDate;
          } else {
            calTo = clickedDate;
          }
        }

        document.getElementById('calConfirm').disabled = !(calFrom && calTo);
        render();
      });
    });
  }

  document.getElementById('calBtn')?.addEventListener('click', e => {
    e.stopPropagation();
    if (DASH_STATE.selectedDateRange?.from && DASH_STATE.selectedDateRange?.to) {
      const from = new Date(DASH_STATE.selectedDateRange.from);
      const to = new Date(DASH_STATE.selectedDateRange.to);
      if (!Number.isNaN(from.getTime()) && !Number.isNaN(to.getTime())) {
        calFrom = toDate(from.getFullYear(), from.getMonth(), from.getDate());
        calTo = toDate(to.getFullYear(), to.getMonth(), to.getDate());
        calY = calFrom.getFullYear();
        calM = calFrom.getMonth();
      } else {
        calFrom = null;
        calTo = null;
      }
    } else {
      calFrom = null;
      calTo = null;
    }
    document.getElementById('calConfirm').disabled = !(calFrom && calTo);
    render();
    document.getElementById('calPopup').classList.toggle('open');
  });

  document.getElementById('calPrev')?.addEventListener('click', e => {
    e.stopPropagation();
    if (--calM < 0) {
      calM = 11;
      calY--;
    }
    render();
  });

  document.getElementById('calNext')?.addEventListener('click', e => {
    e.stopPropagation();
    if (++calM > 11) {
      calM = 0;
      calY++;
    }
    render();
  });

  document.getElementById('calCancel')?.addEventListener('click', e => {
    e.stopPropagation();
    document.getElementById('calPopup').classList.remove('open');
  });

  document.getElementById('calReset')?.addEventListener('click', e => {
    e.stopPropagation();
    resetToRealtimeToday();
  });

  document.getElementById('calConfirm')?.addEventListener('click', e => {
    e.stopPropagation();
    if (!(calFrom && calTo)) return;

    const dayMs = 24 * 60 * 60 * 1000;
    const selectedDays = Math.floor((calTo - calFrom) / dayMs) + 1;

    if (selectedDays > 31) {
      const fixedFrom = new Date(calTo);
      fixedFrom.setDate(calTo.getDate() - 30);
      calFrom = fixedFrom;
      render();
    }

    DASH_STATE.selectedDate = toDateKey(calFrom);
    DASH_STATE.selectedDateRange = {
      from: toDateKey(calFrom),
      to: toDateKey(calTo),
    };

    document.getElementById('calPopup').classList.remove('open');
    document.getElementById('dateBanner').classList.add('show');
    document.getElementById('bannerText').textContent =
      `${formatBannerDate(calFrom)} ~ ${formatBannerDate(calTo)} 데이터 조회 중`;
    renderCurrentTab();
  });

  document.getElementById('bannerClose')?.addEventListener('click', () => {
    document.getElementById('dateBanner').classList.remove('show');
  });

  document.addEventListener('click', e => {
    const p = document.getElementById('calPopup');
    if (p?.classList.contains('open') && !e.target.closest('.cal-wrap')) {
      p.classList.remove('open');
    }
  });
}
