/*
 * login.js
 *
 * 역할 범위
 * - 이 파일은 on-device(PyQt) 로그인 흐름 전용 스크립트다.
 * - 진입 페이지: /login.html
 * - 로그인 성공 후 이동: /auto.html
 * - 세션 키: rss-auth / rss-access-token / rss-refresh-token
 *
 * 아래 웹 전용 흐름과는 분리되어 있다.
 * - /web_login.html
 * - /js/web_login/web_login.js
 * - /web_dashboard.html
 * 위 파일들은 브라우저 기반 web_dashboard 흐름에서 사용한다.
 */

/* ── DOM 참조 / 세션 키 ── */
const form = document.getElementById("login-form");
const errorEl = document.getElementById("login-error");
const employeeNoInput = document.getElementById("employee_no");
const faceEmployeeNoInput = document.getElementById("face_employee_no");
const faceVideo = document.getElementById("face-video");
const faceStatusEl = document.getElementById("face-status");
const cameraStartBtn = document.getElementById("camera-start");
const cameraStopBtn = document.getElementById("camera-stop");
const faceLoginBtn = document.getElementById("face-login");
const loginTabs = Array.from(document.querySelectorAll(".login-tab"));
const tabPanels = Array.from(document.querySelectorAll(".tab-panel"));
const ACCESS_TOKEN_KEY = "rss-access-token";
const REFRESH_TOKEN_KEY = "rss-refresh-token";
const USER_EMPLOYEE_NO_KEY = "rss-user-employee-no";
const USER_DISPLAY_NAME_KEY = "rss-user-display-name";

let cameraStream = null;
const MAX_CAMERA_FPS = 10;
const CAPTURE_QUALITY = 0.9;
const AUTO_FACE_LOGIN_INTERVAL_MS = 1800;

let autoFaceLoginTimer = null;
let faceLoginInFlight = false;

/* ── 공통 에러 / 세션 유틸 ── */
/* on-device 로그인은 웹 대시보드와 세션 저장 위치가 다르다.
 * 이 파일은 localStorage에 rss-* 키로 저장하고 /auto.html로 이동한다.
 * 즉, 브라우저 기반 web_dashboard 흐름과는 같은 로그인 API를 써도
 * 화면 후처리와 세션 키 체계는 완전히 분리되어 있다.
 */
const readErrorDetail = async (response) => {
  try {
    const payload = await response.json();
    if (typeof payload?.detail === "string" && payload.detail.trim()) {
      return payload.detail.trim();
    }
    if (typeof payload?.message === "string" && payload.message.trim()) {
      return payload.message.trim();
    }
  } catch (error) {
    // 응답 파싱이 실패하면 아래 기본 문구로 자연스럽게 떨어진다.
  }
  return "";
};

const storeAuthSession = (payload, fallbackEmployeeNo = "") => {
  /* 로그인 성공 시 다음 화면(auto.html)에서 바로 참조할 수 있도록
     인증 여부, 토큰, 사용자 식별 정보를 한 번에 저장한다.
     name이 없는 응답도 고려해 employee_no를 표시 이름 fallback으로 사용한다. */
  localStorage.setItem("rss-auth", "true");
  localStorage.setItem(USER_EMPLOYEE_NO_KEY, payload.employee_no || fallbackEmployeeNo);
  localStorage.setItem(
    USER_DISPLAY_NAME_KEY,
    payload.name || payload.employee_no || fallbackEmployeeNo,
  );

  if (payload.access_token) {
    localStorage.setItem(ACCESS_TOKEN_KEY, payload.access_token);
  }

  if (payload.refresh_token) {
    localStorage.setItem(REFRESH_TOKEN_KEY, payload.refresh_token);
  }
};

const waitForVideoReady = (videoElement, timeoutMs = 2500) => {
  /* 카메라 권한 허용 직후 바로 캡처를 시도하면
     video 메타데이터가 아직 준비되지 않아 빈 프레임이 잡힐 수 있다.
     그래서 loadedmetadata / loadeddata 이벤트 또는 timeout까지 기다린다. */
  if (!videoElement) {
    return Promise.resolve(false);
  }

  if (videoElement.readyState >= 2 && videoElement.videoWidth > 0 && videoElement.videoHeight > 0) {
    return Promise.resolve(true);
  }

  return new Promise((resolve) => {
    let settled = false;

    const cleanup = () => {
      videoElement.removeEventListener("loadedmetadata", onReady);
      videoElement.removeEventListener("loadeddata", onReady);
    };

    const finish = (ok) => {
      if (settled) {
        return;
      }
      settled = true;
      cleanup();
      resolve(ok);
    };

    const onReady = () => {
      const ok = videoElement.videoWidth > 0 && videoElement.videoHeight > 0;
      finish(ok);
    };

    videoElement.addEventListener("loadedmetadata", onReady);
    videoElement.addEventListener("loadeddata", onReady);

    setTimeout(() => {
      const ok = videoElement.videoWidth > 0 && videoElement.videoHeight > 0;
      finish(ok);
    }, timeoutMs);
  });
};

