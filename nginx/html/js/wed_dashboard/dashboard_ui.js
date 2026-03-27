'use strict';

function loadHiddenNotices() {
  try {
    const raw = sessionStorage.getItem(NOTICE_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (_e) {
    return {};
  }
}

function saveHiddenNotice(key) {
  try {
    const next = { ...loadHiddenNotices(), [key]: true };
    sessionStorage.setItem(NOTICE_STORAGE_KEY, JSON.stringify(next));
  } catch (_e) {
    // ignore storage errors
  }
}

function renderNoticeBar(message, key = 'default') {
  const normalizedMessage = String(message || '').trim();
  if (!normalizedMessage) return '';
  if (['-', 'null', '없음', 'none', 'n/a'].includes(normalizedMessage.toLowerCase())) return '';
  const hidden = loadHiddenNotices();
  if (hidden[key]) return '';
  return `
    <div class="notice-bar" data-notice-key="${esc(key)}" role="status">
      <span class="notice-bar__text">${esc(normalizedMessage)}</span>
      <button class="notice-bar__close" type="button" data-close-notice="${esc(key)}" aria-label="안내 닫기">✕</button>
    </div>
  `;
}

function eventCard(title, badge, events, open = false) {
  const eventList = toArr(events);
  const dots = eventList
    .slice(0, 4)
    .map(e => `<div class="event-pip" style="background:${e.color}"></div>`)
    .join('');

  const items = eventList.map(e => `
    <div class="event-item">
      <div class="event-dot" style="background:${e.color}"></div>
      <div class="event-content">
        <div class="event-meta">${esc(e.meta)}</div>
        <div class="event-text">${esc(e.text)}</div>
      </div>
    </div>
  `).join('');

  const bodyContent = items || '<p class="empty-msg">표시할 이벤트가 없습니다.</p>';

  return `
    <div class="event-card ${open ? 'open' : ''}">
      <div class="event-card-head" onclick="this.closest('.event-card').classList.toggle('open'); this.querySelector('.event-preview-dots').style.display = this.closest('.event-card').classList.contains('open') ? 'none' : 'flex';">
        <div class="event-card-head-left">
          <span class="event-card-title">${esc(title)}</span>
          <span class="badge badge-blue">${esc(badge)}</span>
          <div class="event-preview-dots" style="display:${open ? 'none' : 'flex'};">
            ${dots}
          </div>
        </div>

        <div class="event-chevron">
          <svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
            <polyline points="2 4 6 8 10 4"/>
          </svg>
        </div>
      </div>

      <div class="event-body">
        <div class="event-inner">${bodyContent}</div>
      </div>
    </div>
  `;
}

function isPeriodCompareMode(bundle) {
  const mode = String(bundle?.meta?.viewMode || '').toLowerCase();
  return mode === 'period_compare';
}

function periodComparePanel(bundle, title = '기간별 비교') {
  if (!isPeriodCompareMode(bundle)) return '';

  const rows = toArr(bundle?.dailyCompare);
  const range = bundle?.meta?.requestedDateRange || null;
  const subtitle = range
    ? `${esc(range.from)} ~ ${esc(range.to)} · ${range.days}일`
    : '선택한 기간';

  if (!rows.length) {
    return `
      <div class="card period-compare-card">
        <div class="card-header">
          <span class="card-title">${esc(title)}</span>
          <span class="badge badge-soft">${subtitle}</span>
        </div>
        <p class="empty-msg">선택 기간 데이터가 없습니다.</p>
      </div>
    `;
  }

  const bodyRows = rows.map((row) => `
    <tr>
      <td>${esc(String(row.date || ''))}</td>
      <td>${fmtNum(row.produced || 0)}</td>
      <td>${fmtNum(row.ng || 0)}</td>
      <td>${Number(row.defect_rate || 0).toFixed(2)}%</td>
      <td>${Number(row.oee || 0).toFixed(2)}%</td>
      <td>${fmtNum(row.alarm_count || 0)}</td>
    </tr>
  `).join('');

  return `
    <div class="card period-compare-card">
      <div class="card-header">
        <span class="card-title">${esc(title)}</span>
        <span class="badge badge-soft">${subtitle}</span>
      </div>
      <div class="period-compare-table-wrap">
        <table class="period-compare-table">
          <thead>
            <tr>
              <th>날짜</th>
              <th>생산</th>
              <th>NG</th>
              <th>불량률</th>
              <th>OEE</th>
              <th>알람</th>
            </tr>
          </thead>
          <tbody>${bodyRows}</tbody>
        </table>
      </div>
    </div>
  `;
}

function getPromoCompareBadgeLabel(bundle) {
  if (isPeriodCompareMode(bundle)) return '선택 기간';

  const requestedDate = String(bundle?.meta?.requestedDate || '');
  if (!requestedDate) return '월 기준';

  const date = new Date(requestedDate);
  if (Number.isNaN(date.getTime())) return '월 기준';

  const currentMonth = date.getMonth() + 1;
  const previous = new Date(date);
  previous.setMonth(date.getMonth() - 1);
  const previousMonth = previous.getMonth() + 1;

  return `${previousMonth}월 vs ${currentMonth}월`;
}

function modalTitle(text) {
  return `${String(text || '').trim()}`;
}

function getRequestedDayModeLabel(bundle, { today = '오늘', selected = '선택일', period = '기간' } = {}) {
  if (isPeriodCompareMode(bundle)) return period;

  const requestedDate = String(bundle?.meta?.requestedDate || '').trim();
  if (!requestedDate) return today;

  const now = new Date();
  const todayIso = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  return requestedDate === todayIso ? today : selected;
}
