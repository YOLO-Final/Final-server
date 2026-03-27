/*
 * web_login.js
 *
 * 역할 범위
 * - 이 파일은 브라우저 기반 web_dashboard 로그인 진입 스크립트다.
 * - 아래 on-device(PyQt) 흐름과는 분리되어 있다.
 * - /login.html
 * - /js/login.js
 * - /js/dashboard.js
 * 위 파일들은 PyQt/on-device 흐름에 속한다.
 *
 * 현재 웹 로그인 흐름
 * - 로그인 페이지: /web_login.html
 * - 로그인 성공 후 이동: /web_dashboard.html
 * - 인증 키: dashboard_auth_v1 / sfp_access_token / sfp_refresh_token
 */
const DASHBOARD_AUTH_KEY = 'dashboard_auth_v1';
const ACCESS_TOKEN_KEY = 'sfp_access_token';
const REFRESH_TOKEN_KEY = 'sfp_refresh_token';
const SESSION_USER_KEY = 'sfp_user';
const AUTO_FACE_LOGIN_INTERVAL_MS = 1800;
const MAX_CAMERA_FPS = 10;
const CAPTURE_QUALITY = 0.9;

const empInput = document.getElementById('emp-id');
const rememberChk = document.getElementById('remember');
const passwordInput = document.getElementById('password');
const loginBtn = document.getElementById('btn-login');
const faceEmployeeNoInput = document.getElementById('face-employee-no');
const faceVideo = document.getElementById('face-video');
const faceStartBtn = document.getElementById('face-start-btn');
const faceStopBtn = document.getElementById('face-stop-btn');
const faceLoginBtn = document.getElementById('face-login-btn');

let faceAutoTimer = null;
let faceLoginInFlight = false;
let cameraStream = null;

/* 이 파일에서 관리하는 웹 로그인 세션 구조
 * - localStorage.dashboard_auth_v1: 로그인 여부 + 최소 사용자 표시 정보
 * - sessionStorage.sfp_access_token: 현재 탭에서만 유효한 access token
 * - sessionStorage.sfp_refresh_token: access token 재발급용 refresh token
 * - sessionStorage.sfp_user: employee_no / name / role
 * 화면 리다이렉트, 사이드바 프로필, 권한별 탭 제어는 이 값들을 기준으로 이어진다.
 */
