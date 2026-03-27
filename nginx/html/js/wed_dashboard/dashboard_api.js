/* ============================================================
   dashboard_api.js — web_dashboard API 계층 / mock fallback
   ============================================================ */
'use strict';

/*
 * Scope note
 * - This file belongs to the browser-based web_dashboard flow.
 * - It talks to /api/v1/dashboard/web/* and /api/v1/dashboard/detail.
 * - It is not used by the PyQt/on-device pages that rely on /js/dashboard.js.
 *
 * In short:
 * - on-device(PyQt): login.html + js/login.js + js/dashboard.js
 * - web dashboard: web_login.html + js/web_login/web_login.js + js/wed_dashboard/*
 */

class DashboardAuthError extends Error {
  constructor(message, status = 401) {
    super(message);
    this.name = 'DashboardAuthError';
    this.status = status;
  }
}

/*
 * 이 파일의 역할
 * 1. 탭별 실제 web_dashboard API endpoint를 호출한다.
 * 2. mock 번들은 로컬 개발/비상 fallback 기준 데이터를 제공한다.
 * 3. 화면 렌더 쪽은 데이터 출처를 몰라도 되도록 중간 계층 역할을 한다.
 */

const DASHBOARD_API = {
  // 탭 이름과 실제 백엔드 web endpoint를 여기서만 매핑한다.
  endpointMap: {
    worker: '/api/v1/dashboard/web/worker',
    qa: '/api/v1/dashboard/web/qa',
    manager: '/api/v1/dashboard/web/manager',
    promo: '/api/v1/dashboard/web/promo',
  },

  /* ── mock 번들 데이터 ── */
  /* 탭 이름(worker / qa / manager) 기준으로 화면 전체에 필요한 샘플 데이터를 돌려준다. */
  getMockBundle(tab) {
    const base = {
      meta: { factory: '본사 1공장', line: null, shift: '주간', model: 'PCB-2401' },
    };

    if (tab === 'worker') return {
      ...base,
      meta: { ...base.meta, line: 'LINE-C' },
      kpis: [
        { id: 'worker_hourly_output',  label: '시간당 생산량', value: 119, unit: 'pcs', target: 600, status: 'critical', meta: 'actual/mock' },
        { id: 'worker_line_output',    label: '현재 라인 생산량', value: 5270, unit: 'pcs', status: 'ok', meta: 'actual/mock' },
        { id: 'worker_recent_10m_ng',  label: '최근 10분 NG', value: 7, unit: '건', status: 'warning', meta: 'actual/mock' },
        { id: 'worker_achievement',    label: '가동률', value: 79.97, unit: '%', status: 'critical', meta: 'actual/mock' },
      ],
      lineTemperature: {
        line: 'LINE-C',
        current: 68.4,
        unit: '°C',
        status: 'run',
        warning: 70,
        critical: 78,
        updatedAt: '14:40',
      },
      hint: { value: 'REFLOW-01 LOT-88421 불량률 8% 초과 - HOLD 필요', confidence: .93 },
      statusGrid: [
        { id: 'AOI-03', type: 'AOI',       status: 'idle', opr: '89.03%', ng: '240건', time: '21:22', detail: { '마지막 갱신': '21:22', '상태메모': '대기 중' } },
        { id: 'CMP-07', type: 'COMPONENT', status: 'idle', opr: '89.03%', ng: '116건', time: '21:22', detail: { '마지막 갱신': '21:22', '상태메모': '대기 중' } },
        { id: 'MNT-04', type: 'MOUNT',     status: 'idle', opr: '52.78%', ng: '948건', time: '13:25', detail: { '마지막 갱신': '13:25', '상태메모': '대기 중', '대기사유': '대기 사유 확인 필요' } },
        { id: 'PRN-03', type: 'PRINTER',   status: 'idle', opr: '89.03%', ng: '108건', time: '21:22', detail: { '마지막 갱신': '21:22', '상태메모': '대기 중' } },
      ],
      actionQueue: [
        { priority: 1, target: 'LINE-C NG 추세', reason: '최근 10분 NG 7건', severity: 'warning', time: '23:10' },
        { priority: 2, target: 'LINE-C 온도 점검', reason: '설비 온도 68.4°C', severity: 'warning', time: '14:40' },
        { priority: 3, target: 'REFLOW-01', reason: 'LOT-88421 불량률 8% 초과 - HOLD 필요', severity: 'critical', time: '12:35' },
        { priority: 4, target: 'CMP-07', reason: 'SHORT + OPEN 복합 불량 감지 - LINE-C, LOT-88421', severity: 'critical', time: '11:25' },
      ],
      globalNotices: [
        { color: '#D97706', meta: '16:10 · LINE-A · alarm', text: 'AOI 처리속도 저하 감지' },
        { color: '#D97706', meta: '15:20 · LINE-D · alarm', text: '라인 D 품질 편차 증가' },
      ],
      ngTrend: [
        { time: '21:30', ng: 14 }, { time: '21:40', ng: 14 }, { time: '21:50', ng: 14 },
        { time: '22:00', ng: 6 }, { time: '22:10', ng: 6 }, { time: '22:20', ng: 6 },
        { time: '22:30', ng: 6 }, { time: '22:40', ng: 6 }, { time: '22:50', ng: 6 },
        { time: '23:00', ng: 7 }, { time: '23:10', ng: 7 }, { time: '23:20', ng: 7 },
      ],
      ngTypes: [
        { name: 'short',          count: 34, color: '#DC2626' },
        { name: 'open',           count: 22, color: '#D97706' },
        { name: 'spur',           count: 16, color: '#2563EB' },
        { name: 'mousebite',      count: 10, color: '#059669' },
        { name: 'spurious_copper',count: 8,  color: '#7C3AED' },
        { name: 'pin_hole',       count: 6,  color: '#6B7280' },
      ],
      events: [
        { color: '#D97706', meta: '11:54 · recheck · MNT-04', text: 'SPUR 증가 추세' },
        { color: '#DC2626', meta: '11:47 · recheck · CMP-07', text: 'OPEN 복합 불량' },
        { color: '#DC2626', meta: '11:40 · recheck · PRN-03', text: 'SHORT 집중 불량' },
        { color: '#2563EB', meta: '11:47 · recheck · CMP-07', text: 'LINE-C MISSING_HOLE 재검 필요' },
      ],
    };

    if (tab === 'qa') return {
      ...base,
      kpis: [
        { id: 'qa_defect_rate', label: '불량률',    value: 3.58, unit: '%',  status: 'critical', meta: 'derived/mock' },
        { id: 'qa_recheck',     label: '재검 대기', value: 171,  unit: '건', status: 'critical', meta: 'derived/mock' },
        { id: 'qa_inspect',     label: '검사 현황', value: 31932, unit: '/32528', target: 32528, status: 'ok', meta: 'actual/mock' },
        { id: 'qa_total_output',label: '현재 총 생산량', value: 32528, unit: 'pcs', status: 'ok', meta: 'actual/mock' },
      ],
      hint: { value: 'LOT-88403 MISSING_HOLE 반복 결함 - 공정 파라미터 점검', severity: 'critical' },
      topDefects: [
        { class_name: 'SHORT',           causeCode: 'short',            count: 34, color: '#DC2626' },
        { class_name: 'OPEN',            causeCode: 'open',             count: 22, color: '#D97706' },
        { class_name: 'SPUR',            causeCode: 'spur',             count: 16, color: '#2563EB' },
        { class_name: 'MOUSE_BITE',      causeCode: 'mouse_bite',       count: 10, color: '#059669' },
        { class_name: 'SPURIOUS_COPPER', causeCode: 'spurious_copper',  count: 8,  color: '#7C3AED' },
        { class_name: 'MISSING_HOLE',    causeCode: 'missing_hole',     count: 6,  color: '#6B7280' },
      ],
      recheckQueue: [
        { lotId: 'LOT-88436', defectClass: 'MOUSE_BITE', priority: 'LOW',    severity: 'info',     queuedAt: '19:17', count: 2,  cause: 'MOUSE_BITE 재검 필요' },
        { lotId: 'LOT-88435', defectClass: 'OPEN',       priority: 'MEDIUM', severity: 'warning',  queuedAt: '19:10', count: 2,  cause: 'OPEN 재검 필요' },
        { lotId: 'LOT-88421', defectClass: 'SHORT',      priority: 'HIGH',   severity: 'critical', queuedAt: '11:40', count: 17, cause: 'SHORT 집중 불량' },
      ],
      defectTrend: [
        { time: '00:00', actual: 4.41 }, { time: '01:00', actual: 4.33 }, { time: '02:00', actual: 4.19 },
        { time: '03:00', actual: 3.63 }, { time: '04:00', actual: 3.40 }, { time: '05:00', actual: 3.00 },
        { time: '06:00', actual: 3.00 }, { time: '07:00', actual: 3.19 }, { time: '08:00', actual: 3.61 },
        { time: '09:00', actual: 3.45 }, { time: '10:00', actual: 3.14 }, { time: '11:00', actual: 3.12 },
        { time: '12:00', actual: 3.21 }, { time: '13:00', actual: 2.80 }, { time: '14:00', actual: 2.82 },
        { time: '15:00', actual: 3.57 }, { time: '16:00', actual: 3.07 }, { time: '17:00', actual: 3.53 },
        { time: '18:00', actual: 3.60 }, { time: '19:00', actual: 4.03 }, { time: '20:00', actual: 4.24 },
        { time: '21:00', actual: 3.76 }, { time: '22:00', actual: 3.53 }, { time: '23:00', actual: 3.67 },
      ],
      issues: [
        { id: 'ISS-2405-001', title: 'SHORT 집중 발생',   cause: '솔더 인쇄 압력 편차', equip: 'SMT-01',    severity: 'critical', action: '솔더 인쇄기 설정 점검', owner: 'QA팀 김○○',  time: '09:15' },
        { id: 'ISS-2405-002', title: 'OPEN 불량 증가',    cause: '리플로우 온도 이상',   equip: 'REFLOW-01', severity: 'warning',  action: '온도 프로파일 재설정', owner: '설비팀 이○○', time: '08:50' },
        { id: 'ISS-2405-003', title: 'PIN_HOLE 간헐 발생',cause: 'PCB 소재 이물질',      equip: 'AOI-01',    severity: 'info',     action: '입고 검사 강화 요청',  owner: '품질팀 박○○', time: '08:30' },
      ],
      events: [
        { color: '#2563EB', meta: '19:17 · 재검 · LOT-88436', text: 'MOUSE_BITE 재검 필요' },
        { color: '#D97706', meta: '19:10 · 재검 · LOT-88435', text: 'OPEN 재검 필요' },
        { color: '#DC2626', meta: '12:35 · 알람 · LINE-C', text: 'LOT-88421 불량률 8% 초과 - HOLD 필요' },
        { color: '#DC2626', meta: '11:25 · 알람 · LINE-C', text: 'SHORT + OPEN 복합 불량 감지 - LINE-C, LOT-88421' },
      ],
    };

    if (tab === 'manager') return {
      ...base,
      kpis: [
        { id: 'mgr_oee',             label: 'OEE',          value: 75.51, unit: '%',  status: 'warning',  meta: 'derived/mock' },
        { id: 'mgr_achievement',     label: '목표 달성률',   value: 74.3, unit: '%',  status: 'warning', meta: 'derived/mock' },
        { id: 'mgr_today_output',    label: '현재 총 생산량', value: 32528, unit: 'pcs', status: 'ok', meta: 'actual/mock' },
        { id: 'mgr_expected_output', label: '예상 종료 생산', value: 43800, unit: 'pcs', status: 'ok',   meta: 'predicted/mock' },
      ],
      managerLineOee: [
        { line: 'LINE-A', actual: 79, target: 85 },
        { line: 'LINE-B', actual: 91, target: 85 },
        { line: 'LINE-C', actual: 48, target: 85 },
        { line: 'LINE-D', actual: 63, target: 85 },
      ],
      managerProductionTrend: [
        { time: '00:00', actual: 1202, plan: 1667 }, { time: '01:00', actual: 2172, plan: 3333 },
        { time: '02:00', actual: 3318, plan: 5000 }, { time: '03:00', actual: 4337, plan: 6667 },
        { time: '04:00', actual: 5307, plan: 8333 }, { time: '05:00', actual: 6606, plan: 10000 },
        { time: '06:00', actual: 7438, plan: 11667 }, { time: '07:00', actual: 8693, plan: 13333 },
        { time: '08:00', actual: 10133, plan: 15000 }, { time: '09:00', actual: 11639, plan: 16667 },
        { time: '10:00', actual: 13645, plan: 18333 }, { time: '11:00', actual: 15088, plan: 20000 },
        { time: '12:00', actual: 16585, plan: 21667 }, { time: '13:00', actual: 17871, plan: 23333 },
        { time: '14:00', actual: 19220, plan: 25000 }, { time: '15:00', actual: 20815, plan: 26667 },
        { time: '16:00', actual: 22380, plan: 28333 }, { time: '17:00', actual: 23826, plan: 30000 },
        { time: '18:00', actual: 25937, plan: 31667 }, { time: '19:00', actual: 28069, plan: 33333 },
        { time: '20:00', actual: 29672, plan: 35000 }, { time: '21:00', actual: 31107, plan: 36667 },
        { time: '22:00', actual: 31929, plan: 38333 }, { time: '23:00', actual: 32528, plan: 40000 },
      ],
      managerDefectTrend: [
        { time: '00:00', rate: 4.41 }, { time: '01:00', rate: 4.33 }, { time: '02:00', rate: 4.19 },
        { time: '03:00', rate: 3.63 }, { time: '04:00', rate: 3.40 }, { time: '05:00', rate: 3.00 },
        { time: '06:00', rate: 3.00 }, { time: '07:00', rate: 3.19 }, { time: '08:00', rate: 3.61 },
        { time: '09:00', rate: 3.45 }, { time: '10:00', rate: 3.14 }, { time: '11:00', rate: 3.12 },
        { time: '12:00', rate: 3.21 }, { time: '13:00', rate: 2.80 }, { time: '14:00', rate: 2.82 },
        { time: '15:00', rate: 3.57 }, { time: '16:00', rate: 3.07 }, { time: '17:00', rate: 3.53 },
        { time: '18:00', rate: 3.60 }, { time: '19:00', rate: 4.03 }, { time: '20:00', rate: 4.24 },
        { time: '21:00', rate: 3.76 }, { time: '22:00', rate: 3.53 }, { time: '23:00', rate: 3.67 },
      ],
      riskOverall: { severity: 'critical', reason: 'LINE-C 다운타임 + NG 급증 복합 리스크' },
      riskLines: [
        { lineId: 'LINE-C', summary: '다운타임과 알람 동시 증가', riskScore: 87, severity: 'critical' },
        { lineId: 'LINE-D', summary: '품질 편차 지속',            riskScore: 68, severity: 'warning'  },
        { lineId: 'LINE-A', summary: 'AOI 속도 저하',             riskScore: 42, severity: 'warning'  },
        { lineId: 'LINE-B', summary: '정상 운영',                 riskScore: 18, severity: 'ok'       },
      ],
      pendingActions: [
        { priority: 1, title: '설비 정지 대응',   summary: 'LINE-C MNT-04 즉시 수리 요청', count: 1 },
        { priority: 2, title: '불량률 초과 대응', summary: 'LINE-D 솔더 공정 점검',         count: 3 },
        { priority: 3, title: '생산 목표 조정',   summary: '금일 예상 -1,400 pcs 부족',     count: 1 },
      ],
      activeAlarms: [
        { alarmId: 'ALM-2401', line: 'LINE-C', equip: 'MNT-04', cause: 'DT-201', severity: 'critical', ack: 'unack', time: '14:55' },
        { alarmId: 'ALM-2404', line: 'LINE-D', equip: 'CMP-07', cause: 'MAT-144',severity: 'warning',  ack: 'hold',  time: '14:40' },
        { alarmId: 'ALM-2405', line: 'LINE-A', equip: 'AOI-01', cause: 'SPD-001',severity: 'warning',  ack: 'unack', time: '15:00' },
        { alarmId: 'ALM-2406', line: 'LINE-B', equip: 'DRV-02', cause: 'VIB-003',severity: 'warning',  ack: 'ack',   time: '13:30' },
      ],
      events: [
        { color: '#DC2626', meta: '15:00 · CRITICAL', text: 'LINE-C MNT-04 다운 — ALM-2401' },
        { color: '#D97706', meta: '14:55 · WARNING',  text: 'LINE-D 품질 편차 지속 — R68' },
        { color: '#2563EB', meta: '14:40 · 조치',     text: 'LINE-D CMP-07 HOLD 처리' },
        { color: '#059669', meta: '14:00 · 정보',     text: 'A조 → B조 인계 완료' },
      ],
    };

    if (tab === 'promo') return {
      ...base,
      kpis: [
        { id: 'promo_today_output',  label: '오늘 생산량',    value: 32528,   unit: 'pcs', status: 'ok', meta: 'actual/mock', target: 36000 },
        { id: 'promo_month_output',  label: '이번 달 생산',   value: 187400, unit: 'pcs', status: 'warning', meta: 'actual/mock', target: 240000 },
        { id: 'promo_oee',           label: '전체 OEE',      value: 75.51,   unit: '%',   status: 'warning', meta: 'derived/mock' },
        { id: 'promo_defect_rate',   label: '현재 불량률',    value: 3.58,    unit: '%',   status: 'warning', meta: 'derived/mock' },
        { id: 'promo_delivery_rate', label: '납기 달성률',    value: 96.4,   unit: '%',   status: 'ok', meta: 'actual/mock' },
      ],
      promoWeekProduction: [
        { day: '월(3/16)', actual: 41234, target: 40000 },
        { day: '화(3/17)', actual: 37636, target: 40000 },
        { day: '수(3/18)', actual: 38973, target: 40000 },
        { day: '목(3/19)', actual: 39616, target: 40000 },
        { day: '금(3/20)', actual: 33461, target: 40000 },
        { day: '토(3/21)', actual: 43012, target: 40000 },
        { day: '일(3/22)', actual: 32528, target: 40000 },
      ],
      promoLines: [
        { line: 'LINE-A', status: 'run',  badge: 'RUN',  output: 2840, defectRate: '3.1%', oee: 79, oeeStatus: 'warning' },
        { line: 'LINE-B', status: 'run',  badge: 'RUN',  output: 3120, defectRate: '1.8%', oee: 91, oeeStatus: 'ok' },
        { line: 'LINE-C', status: 'down', badge: 'DOWN', output: 1980, stopTime: '38분',   oee: 48, oeeStatus: 'critical' },
        { line: 'LINE-D', status: 'run',  badge: 'RUN',  output: 1260, defectRate: '4.8%', oee: 63, oeeStatus: 'warning' },
      ],
      promoTopDefects: [
        { name: 'short', count: 34, color: '#FF3A3A' },
        { name: 'open', count: 22, color: '#FFB020' },
        { name: 'spur', count: 16, color: '#4A7CFF' },
        { name: 'mousebite', count: 10, color: '#00D48A' },
        { name: 'pin_hole', count: 6, color: '#9B6DFF' },
      ],
      promoCurrentAlarms: [
        { severity: 'critical', line: 'LINE-C', message: 'MNT-04 설비 정지 — 즉시 조치 필요', time: '14:55' },
        { severity: 'warning', line: 'LINE-D', message: '불량률 4.8% 임계 초과', time: '15:00' },
        { severity: 'warning', line: 'LINE-A', message: 'AOI-01 처리속도 저하 감지', time: '15:02' },
      ],
      promoMonthlyCompare: [
        { label: '일 생산량', value: '32,528', diff: 'DB 집계 기준', tone: 'up' },
        { label: '전체 OEE', value: '74.37%', diff: '가동률·성능·양품률 반영', tone: 'down' },
        { label: '일 불량수', value: '1,142', diff: 'DB 집계 기준', tone: 'down' },
      ],
      promoTicker: [
        'LINE-C MNT-04 긴급 수리 중 — 설비팀 즉시 지원 바람',
        '이번 달 목표 달성률 78% — 잔여 근무일 12일',
        '3월 품질 목표: 불량률 3.5% 이하',
        '오늘 17:00 전체 조회 — 2공장 회의실',
        '안전 제일 — 보호구 착용 필수',
        '이번 주 우수 작업자: LINE-B 김○○ 님',
      ],
    };

    return { ...base, kpis: [], events: [] };
  },

  buildRequestUrl(tab, params = {}) {
    const endpoint = this.endpointMap[tab] || `/api/dashboard/${tab}`;
    const search = new URLSearchParams();

    Object.entries(params).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '') return;
      search.set(key, String(value));
    });

    return search.size ? `${endpoint}?${search.toString()}` : endpoint;
  },

  getAccessToken() {
    // 신형 web_login 세션을 우선 사용하고, 이전 대시보드 토큰 키는 호환용으로만 남겨둔다.
    return (
      sessionStorage.getItem('sfp_access_token') ||
      localStorage.getItem('rss-access-token') ||
      sessionStorage.getItem('rss-access-token') ||
      ''
    );
  },

  getRefreshToken() {
    return (
      sessionStorage.getItem('sfp_refresh_token') ||
      localStorage.getItem('rss-refresh-token') ||
      sessionStorage.getItem('rss-refresh-token') ||
      ''
    );
  },

  async refreshAccessToken() {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) {
      throw new DashboardAuthError('No refresh token available', 401);
    }

    const res = await fetch('/api/v1/auth/refresh', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      credentials: 'same-origin',
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!res.ok) {
      throw new DashboardAuthError(`Token refresh failed with ${res.status}`, res.status);
    }

    const payload = await res.json();
    const accessToken = String(payload?.access_token || '').trim();

    if (!accessToken) {
      throw new DashboardAuthError('Token refresh returned no access token', 401);
    }

    sessionStorage.setItem('sfp_access_token', accessToken);
    return accessToken;
  },

  /* ── 인증 포함 fetch / 토큰 갱신 ── */
  async authorizedFetch(url, options = {}) {
    const baseHeaders = {
      Accept: 'application/json',
      ...(options.headers || {}),
    };

    const accessToken = this.getAccessToken();
    const requestOptions = {
      ...options,
      method: options.method || 'GET',
      credentials: 'same-origin',
      headers: {
        ...baseHeaders,
      },
    };

    if (accessToken) {
      requestOptions.headers.Authorization = `Bearer ${accessToken}`;
    }

    let res = await fetch(url, requestOptions);
    if (res.status !== 401) {
      return res;
    }

    // access token 만료 시 refresh token으로 한 번만 갱신 후 원요청을 재시도한다.
    const refreshedAccessToken = await this.refreshAccessToken();

    res = await fetch(url, {
      ...requestOptions,
      headers: {
        ...requestOptions.headers,
        Authorization: `Bearer ${refreshedAccessToken}`,
      },
    });

    if (res.status === 401) {
      throw new DashboardAuthError('Unauthorized after token refresh', 401);
    }

    return res;
  },

  async logout() {
    try {
      await this.authorizedFetch('/api/v1/auth/logout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
    } catch (_error) {
      // Ignore logout request failures and clear local session in the UI flow.
    }
  },

  redirectToLogin() {
    try {
      localStorage.removeItem('dashboard_auth_v1');
      sessionStorage.removeItem('sfp_user');
      sessionStorage.removeItem('sfp_access_token');
      sessionStorage.removeItem('sfp_refresh_token');
    } catch (_error) {
      // ignore storage errors
    }

    window.location.href = '/web_login.html';
  },

  /* ── 응답 정규화 ── */
  normalizeBundle(tab, payload) {
    if (!payload || typeof payload !== 'object') {
      throw new Error(`Invalid dashboard payload for tab: ${tab}`);
    }

    // 백엔드가 직접 번들을 반환하거나 { data: bundle } 래핑 둘 다 허용한다.
    const bundle = payload.data && typeof payload.data === 'object' ? payload.data : payload;

    if (!bundle.meta || !Array.isArray(bundle.kpis)) {
      throw new Error(`Incomplete dashboard bundle for tab: ${tab}`);
    }

    return bundle;
  },

  /* ── 상세(detail) API ── */
  async fetchDetail(params = {}) {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '') return;
      search.set(key, String(value));
    });

    const url = search.size ? `/api/v1/dashboard/detail?${search.toString()}` : '/api/v1/dashboard/detail';

    try {
      const res = await this.authorizedFetch(url, { method: 'GET' });

      if (!res.ok) {
        let serverMessage = '';
        try {
          const payload = await res.clone().json();
          const detail = payload?.detail;
          if (typeof detail === 'string') {
            serverMessage = detail;
          } else if (detail && typeof detail === 'object') {
            serverMessage = String(detail.message || detail.code || '');
          }
        } catch (_e) {
          // ignore json parse errors
        }
        const fallbackText = `Dashboard detail API responded with ${res.status}`;
        throw new Error(serverMessage || fallbackText);
      }

      return await res.json();
    } catch (error) {
      if (error instanceof DashboardAuthError) {
        this.redirectToLogin();
        throw error;
      }
      throw error;
    }
  },

  /* ── 탭별 메인 번들 API ── */
  async fetchBundle(tab, params = {}) {
    const url = this.buildRequestUrl(tab, params);

    try {
      const res = await this.authorizedFetch(url, { method: 'GET' });

      if (!res.ok) {
        let serverMessage = '';
        try {
          const payload = await res.clone().json();
          const detail = payload?.detail;
          if (typeof detail === 'string') {
            serverMessage = detail;
          } else if (detail && typeof detail === 'object') {
            serverMessage = String(detail.message || detail.code || '');
          }
        } catch (_e) {
          // ignore json parse errors
        }
        const fallbackText = `Dashboard API responded with ${res.status}`;
        throw new Error(serverMessage || fallbackText);
      }

      const payload = await res.json();
      return this.normalizeBundle(tab, payload);
    } catch (error) {
      if (error instanceof DashboardAuthError) {
        this.redirectToLogin();
        throw error;
      }

      throw error;
    }
  },
};