/* ── 카메라 / Face ID 상태 제어 ── */
const buildCameraErrorMessage = (error) => {
  const name = error && error.name ? error.name : "UnknownError";

  if (name === "NotAllowedError" || name === "SecurityError") {
    return "카메라 권한이 거부되었습니다. 브라우저 설정에서 카메라 접근을 허용해 주세요.";
  }

  if (name === "NotFoundError" || name === "DevicesNotFoundError") {
    return "이 시스템에서 카메라 장치를 찾을 수 없습니다.";
  }

  if (name === "NotReadableError" || name === "TrackStartError") {
    return "카메라가 다른 앱에서 이미 사용 중입니다. 해당 앱을 종료한 뒤 다시 시도해 주세요.";
  }

  if (name === "OverconstrainedError" || name === "ConstraintNotSatisfiedError") {
    return "요청한 카메라 모드를 지원하지 않습니다. 기본 카메라 설정으로 전환하는 데 실패했습니다.";
  }

  return "카메라 권한이 거부되었거나 사용할 수 없습니다.";
};

const setFaceStatus = (message, isError = false) => {
  /* on-device Face 로그인 화면은 설명 텍스트가 단순한 대신
     error 클래스를 통해 색상만 빠르게 바꿔 상태를 전달한다. */
  if (!faceStatusEl) {
    return;
  }

  faceStatusEl.textContent = message;
  faceStatusEl.classList.toggle("error", isError);
};

const isFaceTabActive = () => {
  const panel = document.getElementById("panel-face");
  return !!panel && !panel.hidden;
};

const stopAutoFaceLogin = () => {
  if (autoFaceLoginTimer) {
    clearInterval(autoFaceLoginTimer);
    autoFaceLoginTimer = null;
  }
};

const stopCamera = () => {
  /* 브라우저 카메라 stream을 닫지 않으면
     탭 전환/페이지 이동 후에도 장치 점유가 남을 수 있어
     stop() + srcObject 해제를 함께 수행한다. */
  if (cameraStream) {
    cameraStream.getTracks().forEach((track) => track.stop());
    cameraStream = null;
  }

  if (faceVideo) {
    faceVideo.srcObject = null;
  }
};