function readStoredDashboardAuth() {
  try {
    const raw = localStorage.getItem(DASHBOARD_AUTH_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (_error) {
    return null;
  }
}

function hasWebDashboardSession() {
  /* 로그인 여부 판단은 "auth 객체가 있다"만으로 충분하지 않다.
     access token이 실제로 남아 있는지까지 같이 봐야
     새로고침 직후 깨진 세션을 정상적으로 걸러낼 수 있다. */
  const auth = readStoredDashboardAuth();
  return !!(auth && auth.loggedIn === true && sessionStorage.getItem(ACCESS_TOKEN_KEY));
}

function normalizeRole(role) {
  /* 서버 role은 quality_manager처럼 길게 내려올 수 있지만
     프런트 탭은 worker / qa / manager 세 종류만 이해하므로
     여기서 화면 권한 체계에 맞게 정규화한다. */
  const raw = String(role || '').trim().toLowerCase();
  if (raw === 'worker') return 'worker';
  if (raw === 'qa' || raw === 'quality_manager') return 'qa';
  return 'manager';
}

function saveDashboardSession(payload) {
  /* 로그인 직후 필요한 최소 세션 정보만 저장한다.
     상세 프로필 전체를 다 넣기보다, 화면 분기와 사용자 표시용 핵심 정보만 남겨
     웹 대시보드 초기화가 빠르게 끝나도록 구성했다. */
  const auth = {
    loggedIn: true,
    user: String(payload.name || payload.employee_no || 'user'),
    role: normalizeRole(payload.role),
  };

  localStorage.setItem(DASHBOARD_AUTH_KEY, JSON.stringify(auth));
  sessionStorage.setItem(
    SESSION_USER_KEY,
    JSON.stringify({
      employee_no: payload.employee_no || '',
      name: payload.name || '',
      role: auth.role,
    }),
  );

  if (payload.access_token) {
    sessionStorage.setItem(ACCESS_TOKEN_KEY, payload.access_token);
  }

  if (payload.refresh_token) {
    sessionStorage.setItem(REFRESH_TOKEN_KEY, payload.refresh_token);
  }
}

async function fetchWebLoginProfile(employeeNo, accessToken) {
  /* /login 응답만으로는 화면 권한(role)이 부족할 수 있어서,
     대시보드 진입 직전에 프로필을 한 번 더 조회해
     현재 사용자가 어떤 탭 권한을 가져야 하는지 확정한다. */
  if (!employeeNo) {
    throw new Error('사원번호를 확인할 수 없어 권한 정보를 불러오지 못했습니다.');
  }
  if (!accessToken) {
    throw new Error('로그인 토큰이 없어 사용자 권한 정보를 조회할 수 없습니다.');
  }

  const res = await fetch(`/api/v1/auth/web-login-profile/${encodeURIComponent(employeeNo)}`, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
    credentials: 'same-origin',
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(readErrorMessage(data, '사용자 권한 정보를 불러오지 못했습니다.'));
  }
  return data;
}

function redirectToDashboard() {
  window.location.replace('/web_dashboard.html');
}

function normalizeAuthMessage(message, fallback) {
  const value = String(message || '').trim();

  if (!value) {
    return fallback;
  }

  const lowered = value.toLowerCase();

  if (lowered === 'invalid employee number or password.') {
    return '아이디 또는 비밀번호가 틀렸습니다.';
  }
  if (lowered === 'this account has been deactivated.') {
    return '비활성화된 계정입니다. 관리자에게 문의해주세요.';
  }
  if (lowered === 'this account is locked. please contact hr_admin.') {
    return '잠긴 계정입니다. 관리자에게 문의해주세요.';
  }
  if (lowered.includes('face recognition') || lowered.includes('face login') || lowered.includes('face verification')) {
    return '얼굴 인식에 실패했습니다. 다시 시도해주세요.';
  }

  return value;
}

function normalizeUiMessage(message, fallback) {
  const value = String(message || '').trim();
  if (!value) {
    return fallback;
  }

  const lowered = value.toLowerCase();
  if (lowered === 'failed to fetch') {
    return '서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.';
  }
  if (lowered.includes('networkerror') || lowered.includes('load failed')) {
    return '네트워크 연결에 실패했습니다. 잠시 후 다시 시도해주세요.';
  }

  return value;
}

function readErrorMessage(payload, fallback) {
  /* 백엔드 에러 응답이 detail 또는 message 어느 필드로 오더라도
     화면에서는 한 경로로 읽어 사용자 친화적인 문구로 정리한다. */
  if (payload && typeof payload.detail === 'string' && payload.detail.trim()) {
    return normalizeAuthMessage(payload.detail.trim(), fallback);
  }
  if (payload && typeof payload.message === 'string' && payload.message.trim()) {
    return normalizeAuthMessage(payload.message.trim(), fallback);
  }
  return normalizeAuthMessage('', fallback);
}

function showError(msg) {
  /* web_login.html에는 고정 에러 박스를 두지 않고
     필요할 때만 동적으로 생성해 로그인 버튼 바로 아래에 붙인다.
     그래서 마크업을 단순하게 유지하면서도 오류 표시 위치는 일관된다. */
  let el = document.getElementById('login-error');
  if (!el) {
    el = document.createElement('p');
    el.id = 'login-error';
    el.style.cssText = [
      'color:#e11d48', 'font-size:12px', 'margin-top:10px',
      'padding:10px 14px', 'background:#fff1f2',
      'border:1px solid #fecdd3', 'border-radius:6px', 'text-align:center',
    ].join(';');
    loginBtn.after(el);
  }
  el.textContent = msg;
  el.style.display = 'block';
}

function clearError() {
  const el = document.getElementById('login-error');
  if (el) {
    el.style.display = 'none';
  }
}

/* ── 로그인 버튼 / 로딩 상태 ── */
function setLoading(on) {
  loginBtn.disabled = on;
  loginBtn.textContent = on ? '로그인 중...' : '로그인';
  loginBtn.style.opacity = on ? '0.7' : '1';
}

/* ── Face ID 시각 상태 / 카메라 상태 ── */
function setFaceVisualTone(mode) {
  const statusEl = document.getElementById('face-status');
  const descEl = document.getElementById('face-desc');
  const icon = document.querySelector('.face-icon');
  const strokes = icon ? icon.querySelectorAll('[stroke="#334155"]') : [];
  const fills = icon ? icon.querySelectorAll('[fill="#334155"]') : [];

  if (mode === 'error') {
    statusEl.style.color = '#e11d48';
    descEl.style.color = '#e11d48';
    if (icon) {
      icon.style.animationPlayState = 'paused';
    }
    strokes.forEach((el) => el.setAttribute('stroke', '#fca5a5'));
    fills.forEach((el) => el.setAttribute('fill', '#fca5a5'));
    return;
  }

  if (mode === 'active') {
    statusEl.style.color = '#334155';
    descEl.style.color = '#64748b';
    if (icon) {
      icon.style.animationPlayState = 'running';
    }
    strokes.forEach((el) => el.setAttribute('stroke', '#334155'));
    fills.forEach((el) => el.setAttribute('fill', '#334155'));
    return;
  }

  statusEl.style.color = '#94a3b8';
  descEl.style.color = '#94a3b8';
  if (icon) {
    icon.style.animationPlayState = 'paused';
  }
  strokes.forEach((el) => el.setAttribute('stroke', '#334155'));
  fills.forEach((el) => el.setAttribute('fill', '#334155'));
}

function setFaceStatus(message, desc = 'InsightFace가 자동으로 인식합니다.', mode = 'idle') {
  /* Face 로그인 영역은 한 줄짜리 텍스트보다
     "상태 + 보조 설명 + 시각 톤" 세 요소를 같이 바꿔야
     사용자가 현재 단계(대기/진행/실패)를 직관적으로 이해할 수 있다. */
  const statusEl = document.getElementById('face-status');
  const descEl = document.getElementById('face-desc');
  statusEl.textContent = message;
  descEl.textContent = desc;
  setFaceVisualTone(mode);
}

function isFaceTabActive() {
  const panel = document.getElementById('panel-face');
  return !!panel && panel.classList.contains('show');
}

function stopAutoFaceLogin() {
  if (faceAutoTimer) {
    clearInterval(faceAutoTimer);
    faceAutoTimer = null;
  }
}

function stopCamera() {
  if (cameraStream) {
    cameraStream.getTracks().forEach((track) => track.stop());
    cameraStream = null;
  }
  if (faceVideo) {
    faceVideo.srcObject = null;
  }
}

function buildCameraErrorMessage(error) {
  const name = error && error.name ? error.name : 'UnknownError';

  if (name === 'NotAllowedError' || name === 'SecurityError') {
    return '카메라 권한이 차단되었습니다. 브라우저에서 권한을 허용해주세요.';
  }
  if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
    return '사용 가능한 카메라 장치를 찾지 못했습니다.';
  }
  if (name === 'NotReadableError' || name === 'TrackStartError') {
    return '다른 앱에서 카메라를 사용 중입니다. 다른 앱을 종료한 뒤 다시 시도해주세요.';
  }
  if (name === 'OverconstrainedError' || name === 'ConstraintNotSatisfiedError') {
    return '요청한 카메라 설정을 지원하지 않습니다.';
  }
  return '카메라를 사용할 수 없습니다.';
}

async function startCamera() {
  /* 카메라 초기화는 한 번 성공하면 같은 stream을 재사용한다.
     탭 전환이나 버튼 연타 시 매번 getUserMedia를 다시 호출하지 않도록
     cameraStream 존재 여부를 먼저 확인한다. */
  if (!faceVideo) {
    return false;
  }

  if (cameraStream) {
    return true;
  }

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    setFaceStatus('카메라를 지원하지 않는 브라우저입니다.', 'Chrome 또는 Edge 최신 버전을 권장합니다.', 'error');
    return false;
  }

  if (!window.isSecureContext) {
    setFaceStatus('카메라는 HTTPS 또는 localhost 환경에서만 사용할 수 있습니다.', '현재 접속 환경을 확인해주세요.', 'error');
    return false;
  }

  try {
    // 브라우저/장치별 제약 차이를 고려해 점진적으로 느슨한 옵션으로 재시도한다.
    const constraintsList = [
      {
        video: {
          facingMode: { ideal: 'user' },
          frameRate: { ideal: MAX_CAMERA_FPS, max: MAX_CAMERA_FPS },
        },
        audio: false,
      },
      { video: { frameRate: { max: MAX_CAMERA_FPS } }, audio: false },
      { video: true, audio: false },
    ];

    let lastError = null;
    for (const constraints of constraintsList) {
      try {
        cameraStream = await navigator.mediaDevices.getUserMedia(constraints);
        break;
      } catch (error) {
        lastError = error;
      }
    }

    if (!cameraStream) {
      throw lastError || new Error('camera_start_failed');
    }

    faceVideo.srcObject = cameraStream;
    await faceVideo.play().catch(() => null);
    setFaceStatus('카메라가 연결되었습니다.', '정면을 바라보면 자동으로 얼굴 인식을 시도합니다.', 'active');
    return true;
  } catch (error) {
    setFaceStatus('카메라 연결에 실패했습니다.', buildCameraErrorMessage(error), 'error');
    return false;
  }
}

