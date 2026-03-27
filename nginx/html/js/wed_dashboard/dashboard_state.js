/* ============================================================
   dashboard_state.js — 전역 상태 관리
   ============================================================ */
'use strict';

/*
 * 이 파일의 역할
 * 1. 현재 탭, 다크모드 여부, 사이드바 상태처럼 화면 전역 상태를 보관한다.
 * 2. severity / ack / meta 값을 공통 토큰 HTML로 바꾸는 헬퍼를 제공한다.
 * 3. 여러 파일에서 같은 상태 표현을 재사용할 수 있게 한다.
 */

const DASH_STATE = {
  currentTab: 'worker',
  isDark: false,
  sidebarMini: false,
  selectedDate: null,
  selectedDateRange: null,
  // 선택 필터는 API query parameter와 직접 연결된다.
  selectedFilters: {
    factory: '',
    line: '',
    shift: '',
    period: '',
  },
  // 현재 탭이 마지막으로 받은 원본 bundle을 보관해 상세 모달/재렌더에서 재사용한다.
  currentBundle: null,

  // 상태값을 배지 형태 HTML로 바꿔 주는 공통 렌더 함수.
  renderStateToken(type, value) {
    if (!value) return '';
    const v = String(value).toLowerCase();
    if (type === 'severity') {
      if (v === 'critical') return `<span class="sev sev-critical">CRITICAL</span>`;
      if (v === 'warning')  return `<span class="sev sev-warning">WARNING</span>`;
      if (v === 'info')     return `<span class="sev sev-info">INFO</span>`;
      if (v === 'ok')       return `<span class="sev sev-ok">OK</span>`;
      return `<span class="sev sev-info">${value}</span>`;
    }
    if (type === 'ack') {
      if (v === 'unack') return `<span class="ack-unack">UNACK</span>`;
      if (v === 'hold')  return `<span class="ack-hold">HOLD</span>`;
      if (v === 'ack')   return `<span class="ack-ack">ACK</span>`;
    }
    if (type === 'meta') {
      return `<span class="meta-tag meta-${v}">${value}</span>`;
    }
    return `<span>${value}</span>`;
  },
};