const startCamera = async () => {
  /* 장치/브라우저별 제약 조건 차이를 고려해
     선호 설정 -> 느슨한 설정 -> 완전 기본값 순으로 재시도한다.
     이렇게 해두면 고정된 한 가지 설정만 쓸 때보다 카메라 연결 성공률이 높아진다. */
  if (!faceVideo) {
    return false;
  }

  if (cameraStream) {
    return true;
  }

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    setFaceStatus("이 브라우저는 카메라 접근을 지원하지 않습니다.", true);
    return false;
  }

  if (!window.isSecureContext) {
    setFaceStatus("카메라 사용에는 HTTPS 또는 localhost가 필요합니다. 보안 컨텍스트에서 이 페이지를 열어 주세요.", true);
    return false;
  }

  try {
    const constraintsList = [
      {
        video: {
          facingMode: { ideal: "user" },
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
      throw lastError || new Error("camera_start_failed");
    }

    faceVideo.srcObject = cameraStream;
    await faceVideo.play().catch(() => {
      return null;
    });
    setFaceStatus("카메라가 준비되었습니다. Face ID로 로그인할 수 있습니다.");
    return true;
  } catch (error) {
    setFaceStatus(buildCameraErrorMessage(error), true);
    return false;
  }
};

const captureFrameAsBase64 = () => {
  /* 현재 video 프레임을 JPEG base64 문자열로 바꿔
     Face 인증 API의 image_base64 필드로 바로 보낼 수 있게 만든다. */
  if (!faceVideo || !cameraStream) {
    return null;
  }

  const width = faceVideo.videoWidth;
  const height = faceVideo.videoHeight;

  if (!width || !height) {
    return null;
  }

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;

  const context = canvas.getContext("2d");
  if (!context) {
    return null;
  }

  context.drawImage(faceVideo, 0, 0, width, height);
  return canvas.toDataURL("image/jpeg", CAPTURE_QUALITY);
};

/* ── Face ID 로그인 요청 ── */
const attemptFaceLogin = async ({ trigger = "auto" } = {}) => {
  /* Face 로그인 전체 흐름
     1. 중복 요청 방지
     2. Face 탭 활성 여부 확인
     3. 카메라 준비/프레임 준비
     4. 현재 프레임 캡처
     5. /auth/login/face 호출
     6. 성공 시 세션 저장 후 /auto.html 이동 */
  const isAuto = trigger === "auto";

  if (faceLoginInFlight) {
    return false;
  }

  if (!isFaceTabActive()) {
    return false;
  }

  faceLoginInFlight = true;
  if (faceLoginBtn) {
    faceLoginBtn.disabled = true;
  }

  if (!isAuto) {
    setFaceStatus("카메라를 준비하는 중입니다...");
  }

  const cameraReady = await startCamera();
  if (!cameraReady) {
    faceLoginInFlight = false;
    if (faceLoginBtn) {
      faceLoginBtn.disabled = false;
    }
    return false;
  }

  const videoReady = await waitForVideoReady(faceVideo);
  if (!videoReady) {
    setFaceStatus("카메라 프레임을 받지 못했습니다. 카메라 시작 버튼을 눌러 다시 시도해 주세요.", true);
    faceLoginInFlight = false;
    if (faceLoginBtn) {
      faceLoginBtn.disabled = false;
    }
    return false;
  }

  const imageBase64 = captureFrameAsBase64();
  if (!imageBase64) {
    setFaceStatus("얼굴 이미지를 캡처하지 못했습니다. 다시 시도해 주세요.", true);
    faceLoginInFlight = false;
    if (faceLoginBtn) {
      faceLoginBtn.disabled = false;
    }
    return false;
  }

  if (!isAuto) {
    setFaceStatus("Face ID 요청을 전송하는 중입니다...");
  }

  try {
    /* employee_no는 선택 입력이다.
       Face 전용 입력값이 있으면 우선 사용하고,
       없으면 일반 로그인 입력값을 fallback으로 같이 보낸다. */
    const response = await fetch("/api/v1/auth/login/face", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        employee_no: (faceEmployeeNoInput && faceEmployeeNoInput.value.trim()) || employeeNoInput.value.trim() || null,
        image_base64: imageBase64,
      }),
    });

    if (!response.ok) {
      const detail = await readErrorDetail(response);

      if (response.status === 401) {
        setFaceStatus(detail || "얼굴이 일치하지 않습니다. 정면을 바라보고 다시 시도해 주세요.", true);
        return false;
      }

      if (response.status === 404) {
        setFaceStatus(detail || "등록된 Face ID가 없습니다. 관리자에게 등록을 요청해 주세요.", true);
        return false;
      }

      if (response.status === 422) {
        setFaceStatus(detail || "얼굴을 인식하지 못했습니다. 조명을 밝게 하고 다시 시도해 주세요.", true);
        return false;
      }

      if (response.status === 503) {
        setFaceStatus(detail || "얼굴 인식 엔진 준비 중입니다. 잠시 후 다시 시도해 주세요.", true);
        return false;
      }

      setFaceStatus(
        detail || `얼굴 로그인에 실패했습니다 (HTTP ${response.status}). 관리자에게 문의해 주세요.`,
        true
      );
      return false;
    }

    const payload = await response.json();
    if (!payload.verified || !payload.access_token) {
      setFaceStatus(payload.message || "얼굴 인증에 실패했습니다.", true);
      return false;
    }

    stopAutoFaceLogin();
    storeAuthSession(
      payload,
      ((faceEmployeeNoInput && faceEmployeeNoInput.value.trim()) || employeeNoInput.value.trim())
    );
    setFaceStatus("얼굴 인증에 성공했습니다. 페이지를 이동합니다...");
    window.location.href = "/auto.html";
    return true;
  } catch (error) {
    const message =
      error && typeof error.message === "string" && error.message.trim()
        ? error.message.trim()
        : "네트워크 또는 서버 연결 문제로 Face ID 요청에 실패했습니다.";

    setFaceStatus(message, true);
    return false;
  } finally {
    faceLoginInFlight = false;
    if (faceLoginBtn) {
      faceLoginBtn.disabled = false;
    }
  }
};