function waitForVideoReady(videoElement, timeoutMs = 2500) {
  /* getUserMedia가 성공해도 실제 video 프레임 크기(videoWidth/Height)가
     바로 준비되지 않을 수 있다. 이 함수는 loadedmetadata / loadeddata를 기다려
     "캡처 가능한 상태"가 되었는지 확인하는 안전장치다. */
  if (!videoElement) {
    return Promise.resolve(false);
  }
  if (videoElement.readyState >= 2 && videoElement.videoWidth > 0 && videoElement.videoHeight > 0) {
    return Promise.resolve(true);
  }

  return new Promise((resolve) => {
    let settled = false;

    function cleanup() {
      videoElement.removeEventListener('loadedmetadata', onReady);
      videoElement.removeEventListener('loadeddata', onReady);
    }

    function finish(ok) {
      if (settled) return;
      settled = true;
      cleanup();
      resolve(ok);
    }

    function onReady() {
      finish(videoElement.videoWidth > 0 && videoElement.videoHeight > 0);
    }

    videoElement.addEventListener('loadedmetadata', onReady);
    videoElement.addEventListener('loadeddata', onReady);

    setTimeout(() => {
      finish(videoElement.videoWidth > 0 && videoElement.videoHeight > 0);
    }, timeoutMs);
  });
}

