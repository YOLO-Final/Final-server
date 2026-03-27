'use strict';

/* ============================================================
   dashboard_permissions.js
   - 서버 role 값을 dashboard 탭 권한 기준으로 정규화한다
   - 각 권한이 접근 가능한 탭 목록과 기본 진입 탭을 정의한다
   - 사이드바/프로모션 버튼 표시도 이 규칙을 기준으로 제어한다
   ============================================================ */

// 백엔드 role 이름과 프론트 탭 체계를 1곳에서만 매핑한다.
// quality_manager -> qa 처럼 화면 역할명과 서버 역할명이 다른 경우도
// 이 함수가 흡수해서 나머지 렌더 코드가 단순해지도록 한다.
function getDashboardRole(user = getSessionUser()) {
  const role = String(user?.role || '').trim().toLowerCase();
  if (role === 'worker' || role === 'operator') return 'worker';
  if (role === 'qa' || role === 'quality_manager') return 'qa';
  return 'manager';
}

// 역할별 허용 탭 정책.
// worker  -> 작업자 화면만
// qa      -> 작업자 + 품질 화면
// manager -> 작업자 + 품질 + 관리자 + 송출 화면
function getAllowedTabsForRole(role = getDashboardRole()) {
  if (role === 'worker') return ['worker'];
  if (role === 'qa') return ['worker', 'qa'];
  return ['worker', 'qa', 'manager', 'promo'];
}

// 로그인 직후 기본으로 진입할 탭.
// 권한별로 "처음 보여줄 화면"을 중앙에서만 결정한다.
function getDefaultTabForRole(role = getDashboardRole()) {
  if (role === 'worker') return 'worker';
  if (role === 'qa') return 'qa';
  return 'manager';
}

// 탭 전환 전에 현재 role이 접근 가능한 탭인지 빠르게 확인한다.
function isTabAllowed(tab, role = getDashboardRole()) {
  return getAllowedTabsForRole(role).includes(String(tab || '').trim());
}

// 사이드바 탭과 promo fullscreen 버튼을 실제 권한 기준으로 숨긴다.
// 서버 권한은 그대로 두고, 프론트에서는 "보여줄 수 있는 화면"만 제한한다.
function applyRoleTabAccess() {
  const user = getSessionUser();
  const role = getDashboardRole(user);
  const allowedTabs = new Set(getAllowedTabsForRole(role));

  document.querySelectorAll('.sb-item[data-tab]').forEach((el) => {
    const isAllowed = allowedTabs.has(el.dataset.tab);
    el.style.display = isAllowed ? '' : 'none';
  });

  const promoBtn = document.getElementById('promoModeBtn');
  if (promoBtn) {
    promoBtn.style.display = allowedTabs.has('promo') ? '' : 'none';
  }
}