/* ── 탭 전환 / 자동 Face ID 루프 ── */
const startAutoFaceLogin = () => {
  /* Face 탭이 켜진 동안만 자동 인증 루프를 돌린다.
     카메라를 켜자마자 첫 시도를 짧게 한 번 실행하고,
     이후에는 일정 주기로 재시도한다. */
  if (autoFaceLoginTimer || !isFaceTabActive()) {
    return;
  }

  setFaceStatus("자동 얼굴 인식을 시작합니다.");
  autoFaceLoginTimer = setInterval(() => {
    attemptFaceLogin({ trigger: "auto" });
  }, AUTO_FACE_LOGIN_INTERVAL_MS);

  setTimeout(() => {
    attemptFaceLogin({ trigger: "auto" });
  }, 500);
};

const setActiveLoginTab = async (targetPanelId) => {
  /* 탭 전환은 버튼 상태, 패널 표시, aria-selected,
     그리고 Face 탭의 카메라/자동인식 생명주기를 함께 맞춰야 한다. */
  const isFaceTab = targetPanelId === "panel-face";

  loginTabs.forEach((tab) => {
    const isActive = tab.dataset.target === targetPanelId;
    tab.classList.toggle("is-active", isActive);
    tab.setAttribute("aria-selected", isActive ? "true" : "false");
  });

  tabPanels.forEach((panel) => {
    const isActive = panel.id === targetPanelId;
    panel.classList.toggle("is-active", isActive);
    panel.hidden = !isActive;
  });

  if (isFaceTab) {
    const cameraReady = await startCamera();
    if (cameraReady) {
      startAutoFaceLogin();
    }
  } else {
    stopAutoFaceLogin();
    stopCamera();
  }
};

/* ── 이벤트 바인딩 ── */
loginTabs.forEach((tab) => {
  /* 각 탭 버튼의 data-target 값은 실제 패널 id와 1:1로 연결된다. */
  tab.addEventListener("click", async () => {
    const target = tab.dataset.target;
    if (!target) {
      return;
    }
    await setActiveLoginTab(target);
  });
});

if (form) {
  form.addEventListener("submit", async (event) => {
    /* on-device 기본 로그인 흐름
       - 입력 검증
       - /auth/login 호출
       - 성공 시 rss-* 세션 저장
       - /auto.html 이동 */
    event.preventDefault();

    const employeeNo = employeeNoInput.value.trim();
    const password = document.getElementById("password").value;

    if (!employeeNo || !password) {
      errorEl.textContent = "사번과 비밀번호를 모두 입력해 주세요.";
      return;
    }

    errorEl.textContent = "";

    try {
      const response = await fetch("/api/v1/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          employee_no: employeeNo,
          password,
        }),
      });

      if (!response.ok) {
        if (response.status === 401) {
          errorEl.textContent = "사번 또는 비밀번호가 올바르지 않습니다.";
          return;
        }

        errorEl.textContent = "로그인 요청에 실패했습니다. 다시 시도해 주세요.";
        return;
      }

      const payload = await response.json();
      storeAuthSession(payload, employeeNo);
      window.location.href = "/auto.html";
    } catch (error) {
      errorEl.textContent = "로그인 요청에 실패했습니다. 서버 상태를 확인해 주세요.";
    }
  });
}

if (cameraStartBtn) {
  cameraStartBtn.addEventListener("click", async () => {
    const cameraReady = await startCamera();
    if (cameraReady) {
      startAutoFaceLogin();
    }
  });
}

if (cameraStopBtn) {
  cameraStopBtn.addEventListener("click", () => {
    stopAutoFaceLogin();
    stopCamera();
    setFaceStatus("카메라를 중지했습니다.");
  });
}

if (faceLoginBtn) {
  faceLoginBtn.addEventListener("click", async () => {
    await attemptFaceLogin({ trigger: "manual" });
  });
}

window.addEventListener("DOMContentLoaded", async () => {
  /* 진입 시 기본 탭은 아이디/비밀번호 로그인으로 맞춘다.
     이 시점에 Face 탭을 기본값으로 두지 않는 이유는
     페이지 진입 직후 카메라 권한 팝업이 갑자기 뜨는 경험을 피하기 위해서다. */
  await setActiveLoginTab("panel-password");
});

window.addEventListener("beforeunload", () => {
  /* 페이지 이탈 시 카메라/타이머를 정리해 장치 점유가 남지 않게 한다. */
  stopAutoFaceLogin();
  stopCamera();
});