function captureFrameAsBase64() {
  /* Face 인증 API는 현재 video 프레임을 JPEG base64 문자열로 받는다.
     따라서 video -> canvas -> dataURL 순서로 브라우저 내부에서 변환한다. */
  if (!faceVideo || !cameraStream) {
    return null;
  }
  const width = faceVideo.videoWidth;
  const height = faceVideo.videoHeight;
  if (!width || !height) {
    return null;
  }

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;

  const context = canvas.getContext('2d');
  if (!context) {
    return null;
  }

  context.drawImage(faceVideo, 0, 0, width, height);
  return canvas.toDataURL('image/jpeg', CAPTURE_QUALITY);
}

// 비밀번호 로그인과 얼굴 로그인이 모두 마지막에 합류하는 공통 후처리 지점이다.
async function finalizeLogin(payload, employeeNo) {
  /* 비밀번호 로그인과 얼굴 로그인이 모두 이 지점으로 모인다.
     즉, 로그인 방식과 무관하게
     "아이디 저장 -> 프로필 조회 -> 세션 저장 -> 대시보드 이동"
     후처리를 한 곳에서 일관되게 처리한다. */
  if (rememberChk.checked && employeeNo) {
    localStorage.setItem('sfp_saved_id', employeeNo);
  } else {
    localStorage.removeItem('sfp_saved_id');
  }

  const profile = await fetchWebLoginProfile(employeeNo, payload.access_token || '');
  saveDashboardSession({
    ...payload,
    employee_no: profile.employee_no || employeeNo,
    name: profile.name || '',
    role: profile.role || 'manager',
  });
  redirectToDashboard();
}

async function doLogin() {
  /* 아이디/비밀번호 로그인 메인 흐름
     1. 입력값 검사
     2. /auth/login 호출
     3. 성공 시 finalizeLogin으로 공통 후처리 */
  const id = empInput.value.trim();
  const pw = passwordInput.value;

  if (!id || !pw) {
    showError('사원번호와 비밀번호를 입력해주세요.');
    return;
  }

  clearError();
  setLoading(true);

  try {
    const res = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ employee_no: id, password: pw }),
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      showError(readErrorMessage(data, '로그인에 실패했습니다.'));
      return;
    }

    // 로그인 응답의 토큰만으로는 탭 권한 정보가 부족할 수 있어 프로필 조회를 한 번 더 한다.
    await finalizeLogin(data, id);
  } catch (err) {
    console.error('[Password Login Error]', err);
    showError(
      err instanceof Error
        ? normalizeUiMessage(err.message, '서버 연결에 실패했습니다. 잠시 후 다시 시도해주세요.')
        : '서버 연결에 실패했습니다. 잠시 후 다시 시도해주세요.',
    );
  } finally {
    setLoading(false);
  }
}

