'use strict';

/* ============================================================
   dashboard_session.js
   - web_dashboard 로그인 세션 확인 전용 모듈
   - localStorage/sessionStorage에 저장된 인증 상태를 읽는다
   - 사이드바 하단 사용자 표시도 여기서만 갱신한다
   ============================================================ */

const DASHBOARD_AUTH_KEY = 'dashboard_auth_v1';
const ACCESS_TOKEN_KEY = 'sfp_access_token';
const SESSION_USER_KEY = 'sfp_user';

function readDashboardAuth() {
  try {
    const raw = localStorage.getItem(DASHBOARD_AUTH_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (_e) {
    return null;
  }
}

// 로그인 직후 web_login.js가 저장한 최소 인증 상태를 확인한다.
// localStorage의 dashboard_auth_v1은 "로그인 여부",
// sessionStorage의 sfp_access_token은 "현재 탭 세션" 역할을 한다.
function hasDashboardSession() {
  const auth = readDashboardAuth();
  return !!(auth && auth.loggedIn && sessionStorage.getItem(ACCESS_TOKEN_KEY));
}

// 대시보드에서 공통으로 쓰는 현재 사용자 정보를 꺼낸다.
// payload 구조는 web_login.js의 saveDashboardSession()과 맞물린다.
function getSessionUser() {
  try {
    const raw = sessionStorage.getItem(SESSION_USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (_e) {
    return null;
  }
}

function clearDashboardSession() {
  localStorage.removeItem(DASHBOARD_AUTH_KEY);
  sessionStorage.clear();
}

function redirectToWebLogin() {
  window.location.replace('/web_login.html');
}

// 사이드바 하단 프로필 영역을 현재 로그인 사용자 기준으로 맞춘다.
// 이름/아바타/권한 라벨/role pill이 하드코딩 상태로 남지 않도록
// 앱 초기화 시점에 한 번 호출해서 화면을 동기화한다.
function applySessionUserProfile() {
  const user = getSessionUser();
  if (!user) return;

  const normalizedRole = getDashboardRole(user);
  const name = String(user.name || user.employee_no || 'User').trim();
  const roleLabels = {
    worker: '작업자 권한',
    qa: '품질관리 권한',
    manager: '관리자 권한',
  };

  const userNameEl = document.getElementById('userName');
  const userAvatarEl = document.getElementById('userAvatar');
  const userRoleLabelEl = document.getElementById('userRoleLabel');
  const userRolePillEl = document.getElementById('userRolePill');

  if (userNameEl) {
    userNameEl.textContent = name;
  }
  if (userAvatarEl) {
    userAvatarEl.textContent = name ? name.charAt(0) : 'U';
  }
  if (userRoleLabelEl) {
    userRoleLabelEl.textContent = roleLabels[normalizedRole] || '관리자 권한';
  }
  if (userRolePillEl) {
    userRolePillEl.textContent = normalizedRole;
  }
}