async function attemptFaceLogin(trigger = 'auto') {
  /* Face 로그인 메인 흐름
     1. 중복 요청 방지
     2. 카메라 준비 확인
     3. 프레임 준비 대기
     4. 이미지 캡처
     5. /auth/login/face 호출
     6. 성공 시 finalizeLogin 합류 */
  if (faceLoginInFlight || !isFaceTabActive()) {
    return false;
  }

  faceLoginInFlight = true;
  if (faceLoginBtn) {
    faceLoginBtn.disabled = true;
  }

  if (trigger !== 'auto') {
    setFaceStatus('카메라 준비 중입니다.', '잠시만 기다려주세요.', 'active');
  }

  try {
    // 얼굴 로그인은 카메라 준비 -> 프레임 확인 -> 캡처 -> 인증 API 호출 순서로 진행된다.
    const cameraReady = await startCamera();
    if (!cameraReady) {
      return false;
    }

    const videoReady = await waitForVideoReady(faceVideo);
    if (!videoReady) {
      setFaceStatus('카메라 프레임을 받지 못했습니다.', '카메라 시작 버튼을 눌러 다시 시도해주세요.', 'error');
      return false;
    }

    const imageBase64 = captureFrameAsBase64();
    if (!imageBase64) {
      setFaceStatus('얼굴 이미지를 캡처하지 못했습니다.', '다시 시도해주세요.', 'error');
      return false;
    }

    setFaceStatus('얼굴을 확인하고 있습니다.', '정면을 바라본 상태를 유지해주세요.', 'active');

    const res = await fetch('/api/v1/auth/login/face', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({
        employee_no: (faceEmployeeNoInput.value || empInput.value || '').trim() || null,
        image_base64: imageBase64,
      }),
    });

    const payload = await res.json().catch(() => ({}));
    if (!res.ok) {
      if (res.status === 401) {
        setFaceStatus('얼굴이 일치하지 않습니다.', '정면을 바라보고 다시 시도해주세요.', 'error');
        return false;
      }
      if (res.status === 404) {
        setFaceStatus('등록된 얼굴 정보가 없습니다.', '관리자에게 얼굴 등록을 요청해주세요.', 'error');
        return false;
      }
      if (res.status === 422) {
        setFaceStatus('얼굴을 인식하지 못했습니다.', '조명을 밝게 하고 다시 시도해주세요.', 'error');
        return false;
      }
      if (res.status === 503) {
        setFaceStatus('얼굴 인식 엔진이 준비 중입니다.', '잠시 후 다시 시도해주세요.', 'error');
        return false;
      }
      setFaceStatus('얼굴 로그인에 실패했습니다.', readErrorMessage(payload, '관리자에게 문의해주세요.'), 'error');
      return false;
    }

    if (!payload.verified || !payload.access_token) {
      setFaceStatus('얼굴 로그인에 실패했습니다.', readErrorMessage(payload, '다시 시도해주세요.'), 'error');
      return false;
    }

    stopAutoFaceLogin();
    setFaceStatus('인증에 성공했습니다.', '대시보드로 이동합니다.', 'active');
    await finalizeLogin(payload, payload.employee_no || '');
    return true;
  } catch (error) {
    console.error('[Face Login Error]', error);
    setFaceStatus(
      error instanceof Error
        ? normalizeUiMessage(error.message, '네트워크 또는 서버 연결 문제로 실패했습니다.')
        : '네트워크 또는 서버 연결 문제로 실패했습니다.',
      '잠시 후 다시 시도해주세요.',
      'error',
    );
    return false;
  } finally {
    faceLoginInFlight = false;
    if (faceLoginBtn) {
      faceLoginBtn.disabled = false;
    }
  }
}

function startAutoFaceLogin() {
  /* Face 탭이 열려 있는 동안 주기적으로 얼굴 인증을 재시도한다.
     사용자가 별도 버튼을 계속 누르지 않아도 되도록
     자동 루프와 수동 버튼 두 방식을 함께 제공하는 구조다. */
  if (faceAutoTimer || !isFaceTabActive()) {
    return;
  }

  // 탭이 열린 동안만 주기적으로 얼굴 인증을 재시도한다.
  faceAutoTimer = setInterval(() => {
    attemptFaceLogin('auto');
  }, AUTO_FACE_LOGIN_INTERVAL_MS);

  setTimeout(() => {
    attemptFaceLogin('auto');
  }, 500);
}

async function switchTab(type) {
  /* 탭 전환 시 단순 CSS 클래스만 바꾸는 것이 아니라
     Face 탭 진입 시 카메라 준비,
     ID 탭 복귀 시 카메라/타이머 정리까지 함께 수행한다. */
  const tabId = document.getElementById('tab-id');
  const tabFace = document.getElementById('tab-face');
  const panelId = document.getElementById('panel-id');
  const panelFace = document.getElementById('panel-face');

  if (type === 'id') {
    tabId.classList.add('active');
    tabFace.classList.remove('active');
    panelId.classList.remove('hide');
    panelFace.classList.remove('show');
    stopAutoFaceLogin();
    stopCamera();
    setFaceStatus('얼굴을 인증해주세요', 'InsightFace가 자동으로 인식합니다.', 'idle');
    return;
  }

  // Face 탭은 진입과 동시에 카메라 준비를 시작해 사용자가 바로 인증할 수 있게 한다.
  tabFace.classList.add('active');
  tabId.classList.remove('active');
  panelId.classList.add('hide');
  panelFace.classList.add('show');
  clearError();

  const cameraReady = await startCamera();
  if (cameraReady) {
    startAutoFaceLogin();
  }
}

loginBtn.addEventListener('click', doLogin);

/* HTML의 data-tab 속성과 JS의 switchTab 로직을 연결하는 바인딩이다.
   인라인 onclick 대신 여기서 연결해두면 마크업과 동작 분리가 깔끔해진다. */
document.querySelectorAll('[data-tab]').forEach((tabButton) => {
  tabButton.addEventListener('click', () => {
    switchTab(tabButton.dataset.tab);
  });
});

document.addEventListener('keydown', (e) => {
  if (e.key !== 'Enter') {
    return;
  }

  if (isFaceTabActive()) {
    attemptFaceLogin('manual');
    return;
  }

  doLogin();
});

if (faceStartBtn) {
  faceStartBtn.addEventListener('click', async () => {
    const cameraReady = await startCamera();
    if (cameraReady) {
      startAutoFaceLogin();
    }
  });
}

if (faceStopBtn) {
  faceStopBtn.addEventListener('click', () => {
    stopAutoFaceLogin();
    stopCamera();
    setFaceStatus('카메라를 중지했습니다.', '다시 시작하면 자동 얼굴 인식을 재개합니다.', 'idle');
  });
}

if (faceLoginBtn) {
  faceLoginBtn.addEventListener('click', async () => {
    await attemptFaceLogin('manual');
  });
}

if (rememberChk) {
  rememberChk.addEventListener('change', () => {
    if (rememberChk.checked) {
      const currentId = empInput.value.trim();
      if (currentId) {
        localStorage.setItem('sfp_saved_id', currentId);
      }
      return;
    }

    localStorage.removeItem('sfp_saved_id');
  });
}

window.addEventListener('DOMContentLoaded', () => {
  /* 새로고침 후에도 저장된 아이디를 복원하고,
     이미 로그인된 사용자는 곧바로 대시보드로 보내
     로그인 화면을 다시 거치지 않게 한다. */
  if (hasWebDashboardSession()) {
    redirectToDashboard();
    return;
  }

  // 저장된 사원번호는 두 로그인 방식에서 모두 재사용한다.
  const saved = localStorage.getItem('sfp_saved_id');
  if (saved) {
    empInput.value = saved;
    if (faceEmployeeNoInput) {
      faceEmployeeNoInput.value = saved;
    }
    rememberChk.checked = true;
  } else {
    rememberChk.checked = false;
    localStorage.removeItem('sfp_saved_id');
  }
  setFaceStatus('얼굴을 인증해주세요', 'InsightFace가 자동으로 인식합니다.', 'idle');
});

window.addEventListener('beforeunload', () => {
  // 다른 화면으로 이동할 때 카메라와 타이머를 정리하지 않으면 브라우저 권한 충돌이 날 수 있다.
  stopAutoFaceLogin();
  stopCamera();
});
