/*
 * 온디바이스(PyQt) 공통 프론트 모듈
 *
 * 이 파일은 아래 on-device 페이지에서 공통으로 사용한다.
 * - /iot.html
 * - /configuration.html
 * - /model.html
 * - /auto.html
 * - /manual.html
 *
 * 아래 web_dashboard 흐름의 활성 인증/세션 계층은 아니다.
 * - /web_login.html
 * - /web_dashboard.html
 *
 * web_dashboard 쪽은 아래 세션 체계를 사용한다.
 * - localStorage key: dashboard_auth_v1
 * - sessionStorage keys: sfp_access_token / sfp_refresh_token
 * - redirect path: /web_login.html
 *
 * 반대로 on-device 쪽은 아래 세션 체계를 사용한다.
 * - localStorage key: rss-auth
 * - localStorage keys: rss-access-token / rss-refresh-token
 * - redirect path: /login.html
 *
 * 즉 이 파일은 PyQt/on-device 기준선으로 유지하고,
 * web_login/web_dashboard 구현 기준으로는 사용하지 않는다.
 */
console.warn(
  "[ondevice] /js/dashboard.js loaded. 이 파일은 PyQt/on-device 흐름 전용이며 web_login/web_dashboard 흐름에는 포함되지 않습니다."
);

const isAuthenticated = localStorage.getItem("rss-auth") === "true";
const ACCESS_TOKEN_KEY = "rss-access-token";
const REFRESH_TOKEN_KEY = "rss-refresh-token";
const USER_EMPLOYEE_NO_KEY = "rss-user-employee-no";
const USER_DISPLAY_NAME_KEY = "rss-user-display-name";

if (!isAuthenticated) {
  window.location.replace("/login.html");
}

const getAuthHeaders = (extraHeaders = {}) => {
  const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
  if (!accessToken) {
    return { ...extraHeaders };
  }

  return {
    ...extraHeaders,
    Authorization: `Bearer ${accessToken}`,
  };
};

let refreshTokenInFlight = null;
let logoutInFlight = null;

const clearAuthSession = () => {
  localStorage.removeItem("rss-auth");
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_EMPLOYEE_NO_KEY);
  localStorage.removeItem(USER_DISPLAY_NAME_KEY);
};

const logoutAndRedirect = async () => {
  if (logoutInFlight) {
    return logoutInFlight;
  }

  logoutInFlight = (async () => {
    try {
      const response = await authFetch(
        "/api/v1/auth/logout",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        },
        false
      );

      if (!response.ok) {
        console.warn("On-device logout API returned non-OK status:", response.status);
      }
    } catch (error) {
      console.warn("On-device logout API request failed:", error);
    } finally {
      clearAuthSession();
      window.location.replace("/login.html");
    }
  })();

  return logoutInFlight;
};

const refreshAccessToken = async () => {
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
  if (!refreshToken) {
    return false;
  }

  if (refreshTokenInFlight) {
    return refreshTokenInFlight;
  }

  refreshTokenInFlight = (async () => {
    try {
      const response = await fetch("/api/v1/auth/refresh", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!response.ok) {
        return false;
      }

      const payload = await response.json();
      if (!payload || !payload.access_token) {
        return false;
      }

      localStorage.setItem(ACCESS_TOKEN_KEY, payload.access_token);
      return true;
    } catch (error) {
      console.error("Access token refresh failed:", error);
      return false;
    } finally {
      refreshTokenInFlight = null;
    }
  })();

  return refreshTokenInFlight;
};

const authFetch = async (url, options = {}, retryOnUnauthorized = true) => {
  const headers = {
    ...(options.headers || {}),
  };

  if (!headers.Authorization) {
    Object.assign(headers, getAuthHeaders());
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status !== 401 || !retryOnUnauthorized) {
    return response;
  }

  const refreshed = await refreshAccessToken();
  if (!refreshed) {
    clearAuthSession();
    window.location.replace("/login.html");
    return response;
  }

  const retryHeaders = {
    ...headers,
    ...getAuthHeaders(),
  };

  return fetch(url, {
    ...options,
    headers: retryHeaders,
  });
};

const modeButtons = Array.from(document.querySelectorAll(".menu-btn[data-mode]"));
const workerNameElements = Array.from(document.querySelectorAll(".worker-name"));
const simplePanel = document.getElementById("simple-panel");
const manualPanel = document.getElementById("manual-panel");
const iotPanel = document.getElementById("iot-panel");
const logoutBtn = document.getElementById("logout-btn");
const askForm = document.querySelector(".ask-form");
const askInput = document.querySelector(".ask-input");
const askToolsMenu = askForm?.querySelector(".ask-tools-menu") || null;
const askUploadBtn = askForm?.querySelector(".ask-upload-btn") || null;
const askUploadInput = askForm?.querySelector(".ask-upload-input") || null;
const chatbotDisplay = document.getElementById("chatbot-display");
const simpleQuestionList = document.getElementById("simple-question-list");
const handoverBoards = Array.from(document.querySelectorAll(".handover-board"));
const askSendBtn = document.querySelector(".ask-send-btn");
const micBtn = document.getElementById("mic-btn");
const stopTtsBtn = document.getElementById("stop-tts-btn");
const ttsToggle = document.getElementById("tts-toggle");
const sttToggle = document.getElementById("stt-toggle");
const webSearchToggle = document.getElementById("web-search-toggle");
const chatTabButtons = Array.from(document.querySelectorAll(".chat-tab[data-chat-tab]"));
const chatTabPanels = Array.from(document.querySelectorAll("[data-chat-panel]"));
const configTabButtons = Array.from(document.querySelectorAll("[data-config-tab]"));
const configTabPanels = Array.from(document.querySelectorAll("[data-config-panel]"));
const configDefaultPanel =
  document.querySelector('[data-config-panel="basic-setting"]') ||
  document.querySelector('[data-config-panel="question"]');
const faceVideo = document.getElementById("face-video");
const faceCameraStatus = document.getElementById("face-camera-status");
const faceAccountKeywordInput = document.getElementById("face-account-keyword");
const faceAccountListBody = document.getElementById("face-account-list-body");
const faceRegistrationSummary = document.getElementById("face-registration-summary");
const faceSelectedEmployee = document.getElementById("face-selected-employee");
const faceRegisterBtn = document.getElementById("face-register-btn");

const cameraVideo = document.getElementById("camera-video");
const cameraOverlayStream = document.getElementById("camera-overlay-stream");
const cameraPlaceholder = document.getElementById("camera-placeholder");
const cameraCanvas = document.getElementById("camera-canvas");
const cameraStartBtn = document.getElementById("camera-start-btn");
const cameraStopBtn = document.getElementById("camera-stop-btn");
const cameraShotBtn = document.getElementById("camera-shot-btn");
const cameraStatus = document.getElementById("camera-status");
const cameraResolution = document.getElementById("camera-resolution");
const overlayOkCount = document.getElementById("overlay-ok-count");
const overlayNgCount = document.getElementById("overlay-ng-count");
const signalRed = document.getElementById("signal-red");
const signalYellow = document.getElementById("signal-yellow");
const signalGreen = document.getElementById("signal-green");
const logDisplay = document.getElementById("log-display");

let cameraStream = null;
let faceCameraStream = null;
let visionUploadTimer = null;
let visionOverlayCountTimer = null;
let visionFrameUploadInFlight = false;
let onpremOverlayRetryTimer = null;
let onpremNoCameraLogMuted = false;
const onpremOverlayFailureLogMuted = new Set();
let previousOkCount = 0;
let previousNgCount = 0;
let previousSignalType = "standby";
let previousCameraMessage = "";
let faceRegistrationSearchTimer = null;
let handoverStatusResetTimer = null;
let selectedEmployeeNo = "";
let lastFaceRegistrationItems = [];
let activeChatController = null;
let mediaRecorder = null;
let currentMicStream = null;
let audioChunks = [];
let currentTtsAudio = null;
let ttsQueue = Promise.resolve();
let ttsSessionToken = 0;
let sttAudioContext = null;
let sttAnalyser = null;
let sttMonitorId = null;
let sttLastVoiceAt = 0;
let sttRecordStartedAt = 0;
let sttEnabled = true;
let skipNextStt = false;
const simpleSessionHistory = new Map();
let latestChatSources = [];
let sourcePopupAnchor = null;
let sourcePopupButton = null;
let sourcePopupModal = null;
let sourcePopupList = null;
let chatThread = null;
let currentWorkerDisplayName =
  localStorage.getItem(USER_DISPLAY_NAME_KEY) || localStorage.getItem(USER_EMPLOYEE_NO_KEY) || "";

const LOG_MAX_LINES = 90;
const LANGUAGE_STORAGE_KEY = "rss-ui-language";
const STT_ENABLED_KEY = "rss-stt-enabled";
const TTS_ENABLED_KEY = "rss-tts-enabled";
const WEB_SEARCH_ENABLED_KEY = "rss-web-search-enabled";
const HANDOVER_STATUS_TIMEOUT_MS = 5000;
const VISION_CAMERA_ID_KEY = "rss-vision-camera-id";
const VISION_CAMERA_TOKEN_KEY = "rss-vision-camera-token";
const VISION_TARGET_CAMERA_ID_KEY = "rss-vision-target-camera-id";
const ONPREM_STREAM_URL_KEY = "rss-onprem-stream-url";

const DEFAULT_SIMPLE_QUESTIONS = {
  ko: [
    "이 장비는 작업을 시작하려면 어떤 순서로 조작해야 하나요?",
    "작업 중 에러가 발생하면 어떻게 조치해야 하나요?",
    "제품 종류에 따라 어떤 설정 값을 바꿔야 하나요?",
  ],
  en: [
    "What is the startup sequence for this equipment?",
    "What should I do first when an error occurs during operation?",
    "Which settings should be changed for a different product type?",
  ],
};

const getLogTimestamp = () => {
  const now = new Date();
  const pad = (value) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
};

const appendLog = (level, message) => {
  if (!(logDisplay instanceof HTMLTextAreaElement)) {
    return;
  }

  const entry = `[${level}] ${getLogTimestamp()} ${message}`;
  const existing = logDisplay.value.trim();
  const lines = existing ? existing.split("\n") : [];
  lines.push(entry);

  if (lines.length > LOG_MAX_LINES) {
    lines.splice(0, lines.length - LOG_MAX_LINES);
  }

  logDisplay.value = lines.join("\n");
  logDisplay.scrollTop = logDisplay.scrollHeight;
};

const appendOnpremOverlayFailureLogOnce = (muteKey, message) => {
  if (onpremOverlayFailureLogMuted.has(muteKey)) {
    return;
  }
  appendLog("VISION", message);
  onpremOverlayFailureLogMuted.add(muteKey);
};

const resetOnpremOverlayFailureLogMute = () => {
  onpremOverlayFailureLogMuted.clear();
};

const getLegacyGetUserMedia = () => {
  return (
    navigator.getUserMedia ||
    navigator.webkitGetUserMedia ||
    navigator.mozGetUserMedia ||
    navigator.msGetUserMedia ||
    null
  );
};

const requestCameraStream = async (constraints) => {
  if (navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === "function") {
    return navigator.mediaDevices.getUserMedia(constraints);
  }

  const legacyGetUserMedia = getLegacyGetUserMedia();
  if (!legacyGetUserMedia) {
    throw new Error("GET_USER_MEDIA_UNAVAILABLE");
  }

  return new Promise((resolve, reject) => {
    legacyGetUserMedia.call(navigator, constraints, resolve, reject);
  });
};

const MODE_ROUTE_MAP = {
  model: "/model.html",
  configuration: "/configuration.html",
  auto: "/auto.html",
  manual: "/manual.html",
  iot: "/iot.html",
};

const currentPath = window.location.pathname;
const currentMode =
  Object.keys(MODE_ROUTE_MAP).find((mode) => MODE_ROUTE_MAP[mode] === currentPath) || "model";
const HANDOVER_STORAGE_KEY = `rss-handover-${currentMode}`;
const HANDOVER_MIN_ROWS = 5;
const HANDOVER_MAX_ROWS = 12;

const openResultPopup = () => {
  const popup = window.open("", "rss-result-popup", "width=980,height=760,resizable=yes,scrollbars=yes");
  if (!popup) {
    appendLog("ERROR", "Result popup blocked by browser");
    return;
  }

  const setPopupCardText = (id, text) => {
    if (!popup || popup.closed || !popup.document) {
      return;
    }
    const el = popup.document.getElementById(id);
    if (!el) {
      return;
    }
    el.textContent = text;
    el.classList.remove("loading");
  };

  const renderSummary = (summary) => {
    const total = Number(summary && summary.total ? summary.total : 0);
    const ok = Number(summary && summary.ok ? summary.ok : 0);
    const ng = Number(summary && summary.ng ? summary.ng : 0);
    const yieldPct = Number(summary && summary.yield_pct ? summary.yield_pct : 0).toFixed(2);
    return [
      "Summary",
      "-------------------------",
      `Total : ${total}`,
      `OK : ${ok}`,
      `NG : ${ng}`,
      "",
      `Yield : ${yieldPct} %`,
    ].join("\n");
  };

  const renderNgDistribution = (items) => {
    const rows = Array.isArray(items) ? items : [];
    if (!rows.length) {
      return ["NG Distribution", "-------------------------", "No NG records"].join("\n");
    }
    const lines = rows.map((row) => `${String(row && row.defect_type ? row.defect_type : "unknown")} : ${Number(row && row.count ? row.count : 0)}`);
    return ["NG Distribution", "-------------------------", ...lines].join("\n");
  };

  const renderModel = (model) => {
    return [
      "Model",
      "-------------------------",
      `Model ID : ${String((model && model.model_id) || "N/A")}`,
      `Model Name : ${String((model && model.model_name) || "N/A")}`,
      `Unit : ${String((model && model.unit) || "N/A")}`,
      `Alert Threshold : ${String(model && model.alert_threshold != null ? model.alert_threshold : "N/A")}`,
      `Danger Threshold : ${String(model && model.danger_threshold != null ? model.danger_threshold : "N/A")}`,
    ].join("\n");
  };

  const renderSystem = (system) => {
    return [
      "System",
      "-------------------------",
      `Camera : ${String((system && system.camera_status) || "N/A")}`,
      `Camera Resolution : ${String((system && system.camera_resolution) || "N/A")}`,
      `AI Model : ${String((system && system.ai_model) || "N/A")}`,
      `Data Date : ${String((system && system.data_date) || "N/A")}`,
    ].join("\n");
  };

  const renderPopupError = (message) => {
    const text = [
      "Failed to load DB data.",
      "-------------------------",
      message || "Unknown error",
    ].join("\n");
    setPopupCardText("summary-content", text);
    setPopupCardText("ng-content", text);
    setPopupCardText("model-content", text);
    setPopupCardText("system-content", text);
  };

  const toIsoDate = (value) => {
    if (!(value instanceof Date) || Number.isNaN(value.getTime())) {
      return "";
    }
    const pad = (num) => String(num).padStart(2, "0");
    return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
  };

  const buildReportUrl = (path, selectedDate) => {
    const dateText = String(selectedDate || "").trim();
    if (!dateText) {
      return path;
    }
    const params = new URLSearchParams({ target_date: dateText });
    return `${path}?${params.toString()}`;
  };

  const html = `<!DOCTYPE html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Result</title>
    <style>
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: "Space Grotesk", "Segoe UI", sans-serif;
        background:
          radial-gradient(circle at 20% 10%, rgba(34, 211, 160, 0.08) 0%, transparent 35%),
          radial-gradient(circle at 85% 30%, rgba(207, 79, 45, 0.08) 0%, transparent 42%),
          linear-gradient(145deg, #060c14, #0b111b);
        color: #e2ecff;
      }
      .top {
        height: 58px;
        border: 1px solid rgba(23, 32, 48, 0.35);
        border-radius: 12px;
        background: #0c1520;
        display: grid;
        grid-template-columns: 1fr auto;
        align-items: center;
        padding: 0 12px;
        margin: 14px 14px 0;
      }
      .title {
        text-align: center;
        font-size: 2rem;
        font-weight: 700;
        color: #e2ecff;
      }
      .icons { display: flex; gap: 4px; }
      .result-filter {
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .result-filter input[type="date"] {
        height: 38px;
        border-radius: 8px;
        border: 1px solid rgba(34, 211, 160, 0.25);
        background: #111b2a;
        color: #e2ecff;
        padding: 0 10px;
      }
      .result-filter button {
        height: 38px;
        border-radius: 8px;
        border: 1px solid rgba(34, 211, 160, 0.35);
        background: #173042;
        color: #e2ecff;
        padding: 0 12px;
        cursor: pointer;
      }
      .result-filter button:hover {
        background: #1f3d54;
      }
      .pdf-btn {
        width: 52px;
        height: 52px;
        border: 1px solid rgba(34, 211, 160, 0.22);
        border-radius: 6px;
        background: #111b2a;
        padding: 2px;
        cursor: pointer;
      }
      .pdf-btn:hover {
        background: #1a2638;
      }
      .pdf-icon {
        width: 48px;
        height: 48px;
        object-fit: contain;
        display: block;
      }
      .wrap {
        padding: 14px;
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
      }
      .card {
        min-height: 290px;
        border-radius: 12px;
        background: #0c1520;
        border: 1px solid rgba(23, 32, 48, 0.35);
      }
      .card h2 {
        margin: 0;
        background: #1e2d40;
        color: #e2ecff;
        padding: 8px 14px;
        font-size: 2rem;
      }
      .content {
        white-space: pre-line;
        padding: 16px;
        font-size: 1.45rem;
        line-height: 1.35;
        color: #e2ecff;
      }
      .loading {
        color: #8ea4c7;
      }
    </style>
  </head>
  <body>
    <div class="top">
      <div class="title">Result</div>
      <div class="icons">
        <div class="result-filter">
          <input id="result-date" type="date" aria-label="조회 날짜" />
          <button id="result-date-apply" type="button">조회</button>
        </div>
        <button id="result-pdf-btn" class="pdf-btn" type="button" title="PDF 다운로드">
          <img class="pdf-icon" src="/source/pdf.png" alt="PDF" />
        </button>
      </div>
    </div>
    <div class="wrap">
      <section class="card"><h2>Summary</h2><div id="summary-content" class="content loading">Loading...</div></section>
      <section class="card"><h2>NG Distribution</h2><div id="ng-content" class="content loading">Loading...</div></section>
      <section class="card"><h2>Model</h2><div id="model-content" class="content loading">Loading...</div></section>
      <section class="card"><h2>System</h2><div id="system-content" class="content loading">Loading...</div></section>
    </div>
  </body>
</html>`;

  popup.document.open();
  popup.document.write(html);
  popup.document.close();
  popup.focus();

  const dateInput = popup.document.getElementById("result-date");
  const applyBtn = popup.document.getElementById("result-date-apply");
  const pdfBtn = popup.document.getElementById("result-pdf-btn");
  const defaultDate = toIsoDate(new Date());
  if (dateInput) {
    dateInput.value = defaultDate;
  }

  const fetchResultSummary = () => {
    const selectedDate = dateInput ? dateInput.value : "";
    setPopupCardText("summary-content", "Loading...");
    setPopupCardText("ng-content", "Loading...");
    setPopupCardText("model-content", "Loading...");
    setPopupCardText("system-content", "Loading...");

    fetch(buildReportUrl("/api/v1/report/result-summary", selectedDate))
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        return response.json();
      })
      .then((payload) => {
        setPopupCardText("summary-content", renderSummary(payload.summary));
        setPopupCardText("ng-content", renderNgDistribution(payload.ng_distribution));
        setPopupCardText("model-content", renderModel(payload.model));
        setPopupCardText("system-content", renderSystem(payload.system));
      })
      .catch((error) => {
        renderPopupError(error && error.message ? error.message : "Network error");
      });
  };

  if (applyBtn) {
    applyBtn.addEventListener("click", fetchResultSummary);
  }
  if (dateInput) {
    dateInput.addEventListener("change", fetchResultSummary);
  }
  if (pdfBtn) {
    pdfBtn.addEventListener("click", () => {
      const selectedDate = dateInput ? dateInput.value : "";
      popup.open(buildReportUrl("/api/v1/report/pdf", selectedDate), "_blank");
    });
  }

  fetchResultSummary();

  appendLog("NAV", "Result popup opened");
};

const setMode = (mode) => {
  const showManual = mode === "manual" || mode === "auto";
  const showIot = mode === "iot";

  modeButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.mode === mode);
  });

  if (manualPanel) {
    manualPanel.hidden = !showManual;
  }

  if (iotPanel) {
    iotPanel.hidden = !showIot;
  }

  if (simplePanel) {
    simplePanel.hidden = showManual || showIot;
  }
};

const setWorkerNameLabel = (displayName) => {
  if (!displayName) {
    return;
  }

  workerNameElements.forEach((element) => {
    element.textContent = `작업자 : ${displayName}`;
  });
};

const setCurrentWorkerDisplayName = (displayName, { persist = false } = {}) => {
  const normalized = String(displayName || "").trim();
  if (!normalized) {
    return;
  }

  currentWorkerDisplayName = normalized;
  if (persist) {
    localStorage.setItem(USER_DISPLAY_NAME_KEY, normalized);
  }
  setWorkerNameLabel(normalized);
  syncHandoverForms();
};

const loadWorkerNameFromDb = async () => {
  const employeeNo = localStorage.getItem(USER_EMPLOYEE_NO_KEY);
  if (!employeeNo) {
    return;
  }

  // Show employee number immediately while waiting for DB name lookup.
  setCurrentWorkerDisplayName(employeeNo, { persist: true });

  try {
    const response = await authFetch(`/api/v1/auth/users/${encodeURIComponent(employeeNo)}`);
    if (!response.ok) {
      return;
    }

    const payload = await response.json();
    setCurrentWorkerDisplayName(payload.name || payload.employee_no || employeeNo, { persist: true });
  } catch (error) {
    console.error("Failed to load worker name:", error);
  }
};

const setCameraMessage = (text) => {
  if (cameraStatus) {
    cameraStatus.textContent = `Status : ${text}`;
  }

  if (text !== previousCameraMessage) {
    appendLog("CAM", text);
    previousCameraMessage = text;
  }
};

const getVisionCameraId = () => {
  const cached = localStorage.getItem(VISION_CAMERA_ID_KEY);
  if (cached) {
    return cached;
  }

  const employeeNo = localStorage.getItem("rss-user-employee-no") || "anon";
  const randomSuffix = Math.random().toString(36).slice(2, 10);
  const cameraId = `onprem-${employeeNo}-${randomSuffix}`.replace(/[^a-zA-Z0-9-_]/g, "_").slice(0, 64);
  localStorage.setItem(VISION_CAMERA_ID_KEY, cameraId);
  return cameraId;
};

const getVisionCameraToken = () => {
  return localStorage.getItem(VISION_CAMERA_TOKEN_KEY) || "onprem-camera-token";
};

const getTargetOnpremCameraId = () => {
  const params = new URLSearchParams(window.location.search);
  const fromQuery = (params.get("camera_id") || params.get("cameraId") || params.get("stream_id") || "").trim();
  if (fromQuery) {
    localStorage.setItem(VISION_TARGET_CAMERA_ID_KEY, fromQuery);
    return fromQuery;
  }

  const fromStorage = (localStorage.getItem(VISION_TARGET_CAMERA_ID_KEY) || "").trim();
  return fromStorage;
};

const withCacheBust = (url) => {
  const raw = String(url || "").trim();
  if (!raw) {
    return "";
  }
  const sep = raw.includes("?") ? "&" : "?";
  return `${raw}${sep}ts=${Date.now()}`;
};

const getOnpremDirectStreamUrl = () => {
  const params = new URLSearchParams(window.location.search);
  const fromQuery = (params.get("stream_url") || params.get("onprem_stream_url") || "").trim();
  if (fromQuery) {
    localStorage.setItem(ONPREM_STREAM_URL_KEY, fromQuery);
    return fromQuery;
  }

  return (localStorage.getItem(ONPREM_STREAM_URL_KEY) || "").trim();
};

const fetchLatestOnpremCameraId = async (preferredCameraId = "") => {
  try {
    const response = await fetch("/api/v1/vision/cameras", { cache: "no-store" });
    if (!response.ok) {
      return "";
    }

    const payload = await response.json();
    const items = Array.isArray(payload.items) ? payload.items : [];
    if (items.length === 0) {
      return "";
    }

    const normalizedPreferred = String(preferredCameraId || "").trim();
    if (normalizedPreferred) {
      const preferredItem = items.find((item) => String(item?.camera_id || "").trim() === normalizedPreferred);
      if (preferredItem) {
        const preferredUpdated = Number(preferredItem?.updated_at || preferredItem?.device?.last_frame_at || 0);
        if (preferredUpdated > 0) {
          localStorage.setItem(VISION_TARGET_CAMERA_ID_KEY, normalizedPreferred);
          return normalizedPreferred;
        }
      }
    }

    const sorted = [...items].sort((a, b) => {
      const aUpdated = Number(a?.updated_at || a?.device?.last_frame_at || 0);
      const bUpdated = Number(b?.updated_at || b?.device?.last_frame_at || 0);
      return bUpdated - aUpdated;
    });

    const candidate = String(sorted[0]?.camera_id || "").trim();
    if (!candidate) {
      return "";
    }

    localStorage.setItem(VISION_TARGET_CAMERA_ID_KEY, candidate);
    return candidate;
  } catch (error) {
    console.error("Failed to fetch active on-prem camera list:", error);
    return "";
  }
};

const detectClientOs = () => {
  const ua = navigator.userAgent || "";
  if (/Windows/i.test(ua)) {
    return "Windows";
  }
  if (/Mac OS X|Macintosh/i.test(ua)) {
    return "macOS";
  }
  if (/Android/i.test(ua)) {
    return "Android";
  }
  if (/iPhone|iPad|iPod/i.test(ua)) {
    return "iOS";
  }
  if (/Linux/i.test(ua)) {
    return "Linux";
  }
  return "Unknown";
};

const buildClientDeviceInfo = () => {
  const nav = navigator;
  const conn = nav.connection || nav.mozConnection || nav.webkitConnection;
  const viewport = `${window.innerWidth || 0}x${window.innerHeight || 0}`;
  const screenSize = `${window.screen?.width || 0}x${window.screen?.height || 0}`;

  return {
    device_name: localStorage.getItem("rss-user-employee-no") || "onprem-device",
    user_agent: nav.userAgent || "",
    os: detectClientOs(),
    browser_language: nav.language || "",
    viewport,
    screen: screenSize,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "",
    platform: nav.platform || "",
    cpu_cores: Number(nav.hardwareConcurrency || 0),
    memory_gb: Number(nav.deviceMemory || 0),
    network_type: (conn && conn.effectiveType) || "",
    network_downlink_mbps: Number((conn && conn.downlink) || 0),
    local_ip_hint: "",
  };
};

const registerVisionDeviceInfo = async () => {
  const cameraId = getVisionCameraId();
  try {
    const response = await fetch(`/api/v1/vision/cameras/${encodeURIComponent(cameraId)}/device`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Camera-Token": getVisionCameraToken(),
      },
      body: JSON.stringify(buildClientDeviceInfo()),
    });

    if (!response.ok) {
      const errorText = await response.text();
      appendLog("ERROR", `Vision device register failed (${response.status}): ${errorText.slice(0, 120)}`);
      return;
    }

    appendLog("VISION", `On-prem device info registered: ${cameraId}`);
  } catch (error) {
    console.error("Vision device registration failed:", error);
  }
};

const captureVisionFrameBlob = async () => {
  if (!cameraVideo || !cameraCanvas || !cameraStream) {
    return null;
  }

  const width = cameraVideo.videoWidth;
  const height = cameraVideo.videoHeight;
  if (!width || !height) {
    return null;
  }

  cameraCanvas.width = width;
  cameraCanvas.height = height;

  const context = cameraCanvas.getContext("2d");
  if (!context) {
    return null;
  }

  context.drawImage(cameraVideo, 0, 0, width, height);

  return new Promise((resolve) => {
    cameraCanvas.toBlob((blob) => resolve(blob), "image/jpeg", 0.82);
  });
};

const setAutoOverlayView = (enabled) => {
  if (cameraOverlayStream instanceof HTMLImageElement) {
    cameraOverlayStream.hidden = !enabled;
  }
  if (cameraVideo instanceof HTMLVideoElement) {
    cameraVideo.hidden = enabled;
  }
};

const stopVisionUploadLoop = () => {
  if (visionUploadTimer) {
    clearInterval(visionUploadTimer);
    visionUploadTimer = null;
  }
};

const stopOverlayCountPolling = () => {
  if (visionOverlayCountTimer) {
    clearInterval(visionOverlayCountTimer);
    visionOverlayCountTimer = null;
  }
};

const fetchOverlayTodayCounts = async () => {
  try {
    const response = await fetch("/api/v1/vision/overlay-counts/today", { cache: "no-store" });
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    setOverlayCounts(payload.ok_count, payload.ng_count);
  } catch (error) {
    console.error("Failed to fetch DB overlay counts:", error);
  }
};

const startOverlayCountPolling = () => {
  stopOverlayCountPolling();
  fetchOverlayTodayCounts();
  visionOverlayCountTimer = setInterval(() => {
    fetchOverlayTodayCounts();
  }, 1200);
};

const uploadVisionFrame = async () => {
  if (visionFrameUploadInFlight || currentMode !== "auto") {
    return;
  }

  visionFrameUploadInFlight = true;
  try {
    const blob = await captureVisionFrameBlob();
    if (!(blob instanceof Blob)) {
      return;
    }

    const cameraId = getVisionCameraId();
    const formData = new FormData();
    formData.append("file", blob, "frame.jpg");

    const response = await fetch(`/api/v1/vision/cameras/${encodeURIComponent(cameraId)}/frames`, {
      method: "POST",
      headers: {
        "X-Camera-Token": getVisionCameraToken(),
      },
      body: formData,
    });

    if (!response.ok) {
      const errorText = await response.text();
      appendLog("ERROR", `Vision upload failed (${response.status}): ${errorText.slice(0, 120)}`);
      return;
    }

    await response.json();
  } catch (error) {
    console.error("Vision frame upload failed:", error);
  } finally {
    visionFrameUploadInFlight = false;
  }
};

const startVisionOverlayPipeline = () => {
  if (currentMode !== "auto" || !cameraVideo) {
    return;
  }

  const cameraId = getVisionCameraId();
  if (cameraOverlayStream instanceof HTMLImageElement) {
    cameraOverlayStream.src = `/api/v1/vision/cameras/${encodeURIComponent(cameraId)}/stream.mjpeg?ts=${Date.now()}`;
    cameraOverlayStream.onerror = () => {
      cameraOverlayStream.src = `/api/v1/vision/cameras/${encodeURIComponent(cameraId)}/stream?ts=${Date.now()}`;
      appendLog("VISION", "Primary stream URL failed, fallback stream URL applied");
    };
  }

  setAutoOverlayView(true);
  if (cameraPlaceholder) {
    cameraPlaceholder.hidden = true;
  }

  stopVisionUploadLoop();
  startOverlayCountPolling();
  registerVisionDeviceInfo();
  visionUploadTimer = setInterval(() => {
    uploadVisionFrame();
  }, 260);
  setCameraMessage("Running (On-prem overlay)");
  appendLog("VISION", `On-prem overlay pipeline started: ${cameraId}`);
};

const startOnpremOverlayOnly = async (skipDirectStream = false) => {
  if (currentMode !== "auto") {
    return;
  }

  startOverlayCountPolling();

  if (onpremOverlayRetryTimer) {
    clearTimeout(onpremOverlayRetryTimer);
    onpremOverlayRetryTimer = null;
  }

  const directStreamUrl = skipDirectStream ? "" : getOnpremDirectStreamUrl();
  if (directStreamUrl) {
    stopVisionUploadLoop();
    setAutoOverlayView(true);
    if (cameraPlaceholder) {
      cameraPlaceholder.hidden = true;
    }

    if (cameraOverlayStream instanceof HTMLImageElement) {
      cameraOverlayStream.src = withCacheBust(directStreamUrl);
      cameraOverlayStream.onerror = () => {
        appendOnpremOverlayFailureLogOnce(
          "direct-stream-failed",
          "Direct on-prem stream failed, fallback to vision API relay",
        );
        cameraOverlayStream.onerror = null;
        startOnpremOverlayOnly(true);
      };
    }

    setCameraMessage("Running (Direct on-prem stream)");
    resetOnpremOverlayFailureLogMute();
    appendLog("VISION", `Direct on-prem stream connected: ${directStreamUrl}`);
    return;
  }


  // Primary default for Auto Inspection: bind camera area directly to relay overlay stream.
  stopVisionUploadLoop();
  setAutoOverlayView(true);
  if (cameraPlaceholder) {
    cameraPlaceholder.hidden = true;
  }

  if (cameraOverlayStream instanceof HTMLImageElement) {
    cameraOverlayStream.src = withCacheBust("/api/v1/vision/overlay");
    cameraOverlayStream.onerror = () => {
      appendOnpremOverlayFailureLogOnce(
        "default-overlay-unavailable",
        "Default overlay stream unavailable, trying camera-specific fallback",
      );
      cameraOverlayStream.onerror = null;
      startOnpremOverlayOnly(true);
    };
  }

  setCameraMessage("Running (On-prem overlay)");
  appendLog("VISION", "Auto Inspection camera area bound to /api/v1/vision/overlay");

  // Also resolve explicit camera id in background for stable fallback path.
  let cameraId = getTargetOnpremCameraId();
  cameraId = await fetchLatestOnpremCameraId(cameraId);

  if (!cameraId) {
    setCameraMessage("Running (waiting active on-prem source)");
    if (!onpremNoCameraLogMuted) {
      appendLog("VISION", "No active on-prem camera yet, retrying overlay connection");
      onpremNoCameraLogMuted = true;
    }
    onpremOverlayRetryTimer = setTimeout(() => {
      startOnpremOverlayOnly();
    }, 2000);
    return;
  }

  // Camera source is back; unmute the one-time no-camera log gate.
  onpremNoCameraLogMuted = false;

  if (cameraOverlayStream instanceof HTMLImageElement) {
    cameraOverlayStream.src = withCacheBust(`/api/v1/vision/overlay?camera_id=${encodeURIComponent(cameraId)}`);
    cameraOverlayStream.onerror = () => {
      appendOnpremOverlayFailureLogOnce(
        `overlay-stream-error:${cameraId}`,
        `Overlay stream error for ${cameraId}, trying fallback`,
      );
      cameraOverlayStream.src = withCacheBust(`/api/v1/vision/cameras/${encodeURIComponent(cameraId)}/stream`);

      cameraOverlayStream.onerror = () => {
        appendOnpremOverlayFailureLogOnce(
          `fallback-stream-error:${cameraId}`,
          `Fallback stream failed for ${cameraId}, reselecting active camera`,
        );
        localStorage.removeItem(VISION_TARGET_CAMERA_ID_KEY);
        onpremOverlayRetryTimer = setTimeout(() => {
          startOnpremOverlayOnly();
        }, 1500);
      };
    };
  }

  setCameraMessage(`Running (On-prem stream: ${cameraId})`);
  resetOnpremOverlayFailureLogMute();
  appendLog("VISION", `Overlay-only mode connected: ${cameraId}`);
};

const stopVisionOverlayPipeline = () => {
  stopVisionUploadLoop();
  stopOverlayCountPolling();
  if (onpremOverlayRetryTimer) {
    clearTimeout(onpremOverlayRetryTimer);
    onpremOverlayRetryTimer = null;
  }
  onpremNoCameraLogMuted = false;
  resetOnpremOverlayFailureLogMute();
  if (cameraOverlayStream instanceof HTMLImageElement) {
    cameraOverlayStream.src = "";
  }
  setAutoOverlayView(false);
};

const renderChatTab = (tabKey) => {
  if (chatTabPanels.length === 0) {
    return;
  }

  chatTabButtons.forEach((button) => {
    const isActive = button.dataset.chatTab === tabKey;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", isActive ? "true" : "false");
  });

  chatTabPanels.forEach((panel) => {
    panel.hidden = panel.dataset.chatPanel !== tabKey;
  });
};

const renderConfigTab = (tabKey) => {
  if (configTabPanels.length === 0) {
    return;
  }

  configTabButtons.forEach((button) => {
    const isActive = button.dataset.configTab === tabKey;
    button.classList.toggle("configuration-tab-is-active", isActive);
    button.classList.toggle("configuration-tab", !isActive);
    button.setAttribute("aria-selected", isActive ? "true" : "false");
  });

  configTabPanels.forEach((panel) => {
    const isActive = panel.dataset.configPanel === tabKey;
    panel.hidden = !isActive;
    panel.style.display = isActive ? "grid" : "none";
  });
};

const ensureDefaultConfigSpace = () => {
  if (!(configDefaultPanel instanceof HTMLDivElement)) {
    return;
  }

  if (configDefaultPanel.querySelector(".configuration-default-space")) {
    return;
  }

  configDefaultPanel.innerHTML = `
    <section class="configuration-default-space" aria-label="기본설정 영역">
      <header class="configuration-default-head" style="display: flex; align-items: center; gap: 8px;">
        <label for="language-setting-select" style="font-weight: 700; color: #1e3553;">언어 설정</label>
        <select id="language-setting-select" style="height: 32px; border: 1px solid #9aa9bb; border-radius: 6px; padding: 0 8px; background: #fff; color: #1e3553;">
          <option value="ko">한국어</option>
          <option value="en">English</option>
        </select>
      </header>
      <p style="margin: 0; color: #4e5a69; font-size: 0.88rem;">선택한 언어는 이 브라우저에 저장됩니다.</p>
    </section>
  `;
};

const applyLanguageSetting = (language, silent = false) => {
  const normalized = String(language).toLowerCase().startsWith("en") ? "en" : "ko";
  document.documentElement.lang = normalized;
  localStorage.setItem(LANGUAGE_STORAGE_KEY, normalized);

  const selector = document.getElementById("language-setting-select");
  if (selector instanceof HTMLSelectElement && selector.value !== normalized) {
    selector.value = normalized;
  }

  if (!silent) {
    appendLog("SET", `Language changed to ${normalized}`);
  }
};

const bindLanguageSettingControl = () => {
  const selector = document.getElementById("language-setting-select");
  if (!(selector instanceof HTMLSelectElement)) {
    return;
  }

  if (selector.dataset.bound === "true") {
    return;
  }

  const savedLanguage = localStorage.getItem(LANGUAGE_STORAGE_KEY) || document.documentElement.lang || "ko";
  applyLanguageSetting(savedLanguage, true);

  selector.addEventListener("change", () => {
    applyLanguageSetting(selector.value);
  });

  selector.dataset.bound = "true";
};

const setFaceCameraStatus = (message) => {
  if (faceCameraStatus) {
    faceCameraStatus.textContent = message;
  }
};

const escapeHtml = (value) =>
  String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");

const scrollChatDisplayToBottom = (display) => {
  if (display === chatbotDisplay && chatThread instanceof HTMLDivElement) {
    chatThread.scrollTop = chatThread.scrollHeight;
    return;
  }
  if (display instanceof HTMLTextAreaElement) {
    display.scrollTop = display.scrollHeight;
  }
};

const setupChatThread = () => {
  if (!(chatbotDisplay instanceof HTMLTextAreaElement) || chatThread instanceof HTMLDivElement) {
    return;
  }

  chatbotDisplay.hidden = true;
  chatThread = document.createElement("div");
  chatThread.className = "chat-thread";
  chatThread.setAttribute("aria-live", "polite");
  chatbotDisplay.insertAdjacentElement("afterend", chatThread);
};

const setSourcePopupSources = (sources) => {
  latestChatSources = Array.isArray(sources)
    ? Array.from(new Set(sources.map((value) => String(value || "").trim()).filter(Boolean)))
    : [];
};

const isMainRichChatDisplay = (display) =>
  display === chatbotDisplay && chatbotDisplay instanceof HTMLTextAreaElement && chatThread instanceof HTMLDivElement;

const buildInlineSourcesText = (sources) => {
  if (!Array.isArray(sources) || sources.length === 0) {
    return "";
  }
  return `\n\n[Sources]\n${sources.map((source) => `- ${source}`).join("\n")}`;
};

const createMessageSourceMenu = (sources) => {
  if (!Array.isArray(sources) || sources.length === 0) {
    return null;
  }

  const details = document.createElement("details");
  details.className = "chat-message-sources";

  const summary = document.createElement("summary");
  summary.className = "chat-message-sources-trigger";
  summary.innerHTML = `
    <span>출처</span>
    <span class="chat-message-sources-count">${sources.length}</span>
  `;

  const popover = document.createElement("div");
  popover.className = "chat-message-sources-popover";

  sources.forEach((source) => {
    const item = document.createElement("a");
    item.className = "chat-message-source-link";
    item.href = source;
    item.target = "_blank";
    item.rel = "noopener noreferrer";
    item.textContent = source;
    item.title = source;
    popover.append(item);
  });

  details.append(summary, popover);
  return details;
};

const renderMessageSources = (footer, sources) => {
  if (!(footer instanceof HTMLDivElement)) {
    return;
  }
  footer.replaceChildren();
  if (!Array.isArray(sources) || sources.length === 0) {
    footer.hidden = true;
    return;
  }
  const menu = createMessageSourceMenu(sources);
  if (menu) {
    footer.hidden = false;
    footer.append(menu);
  }
};

const createRichChatMessage = (role, text = "", sources = []) => {
  if (!(chatThread instanceof HTMLDivElement)) {
    return null;
  }

  const article = document.createElement("article");
  article.className = `chat-message is-${role}`;

  const label = document.createElement("div");
  label.className = "chat-message-label";
  label.textContent = role === "user" ? "질문" : role === "assistant" ? "답변" : "안내";

  const body = document.createElement("div");
  body.className = "chat-message-body";
  body.textContent = text;

  const footer = document.createElement("div");
  footer.className = "chat-message-footer";
  footer.hidden = true;
  renderMessageSources(footer, sources);

  article.append(label, body, footer);
  chatThread.append(article);
  scrollChatDisplayToBottom(chatbotDisplay);
  return { article, body, footer };
};

const updateRichChatMessage = (messageRef, text, sources = []) => {
  if (!messageRef || !(messageRef.body instanceof HTMLDivElement)) {
    return;
  }
  messageRef.body.textContent = text;
  renderMessageSources(messageRef.footer, sources);
  scrollChatDisplayToBottom(chatbotDisplay);
};

const splitAnswerAndSources = (text) => {
  const raw = String(text || "");
  const marker = /\n+\[(?:출처|sources)\]\n/i;
  const match = marker.exec(raw);
  if (!match) {
    return { answerText: raw.trim(), sources: [] };
  }

  const answerText = raw.slice(0, match.index).trim();
  const sourceBlock = raw.slice(match.index + match[0].length).trim();
  const sources = sourceBlock
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.startsWith("- "))
    .map((line) => line.slice(2).trim())
    .map((line) => {
      const markdownMatch = line.match(/\((https?:\/\/[^)\s]+)\)/i);
      if (markdownMatch) {
        return markdownMatch[1].trim();
      }
      const urlMatch = line.match(/https?:\/\/[^\s)\]]+/i);
      return urlMatch ? urlMatch[0].trim() : line;
    })
    .filter(Boolean);

  return { answerText, sources };
};

const stripSimpleModeLead = (text) =>
  String(text || "")
    .replace(/^최신 웹 검색 결과를 바탕으로 확인한 내용입니다\.\s*/i, "")
    .replace(/^\s*Date:\s.*$/gim, "")
    .replace(/^\s*Source:\s.*$/gim, "")
    .trim();

const normalizeHandoverRecords = (items) => {
  const normalized = Array.isArray(items) ? items : [];
  return normalized
    .map((item) => ({
      issue: String(item?.issue || "").trim(),
      content: String(item?.content || "").trim(),
      worker: String(item?.worker || "").trim(),
      createdAt: String(item?.createdAt || "").trim(),
    }))
    .filter((item) => item.issue || item.content || item.worker)
    .slice(0, HANDOVER_MAX_ROWS);
};

const loadHandoverRecords = () => {
  try {
    const raw = localStorage.getItem(HANDOVER_STORAGE_KEY);
    if (!raw) {
      return normalizeHandoverRecords([]);
    }
    return normalizeHandoverRecords(JSON.parse(raw));
  } catch (error) {
    return normalizeHandoverRecords([]);
  }
};

const saveHandoverRecords = (items) => {
  const normalized = normalizeHandoverRecords(items);
  localStorage.setItem(HANDOVER_STORAGE_KEY, JSON.stringify(normalized));
  return normalized;
};

let handoverRecords = loadHandoverRecords();
let handoverEditingIndex = -1;

const getDefaultHandoverWorkerName = () =>
  String(currentWorkerDisplayName || localStorage.getItem(USER_DISPLAY_NAME_KEY) || localStorage.getItem(USER_EMPLOYEE_NO_KEY) || "").trim();

const syncHandoverForms = () => {
  const forms = Array.from(document.querySelectorAll(".handover-form"));
  const editingRecord =
    handoverEditingIndex >= 0 && handoverEditingIndex < handoverRecords.length
      ? handoverRecords[handoverEditingIndex]
      : null;

  forms.forEach((form) => {
    if (!(form instanceof HTMLFormElement)) {
      return;
    }

    const issueInput = form.querySelector('input[name="issue"]');
    const contentInput = form.querySelector('textarea[name="content"]');
    const workerInput = form.querySelector('input[name="worker"]');
    const saveButton = form.querySelector(".handover-save-btn");
    const cancelButton = form.querySelector('[data-handover-form-action="cancel"]');
    if (
      !(issueInput instanceof HTMLInputElement) ||
      !(contentInput instanceof HTMLTextAreaElement) ||
      !(workerInput instanceof HTMLInputElement) ||
      !(saveButton instanceof HTMLButtonElement) ||
      !(cancelButton instanceof HTMLButtonElement)
    ) {
      return;
    }

    if (editingRecord) {
      issueInput.value = editingRecord.issue;
      contentInput.value = editingRecord.content;
      workerInput.value = editingRecord.worker;
      saveButton.textContent = "수정";
      cancelButton.hidden = false;
      form.dataset.editingIndex = String(handoverEditingIndex);
      return;
    }

    issueInput.value = "";
    contentInput.value = "";
    workerInput.value = getDefaultHandoverWorkerName();
    saveButton.textContent = "저장";
    cancelButton.hidden = true;
    delete form.dataset.editingIndex;
  });
};

const startHandoverEditing = (index) => {
  if (!Number.isInteger(index) || index < 0 || index >= handoverRecords.length) {
    return;
  }

  handoverEditingIndex = index;
  syncHandoverForms();

  const firstForm = document.querySelector(".handover-form");
  if (!(firstForm instanceof HTMLFormElement)) {
    return;
  }

  const contentInput = firstForm.querySelector('textarea[name="content"]');
  if (contentInput instanceof HTMLTextAreaElement) {
    contentInput.focus();
    contentInput.setSelectionRange(contentInput.value.length, contentInput.value.length);
  }
};

const stopHandoverEditing = () => {
  handoverEditingIndex = -1;
  syncHandoverForms();
};

const renderHandoverBoards = () => {
  if (handoverBoards.length === 0) {
    return;
  }

  const rowsMarkup =
    handoverRecords.length > 0
      ? handoverRecords
          .map(
            (item, index) => `
              <div class="handover-row" role="row" data-row-index="${index}">
                <span role="cell">${escapeHtml(item.worker || "-")}</span>
                <span role="cell">${escapeHtml(item.issue || "-")}</span>
                <span role="cell">${escapeHtml(item.content || "-")}</span>
                <div class="handover-cell handover-cell-actions" role="cell">
                  <button class="handover-row-btn" type="button" data-handover-edit-index="${index}">수정</button>
                </div>
              </div>
            `,
          )
          .join("")
      : `
          <div class="handover-row handover-empty" role="row">
            <span role="cell">-</span>
            <span role="cell">등록된 인수인계가 없습니다.</span>
            <span role="cell">이슈, 내용, 작업자를 입력한 뒤 저장해 주세요.</span>
            <span role="cell">-</span>
          </div>
        `;

  handoverBoards.forEach((board) => {
    if (!(board instanceof HTMLDivElement)) {
      return;
    }

    let form = board.previousElementSibling;
    if (!(form instanceof HTMLFormElement) || !form.classList.contains("handover-form")) {
      form = document.createElement("form");
      form.className = "handover-form";
      board.insertAdjacentElement("beforebegin", form);
    }
    form.innerHTML = `
      <input class="handover-input" type="text" name="worker" placeholder="작업자 입력" autocomplete="off" />
      <input class="handover-input" type="text" name="issue" placeholder="이슈 입력" autocomplete="off" />
      <textarea class="handover-input handover-textarea" name="content" placeholder="내용 입력"></textarea>
      <div class="handover-form-actions">
        <button class="handover-save-btn" type="submit">저장</button>
        <button class="handover-action-btn" type="button" data-handover-form-action="cancel" hidden>취소</button>
      </div>
    `;

    board.innerHTML = `
      <div class="handover-row handover-head" role="row">
        <span role="columnheader">작업자</span>
        <span role="columnheader">이슈</span>
        <span role="columnheader">내용</span>
        <span role="columnheader">관리</span>
      </div>
      ${rowsMarkup}
    `;

    let actions = board.nextElementSibling;
    if (!(actions instanceof HTMLDivElement) || !actions.classList.contains("handover-actions")) {
      actions = document.createElement("div");
      actions.className = "handover-actions";
      board.insertAdjacentElement("afterend", actions);
    }
    actions.innerHTML = `
      <span class="handover-status"></span>
      <div class="handover-actions-right">
        <button class="handover-action-btn is-danger" type="button" data-handover-action="reset">초기화</button>
      </div>
    `;
  });

  syncHandoverForms();
};

const setChatFormPending = (isPending) => {
  if (askInput instanceof HTMLInputElement) {
    askInput.disabled = isPending;
  }

  if (askUploadBtn instanceof HTMLButtonElement) {
    askUploadBtn.disabled = isPending;
  }

  if (askUploadInput instanceof HTMLInputElement) {
    askUploadInput.disabled = isPending;
  }

  if (askSendBtn instanceof HTMLButtonElement) {
    askSendBtn.disabled = isPending;
    askSendBtn.textContent = isPending ? "Sending..." : "Send";
  }
};

const markHandoverSaved = (
  message = "자동 저장됨",
  { autoReset = false, blinking = false } = {},
) => {
  if (handoverStatusResetTimer) {
    window.clearTimeout(handoverStatusResetTimer);
    handoverStatusResetTimer = null;
  }

  const labels = Array.from(document.querySelectorAll(".handover-status"));
  labels.forEach((label) => {
    if (label instanceof HTMLSpanElement) {
      label.textContent = message;
      label.classList.toggle("is-flashing", blinking);
    }
  });

  if (autoReset) {
    handoverStatusResetTimer = window.setTimeout(() => {
      markHandoverSaved("");
    }, HANDOVER_STATUS_TIMEOUT_MS);
  }
};

const handleHandoverSubmit = (form) => {
  if (!(form instanceof HTMLFormElement)) {
    return;
  }

  const issueInput = form.querySelector('input[name="issue"]');
  const contentInput = form.querySelector('textarea[name="content"]');
  const workerInput = form.querySelector('input[name="worker"]');
  if (
    !(issueInput instanceof HTMLInputElement) ||
    !(contentInput instanceof HTMLTextAreaElement) ||
    !(workerInput instanceof HTMLInputElement)
  ) {
    return;
  }

  const record = {
    issue: issueInput.value.trim(),
    content: contentInput.value.trim(),
    worker: workerInput.value.trim() || getDefaultHandoverWorkerName(),
    createdAt: new Date().toISOString(),
  };

  if (!record.issue && !record.content && !record.worker) {
    markHandoverSaved("저장할 내용을 입력해 주세요.");
    issueInput.focus();
    return;
  }

  if (handoverEditingIndex >= 0 && handoverEditingIndex < handoverRecords.length) {
    const current = handoverRecords[handoverEditingIndex];
    const nextRecords = [...handoverRecords];
    nextRecords[handoverEditingIndex] = {
      issue: record.issue,
      content: record.content,
      worker: record.worker,
      createdAt: current?.createdAt || record.createdAt,
    };
    handoverRecords = saveHandoverRecords(nextRecords);
    handoverEditingIndex = -1;
    renderHandoverBoards();
    bindHandoverBoards();
    markHandoverSaved("수정하였습니다.", { autoReset: true, blinking: true });
    return;
  }

  handoverRecords = saveHandoverRecords([record, ...handoverRecords]);
  renderHandoverBoards();
  bindHandoverBoards();
  markHandoverSaved("인수인계가 저장되었습니다.", { autoReset: true, blinking: true });
};

const handleHandoverAction = (action) => {
  if (action === "reset") {
    handoverEditingIndex = -1;
    handoverRecords = saveHandoverRecords([]);
    renderHandoverBoards();
    bindHandoverBoards();
    markHandoverSaved("인수인계 기록을 초기화했습니다.", { autoReset: true, blinking: true });
  }
};

const bindHandoverBoards = () => {
  if (handoverBoards.length === 0) {
    return;
  }

  const forms = Array.from(document.querySelectorAll(".handover-form"));
  forms.forEach((form) => {
    if (!(form instanceof HTMLFormElement) || form.dataset.bound === "true") {
      return;
    }
    form.dataset.bound = "true";
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      handleHandoverSubmit(form);
    });
    form.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) {
        return;
      }
      const actionButton = target.closest("[data-handover-form-action]");
      if (!(actionButton instanceof HTMLButtonElement)) {
        return;
      }
      if ((actionButton.dataset.handoverFormAction || "") !== "cancel") {
        return;
      }
      stopHandoverEditing();
      const issueInput = form.querySelector('input[name="issue"]');
      if (issueInput instanceof HTMLInputElement) {
        issueInput.focus();
      }
    });
  });

  handoverBoards.forEach((board) => {
    if (!(board instanceof HTMLDivElement) || board.dataset.bound === "true") {
      return;
    }
    board.dataset.bound = "true";
    board.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) {
        return;
      }
      const editButton = target.closest("[data-handover-edit-index]");
      if (!(editButton instanceof HTMLButtonElement)) {
        return;
      }
      const editIndex = Number.parseInt(editButton.dataset.handoverEditIndex || "", 10);
      startHandoverEditing(editIndex);
    });
  });

  const actionAreas = Array.from(document.querySelectorAll(".handover-actions"));
  actionAreas.forEach((area) => {
    if (!(area instanceof HTMLDivElement) || area.dataset.bound === "true") {
      return;
    }
    area.dataset.bound = "true";
    area.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) {
        return;
      }
      const actionButton = target.closest("[data-handover-action]");
      if (!(actionButton instanceof HTMLButtonElement)) {
        return;
      }
      handleHandoverAction(actionButton.dataset.handoverAction || "");
    });
  });
};

const appendChatNotice = (message, targetDisplay = chatbotDisplay) => {
  const text = String(message || "").trim();
  if (!text || !(targetDisplay instanceof HTMLTextAreaElement)) {
    return;
  }

  if (isMainRichChatDisplay(targetDisplay)) {
    createRichChatMessage("notice", text);
  }

  const previous = targetDisplay.value.trim();
  targetDisplay.value = previous ? `${previous}\n\n${text}` : text;
  scrollChatDisplayToBottom(targetDisplay);
};

const closeAskToolsMenu = () => {
  if (askToolsMenu instanceof HTMLDetailsElement) {
    askToolsMenu.open = false;
  }
};

const uploadKnowledgeFile = async (file) => {
  if (!(file instanceof File) || !file.name) {
    return;
  }

  setChatFormPending(true);
  appendLog("CHAT", `Knowledge file upload started: ${file.name}`);

  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch("/api/v1/llm/upload", {
      method: "POST",
      body: formData,
    });

    let payload = null;
    try {
      payload = await response.json();
    } catch (error) {
      payload = null;
    }

    if (!response.ok) {
      const errorMessage =
        payload && typeof payload.error === "string" && payload.error.trim()
          ? payload.error.trim()
          : payload && typeof payload.message === "string" && payload.message.trim()
            ? payload.message.trim()
            : `파일 업로드 실패 (${response.status})`;
      throw new Error(errorMessage);
    }

    const successMessage =
      payload && typeof payload.message === "string" && payload.message.trim()
        ? payload.message.trim()
        : `Upload complete: ${file.name}`;

    appendChatNotice(`[파일 업로드]\n${successMessage}`);
    appendLog("CHAT", `Knowledge file upload completed: ${file.name}`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "파일 업로드에 실패했습니다.";
    appendChatNotice(`[파일 업로드 실패]\n${message}`);
    appendLog("ERROR", `Knowledge file upload failed: ${message}`);
  } finally {
    if (askUploadInput instanceof HTMLInputElement) {
      askUploadInput.value = "";
    }
    setChatFormPending(false);
  }
};

const setSimpleItemPending = (container, isPending) => {
  if (!(container instanceof HTMLElement)) {
    return;
  }

  container.dataset.pending = isPending ? "true" : "false";
  const input = container.querySelector(".simple-chat-item-input");
  const sendBtn = container.querySelector(".simple-chat-item-send");
  if (input instanceof HTMLInputElement) {
    input.disabled = isPending;
  }
  if (sendBtn instanceof HTMLButtonElement) {
    sendBtn.disabled = isPending;
    sendBtn.textContent = isPending ? "Sending..." : "Send";
  }
};

const ensureSimpleItemChatView = (button, question) => {
  if (!(button instanceof HTMLButtonElement)) {
    return null;
  }

  const sessionKey = String(question || "").trim();
  if (!sessionKey) {
    return null;
  }

  const container = document.createElement("div");
  container.className = "chat-question-item simple-chat-item-open";
  container.dataset.sessionKey = sessionKey;
  container.dataset.pending = "false";
  container.dataset.initialized = "true";
  container.setAttribute("role", "group");
  container.innerHTML = `
    <div class="simple-chat-item-head">
      <span class="simple-chat-item-title">${escapeHtml(sessionKey)}</span>
    </div>
    <textarea class="chat-display-box simple-chat-item-display" readonly placeholder="답변이 여기에 표시됩니다."></textarea>
    <form class="simple-chat-item-form" aria-label="간편모드 항목 채팅 입력">
      <input class="ask-input simple-chat-item-input" type="text" name="simple-item-question" placeholder="추가 질문을 입력하세요..." autocomplete="off" />
      <button class="ask-send-btn simple-chat-item-send" type="submit">Send</button>
    </form>
  `;
  button.replaceWith(container);

  const display = container.querySelector(".simple-chat-item-display");
  const form = container.querySelector(".simple-chat-item-form");
  const input = container.querySelector(".simple-chat-item-input");
  const sendBtn = container.querySelector(".simple-chat-item-send");
  const title = container.querySelector(".simple-chat-item-title");

  if (
    !(display instanceof HTMLTextAreaElement) ||
    !(form instanceof HTMLFormElement) ||
    !(input instanceof HTMLInputElement) ||
    !(sendBtn instanceof HTMLButtonElement) ||
    !(title instanceof HTMLElement)
  ) {
    return null;
  }

  title.textContent = sessionKey;
  display.value = simpleSessionHistory.get(sessionKey) || "";
  scrollChatDisplayToBottom(display);
  setSimpleItemPending(container, false);

  return { container, sessionKey, display, form, input, sendBtn };
};

const isTtsEnabled = () => !(ttsToggle instanceof HTMLInputElement) || ttsToggle.checked;

const syncTtsStopButton = () => {
  if (!(stopTtsBtn instanceof HTMLButtonElement)) {
    return;
  }
  const speechActive = "speechSynthesis" in window && window.speechSynthesis.speaking;
  const active = !!currentTtsAudio || speechActive;
  stopTtsBtn.disabled = !active;
  stopTtsBtn.classList.toggle("is-off", !active);
};

const stopSpeech = () => {
  ttsSessionToken += 1;
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
  if (currentTtsAudio) {
    currentTtsAudio.pause();
    currentTtsAudio.src = "";
    currentTtsAudio = null;
  }
  ttsQueue = Promise.resolve();
  syncTtsStopButton();
};

const stripSourcesForTts = (text) => String(text || "").replace(/\n+\[(?:출처|sources)\][\s\S]*$/im, "").trim();

const speakViaServer = async (text) => {
  const fd = new FormData();
  fd.append("text", text);
  fd.append("provider", "openai");
  fd.append("voice", "alloy");
  fd.append("audio_format", "mp3");

  const response = await fetch("/api/v1/llm/tts", { method: "POST", body: fd });
  if (!response.ok) {
    throw new Error(`tts_http_${response.status}`);
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    const payload = await response.json();
    throw new Error(payload.error || "tts_error");
  }

  const blob = await response.blob();
  if (!blob.size) {
    return;
  }

  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  currentTtsAudio = audio;
  syncTtsStopButton();

  await new Promise((resolve, reject) => {
    audio.onended = () => {
      URL.revokeObjectURL(url);
      if (currentTtsAudio === audio) {
        currentTtsAudio = null;
      }
      syncTtsStopButton();
      resolve();
    };
    audio.onerror = () => {
      URL.revokeObjectURL(url);
      if (currentTtsAudio === audio) {
        currentTtsAudio = null;
      }
      syncTtsStopButton();
      reject(new Error("tts_playback_error"));
    };
    audio.play().catch(reject);
  });
};

const speakViaBrowser = async (text) => {
  if (!("speechSynthesis" in window)) {
    return;
  }

  await new Promise((resolve) => {
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = "ko-KR";
    utter.rate = 1;
    utter.pitch = 1;
    utter.onend = () => {
      syncTtsStopButton();
      resolve();
    };
    utter.onerror = () => {
      syncTtsStopButton();
      resolve();
    };
    window.speechSynthesis.speak(utter);
    syncTtsStopButton();
  });
};

const speak = async (text, token = null) => {
  if (token !== null && token !== ttsSessionToken) {
    return;
  }
  if (!isTtsEnabled()) {
    return;
  }

  const content = stripSourcesForTts(text);
  if (!content) {
    return;
  }

  try {
    await speakViaServer(content);
  } catch (error) {
    await speakViaBrowser(content);
  }
};

const queueTtsText = (rawText) => {
  const text = stripSourcesForTts(rawText);
  if (!text || !isTtsEnabled()) {
    return;
  }

  const token = ttsSessionToken;
  ttsQueue = ttsQueue
    .then(async () => {
      if (token !== ttsSessionToken || !isTtsEnabled()) {
        return;
      }
      await speak(text, token);
    })
    .catch(() => {});
};

const stopSttMonitoring = () => {
  if (sttMonitorId) {
    cancelAnimationFrame(sttMonitorId);
    sttMonitorId = null;
  }
  if (sttAudioContext) {
    sttAudioContext.close();
    sttAudioContext = null;
  }
  sttAnalyser = null;
  sttLastVoiceAt = 0;
  sttRecordStartedAt = 0;
};

const startSttMonitoring = (stream) => {
  stopSttMonitoring();
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) {
    return;
  }

  sttAudioContext = new AudioContextClass();
  const source = sttAudioContext.createMediaStreamSource(stream);
  sttAnalyser = sttAudioContext.createAnalyser();
  sttAnalyser.fftSize = 1024;
  source.connect(sttAnalyser);

  const data = new Uint8Array(sttAnalyser.frequencyBinCount);
  sttLastVoiceAt = Date.now();

  const monitor = () => {
    if (!mediaRecorder || mediaRecorder.state !== "recording" || !sttAnalyser) {
      return;
    }

    sttAnalyser.getByteFrequencyData(data);
    let sum = 0;
    for (let i = 0; i < data.length; i += 1) {
      sum += data[i];
    }

    const avg = sum / data.length;
    if (avg > 10) {
      sttLastVoiceAt = Date.now();
    } else if (Date.now() - sttLastVoiceAt > 1400 && Date.now() - sttRecordStartedAt > 1200) {
      mediaRecorder.stop();
      return;
    }

    sttMonitorId = requestAnimationFrame(monitor);
  };
  sttMonitorId = requestAnimationFrame(monitor);
};

const stopRecording = (discard = false) => {
  if (!mediaRecorder) {
    return;
  }
  if (discard) {
    skipNextStt = true;
  }
  if (mediaRecorder.state === "recording") {
    mediaRecorder.stop();
  }
  stopSttMonitoring();
};

const setSttEnabled = (enabled) => {
  sttEnabled = !!enabled;
  if (sttToggle instanceof HTMLInputElement) {
    sttToggle.checked = sttEnabled;
  }
  if (micBtn instanceof HTMLButtonElement) {
    micBtn.disabled = !sttEnabled;
    micBtn.classList.toggle("is-off", !sttEnabled);
  }
  if (!sttEnabled) {
    stopRecording(true);
  }
  localStorage.setItem(STT_ENABLED_KEY, sttEnabled ? "true" : "false");
};

const toggleRecording = async () => {
  if (!sttEnabled) {
    return;
  }

  stopSpeech();

  if (typeof MediaRecorder === "undefined") {
    appendLog("ERROR", "This browser does not support MediaRecorder");
    return;
  }

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    appendLog("ERROR", "This browser does not support audio recording");
    return;
  }

  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    currentMicStream = stream;
    audioChunks = [];
    skipNextStt = false;

    const mimeTypeCandidates = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"];
    const mimeType =
      mimeTypeCandidates.find((m) => MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(m)) || "";
    mediaRecorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);

    startSttMonitoring(stream);
    sttRecordStartedAt = Date.now();

    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data);
      }
    };

    mediaRecorder.onstop = async () => {
      if (micBtn instanceof HTMLButtonElement) {
        micBtn.classList.remove("recording");
      }
      stopSttMonitoring();

      if (skipNextStt) {
        skipNextStt = false;
        if (currentMicStream) {
          currentMicStream.getTracks().forEach((track) => track.stop());
          currentMicStream = null;
        }
        mediaRecorder = null;
        return;
      }

      const blobType = mediaRecorder && mediaRecorder.mimeType ? mediaRecorder.mimeType : "audio/webm";
      const ext = blobType.includes("mp4") ? "mp4" : "webm";
      const audioBlob = new Blob(audioChunks, { type: blobType });
      if (audioBlob.size < 1500) {
        appendLog("CHAT", "STT skipped: audio too short");
        if (currentMicStream) {
          currentMicStream.getTracks().forEach((track) => track.stop());
          currentMicStream = null;
        }
        mediaRecorder = null;
        return;
      }

      const fd = new FormData();
      fd.append("file", audioBlob, `speech.${ext}`);
      fd.append("provider", "openai");
      fd.append("language", "ko");

      try {
        const response = await fetch("/api/v1/llm/stt", { method: "POST", body: fd });
        const payload = await response.json();
        if (payload.error) {
          appendLog("ERROR", `STT error: ${payload.error}`);
          return;
        }

        if (payload.text && askInput instanceof HTMLInputElement) {
          askInput.value = payload.text;
          askInput.focus();
          appendLog("CHAT", "STT text applied to input");
        }
      } catch (error) {
        appendLog("ERROR", "STT request failed");
      } finally {
        stopSttMonitoring();
        if (currentMicStream) {
          currentMicStream.getTracks().forEach((track) => track.stop());
          currentMicStream = null;
        }
        mediaRecorder = null;
      }
    };

    mediaRecorder.start(300);
    if (micBtn instanceof HTMLButtonElement) {
      micBtn.classList.add("recording");
    }
  } catch (error) {
    appendLog("ERROR", `Mic access failed: ${error instanceof Error ? error.message : "unknown"}`);
  }
};

const submitQuestion = async (questionText, options = {}) => {
  const question = String(questionText || "").trim();
  const targetDisplay =
    options.targetDisplay instanceof HTMLTextAreaElement ? options.targetDisplay : chatbotDisplay;
  const useChatFormPending = options.useChatFormPending !== false;
  const showSources = options.showSources !== false;
  const stripLead = options.stripWebLead === true;
  const disableAutoWeb = options.disableAutoWeb === true;

  if (!question) {
    return;
  }

  stopSpeech();
  appendLog("CHAT", `Question submitted: ${question}`);

  if (!(targetDisplay instanceof HTMLTextAreaElement)) {
    return;
  }

  if (activeChatController) {
    activeChatController.abort();
    activeChatController = null;
  }

  const previous = targetDisplay.value.trim();
  const responsePrefix = previous ? `${previous}\n\nQ: ${question}\nA: ` : `Q: ${question}\nA: `;
  const useRichChat = isMainRichChatDisplay(targetDisplay);
  let assistantMessageRef = null;

  if (useRichChat) {
    createRichChatMessage("user", question);
    assistantMessageRef = createRichChatMessage("assistant", "응답을 불러오는 중...");
  } else {
    setSourcePopupSources([]);
    targetDisplay.value = `${responsePrefix}응답을 불러오는 중...`;
  }

  targetDisplay.value = `${responsePrefix}응답을 불러오는 중...`;
  scrollChatDisplayToBottom(targetDisplay);
  if (useChatFormPending) {
    setChatFormPending(true);
  }

  const formData = new FormData();
  formData.append("message", question);
  formData.append("provider", "openai");
  formData.append(
    "web_search",
    webSearchToggle instanceof HTMLInputElement && webSearchToggle.checked ? "true" : "false",
  );
  formData.append("disable_auto_web", disableAutoWeb ? "true" : "false");
  formData.append("reset_memory", "false");
  formData.append("empathy_level", "balanced");
  formData.append("language", getCurrentLanguageForQuestions());

  const controller = new AbortController();
  activeChatController = controller;

  try {
    const response = await fetch("/api/v1/llm/chat", {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });

    if (!response.ok || !response.body) {
      throw new Error(`server_error_${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let answer = "";
    if (!useRichChat) {
      targetDisplay.value = responsePrefix;
    }
    scrollChatDisplayToBottom(targetDisplay);

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      answer += decoder.decode(value, { stream: true });
      const parsed = splitAnswerAndSources(answer);
      const visibleAnswerText = stripLead ? stripSimpleModeLead(parsed.answerText) : parsed.answerText;
      const visibleSources = showSources ? parsed.sources : [];
      const inlineSourceText = useRichChat ? "" : buildInlineSourcesText(visibleSources);
      targetDisplay.value = `${responsePrefix}${visibleAnswerText}${inlineSourceText}`;
      if (useRichChat && assistantMessageRef) {
        updateRichChatMessage(
          assistantMessageRef,
          visibleAnswerText || "응답을 불러오는 중...",
          visibleSources,
        );
      } else {
        setSourcePopupSources(visibleSources);
      }
      scrollChatDisplayToBottom(targetDisplay);
    }

    answer += decoder.decode();
    const parsed = splitAnswerAndSources(answer);
    const finalAnswer = (stripLead ? stripSimpleModeLead(parsed.answerText) : parsed.answerText).trim();
    const visibleSources = showSources ? parsed.sources : [];
    const inlineSourceText = useRichChat ? "" : buildInlineSourcesText(visibleSources);
    targetDisplay.value = `${responsePrefix}${finalAnswer}${inlineSourceText}`;
    if (useRichChat && assistantMessageRef) {
      updateRichChatMessage(assistantMessageRef, finalAnswer, visibleSources);
    } else {
      setSourcePopupSources(visibleSources);
    }
    scrollChatDisplayToBottom(targetDisplay);
    appendLog("CHAT", "Chat response received");
    queueTtsText(finalAnswer);
  } catch (error) {
    const message =
      error instanceof DOMException && error.name === "AbortError"
        ? "이전 요청이 취소되었습니다."
        : "응답을 가져오지 못했습니다.";
    if (useRichChat && assistantMessageRef) {
      updateRichChatMessage(assistantMessageRef, message, []);
    } else {
      setSourcePopupSources([]);
      targetDisplay.value = `${responsePrefix}${message}`;
    }
    targetDisplay.value = `${responsePrefix}${message}`;
    scrollChatDisplayToBottom(targetDisplay);
    appendLog("ERROR", `Chat request failed: ${message}`);
  } finally {
    if (activeChatController === controller) {
      activeChatController = null;
    }
    if (useChatFormPending) {
      setChatFormPending(false);
    }
    syncTtsStopButton();
  }
};

const getCurrentLanguageForQuestions = () => {
  const savedLanguage = localStorage.getItem(LANGUAGE_STORAGE_KEY) || document.documentElement.lang || "ko";
  return String(savedLanguage).toLowerCase().startsWith("en") ? "en" : "ko";
};

const renderSimpleQuestionButtons = (questions) => {
  if (!(simpleQuestionList instanceof HTMLDivElement)) {
    return;
  }

  if (!Array.isArray(questions) || questions.length === 0) {
    return;
  }

  simpleQuestionList.innerHTML = questions
    .map((question) => {
      const safeQuestion = escapeHtml(question);
      return `
        <button class="chat-question-item chat-question-btn" type="button" role="listitem" data-question="${safeQuestion}">
          ${safeQuestion}
        </button>
      `;
    })
    .join("");
};

const loadRecommendedQuestions = async () => {
  if (!(simpleQuestionList instanceof HTMLDivElement)) {
    return;
  }

  const language = getCurrentLanguageForQuestions();

  try {
    const response = await fetch(`/api/v1/llm/recommended-questions?lang=${language}&count=3`);
    if (!response.ok) {
      throw new Error("recommended_questions_fetch_failed");
    }

    const payload = await response.json();
    const questions = Array.isArray(payload?.items) ? payload.items : [];

    if (questions.length > 0) {
      renderSimpleQuestionButtons(questions);
      appendLog("CHAT", `Recommended questions loaded (${payload.source || "unknown"})`);
      return;
    }
  } catch (error) {
    console.error("Failed to load recommended questions:", error);
  }

  renderSimpleQuestionButtons(DEFAULT_SIMPLE_QUESTIONS[language] || DEFAULT_SIMPLE_QUESTIONS.ko);
  appendLog("CHAT", "Fallback recommended questions loaded");
};

const renderFaceRegistrationRows = (items) => {
  if (!(faceAccountListBody instanceof HTMLDivElement)) {
    return;
  }

  if (!Array.isArray(items) || items.length === 0) {
    faceAccountListBody.innerHTML = `
      <div class="configuration-account-row" role="row">
        <span role="cell">-</span>
        <span role="cell">-</span>
        <span role="cell">-</span>
        <span role="cell">결과없음</span>
      </div>
    `;
    return;
  }

  faceAccountListBody.innerHTML = items
    .map((item) => {
      const employeeNo = escapeHtml(item.employee_no ?? "-");
      const name = escapeHtml(item.name ?? "-");
      const status = escapeHtml(item.registration_status ?? "미등록");
      const isSelected = selectedEmployeeNo === item.employee_no;

      return `
        <div class="configuration-account-row" role="row">
          <span role="cell">
            <button
              class="configuration-select-btn${isSelected ? " is-selected" : ""}"
              type="button"
              data-employee-no="${employeeNo}"
              aria-pressed="${isSelected ? "true" : "false"}"
            >
              V
            </button>
          </span>
          <span role="cell">${employeeNo}</span>
          <span role="cell">${name}</span>
          <span role="cell">${status}</span>
        </div>
      `;
    })
    .join("");
};

const setFaceRegistrationSummary = (text) => {
  if (faceRegistrationSummary) {
    faceRegistrationSummary.textContent = text;
  }
};

const setSelectedEmployeeNo = (employeeNo) => {
  selectedEmployeeNo = employeeNo || "";

  if (faceSelectedEmployee) {
    faceSelectedEmployee.textContent = selectedEmployeeNo
      ? `선택된 사원번호: ${selectedEmployeeNo}`
      : "선택된 사원번호: 없음";
  }
};

const loadFaceRegistrations = async (keyword = "") => {
  if (currentPath !== "/configuration.html") {
    return;
  }

  setFaceRegistrationSummary("조회중");

  try {
    const query = keyword ? `?keyword=${encodeURIComponent(keyword)}` : "";
    const response = await authFetch(`/api/v1/auth/face/registrations${query}`);

    if (!response.ok) {
      throw new Error("face_registration_fetch_failed");
    }

    const payload = await response.json();
    lastFaceRegistrationItems = payload.items ?? [];
    renderFaceRegistrationRows(lastFaceRegistrationItems);
    setFaceRegistrationSummary(`등록 ${payload.registered_count} / 전체 ${payload.total}`);
  } catch (error) {
    console.error("Failed to load face registrations:", error);
    lastFaceRegistrationItems = [];
    renderFaceRegistrationRows(lastFaceRegistrationItems);
    setFaceRegistrationSummary("조회실패");
  }
};

const captureFaceFrameAsBase64 = () => {
  if (!(faceVideo instanceof HTMLVideoElement)) {
    return null;
  }

  const width = faceVideo.videoWidth;
  const height = faceVideo.videoHeight;

  if (!width || !height) {
    return null;
  }

  const maxWidth = 960;
  const scale = width > maxWidth ? maxWidth / width : 1;
  const targetWidth = Math.max(1, Math.round(width * scale));
  const targetHeight = Math.max(1, Math.round(height * scale));

  const canvas = document.createElement("canvas");
  canvas.width = targetWidth;
  canvas.height = targetHeight;

  const context = canvas.getContext("2d");
  if (!context) {
    return null;
  }

  context.drawImage(faceVideo, 0, 0, targetWidth, targetHeight);
  return canvas.toDataURL("image/jpeg", 0.82);
};

const submitFaceRegistration = async () => {
  if (!selectedEmployeeNo) {
    setFaceRegistrationSummary("사원번호 선택 필요");
    return;
  }

  const imageBase64 = captureFaceFrameAsBase64();
  if (!imageBase64) {
    setFaceRegistrationSummary("카메라 프레임 없음");
    return;
  }

  if (faceRegisterBtn instanceof HTMLButtonElement) {
    faceRegisterBtn.disabled = true;
  }

  setFaceRegistrationSummary("등록중 (최대 20초)");

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
      controller.abort();
    }, 20000);

    let response;
    try {
      response = await authFetch("/api/v1/auth/face/register", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getAuthHeaders(),
        },
        signal: controller.signal,
        body: JSON.stringify({
          employee_no: selectedEmployeeNo,
          image_base64: imageBase64,
        }),
      });
    } finally {
      clearTimeout(timeoutId);
    }

    if (!response.ok) {
      const errorPayload = await response.clone().json().catch(() => null);
      const errorText = await response.text().catch(() => "");
      const detail = errorPayload?.detail || errorText || `등록 실패 (${response.status})`;
      throw new Error(detail);
    }

    appendLog("FACE", `Face embedding registered for ${selectedEmployeeNo}`);
    await loadFaceRegistrations(faceAccountKeywordInput instanceof HTMLInputElement ? faceAccountKeywordInput.value.trim() : "");
    setFaceRegistrationSummary(`등록 완료: ${selectedEmployeeNo}`);
  } catch (error) {
    const errorMessage =
      error instanceof DOMException && error.name === "AbortError"
        ? "요청 시간 초과 (카메라/모델 상태 확인 필요)"
        : error instanceof Error
          ? error.message
          : "등록 실패";
    setFaceRegistrationSummary(errorMessage);
    appendLog("ERROR", `Face registration failed: ${errorMessage}`);
  } finally {
    if (faceRegisterBtn instanceof HTMLButtonElement) {
      faceRegisterBtn.disabled = false;
    }
  }
};

const stopFaceCamera = () => {
  if (!faceCameraStream) {
    return;
  }

  faceCameraStream.getTracks().forEach((track) => track.stop());
  faceCameraStream = null;

  if (faceVideo instanceof HTMLVideoElement) {
    faceVideo.srcObject = null;
  }
};

const startFaceCamera = async () => {
  if (!(faceVideo instanceof HTMLVideoElement)) {
    return;
  }

  if (faceCameraStream) {
    setFaceCameraStatus("카메라가 연결되었습니다.");
    return;
  }

  if (!window.isSecureContext) {
    setFaceCameraStatus("HTTPS 또는 localhost 환경에서 카메라를 사용할 수 있습니다.");
    return;
  }

  const hasModernApi = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
  const hasLegacyApi = !!getLegacyGetUserMedia();

  if (!hasModernApi && !hasLegacyApi) {
    setFaceCameraStatus("브라우저에서 카메라 API를 지원하지 않습니다.");
    return;
  }

  try {
    setFaceCameraStatus("카메라 권한을 요청 중입니다...");

    try {
      faceCameraStream = await requestCameraStream({
        video: {
          facingMode: "user",
        },
        audio: false,
      });
    } catch (primaryError) {
      faceCameraStream = await requestCameraStream({
        video: true,
        audio: false,
      });
      console.warn("Configuration camera fallback applied:", primaryError);
    }

    faceVideo.srcObject = faceCameraStream;
    await faceVideo.play();
    setFaceCameraStatus("카메라가 자동으로 시작되었습니다.");
    appendLog("CAM", "Configuration face camera started");
  } catch (error) {
    console.error("Configuration face camera start failed:", error);
    setFaceCameraStatus(`카메라 연결 실패: ${mapCameraErrorToStatus(error)}`);
    appendLog("ERROR", "Configuration face camera start failed");
  }
};

const setCameraResolution = () => {
  if (!cameraVideo || !cameraResolution || !cameraVideo.videoWidth || !cameraVideo.videoHeight) {
    return;
  }

  cameraResolution.textContent = `Resolution : ${cameraVideo.videoWidth}x${cameraVideo.videoHeight}`;
};

const setOverlayCounts = (okCount, ngCount) => {
  const okValue = Number.isFinite(Number(okCount)) ? Number(okCount) : 0;
  const ngValue = Number.isFinite(Number(ngCount)) ? Number(ngCount) : 0;

  if (overlayOkCount) {
    overlayOkCount.textContent = String(okValue);
  }

  if (overlayNgCount) {
    overlayNgCount.textContent = String(ngValue);
  }

  if (ngValue > previousNgCount) {
    setSignalLight("ng");
    appendLog("NG", `NG count increased to ${ngValue}`);
  } else if (okValue > previousOkCount) {
    setSignalLight("ok");
    appendLog("OK", `OK count increased to ${okValue}`);
  }

  previousOkCount = okValue;
  previousNgCount = ngValue;
};

const setSignalLight = (type) => {
  [signalRed, signalYellow, signalGreen].forEach((lightEl) => {
    if (lightEl) {
      lightEl.classList.remove("is-on");
    }
  });

  if (type === "ng" && signalRed) {
    signalRed.classList.add("is-on");
  }

  if (type === "ok" && signalGreen) {
    signalGreen.classList.add("is-on");
  }

  if ((type === "warning" || type === "standby") && signalYellow) {
    signalYellow.classList.add("is-on");
  }

  if (type !== previousSignalType) {
    const signalText =
      type === "ok" ? "GREEN(OK)" : type === "ng" ? "RED(NG)" : "YELLOW(STANDBY/WARNING)";
    appendLog("SIGNAL", signalText);
    previousSignalType = type;
  }
};

const mapCameraErrorToStatus = (error) => {
  if (!error || !error.name) {
    return "Camera unavailable";
  }

  if (error.name === "NotAllowedError" || error.name === "SecurityError") {
    return "Permission denied";
  }

  if (error.name === "NotFoundError" || error.name === "DevicesNotFoundError") {
    return "No camera device found";
  }

  if (error.name === "NotReadableError" || error.name === "TrackStartError") {
    return "Camera already in use";
  }

  if (error.name === "OverconstrainedError" || error.name === "ConstraintNotSatisfiedError") {
    return "Requested camera mode not supported";
  }

  return "Camera unavailable";
};

const stopCamera = () => {
  stopVisionOverlayPipeline();

  if (!cameraStream) {
    setCameraMessage("Stopped");
    setSignalLight("standby");
    return;
  }

  cameraStream.getTracks().forEach((track) => track.stop());
  cameraStream = null;

  if (cameraVideo) {
    cameraVideo.srcObject = null;
  }

  if (cameraPlaceholder) {
    cameraPlaceholder.hidden = false;
  }

  if (cameraResolution) {
    cameraResolution.textContent = "Resolution : -";
  }

  setCameraMessage("Stopped");
  setSignalLight("standby");
};

const startCamera = async () => {
  if (!cameraVideo) {
    return;
  }

  if (!window.isSecureContext) {
    setCameraMessage("Open with https or localhost");
    return;
  }

  const hasModernApi = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
  const hasLegacyApi = !!getLegacyGetUserMedia();

  if (!hasModernApi && !hasLegacyApi) {
    setCameraMessage("Camera API is not supported");
    return;
  }

  if (cameraStream) {
    setCameraMessage("Running");
    return;
  }

  try {
    setCameraMessage("Requesting permission...");
    appendLog("CAM", "Requesting camera permission");

    try {
      cameraStream = await requestCameraStream({
        video: {
          facingMode: { ideal: "environment" },
        },
        audio: false,
      });
    } catch (primaryError) {
      // Retry with a relaxed constraint for laptops/VM cameras that ignore facingMode.
      cameraStream = await requestCameraStream({
        video: true,
        audio: false,
      });
      console.warn("Primary camera constraint failed, used fallback:", primaryError);
      appendLog("CAM", "Primary camera constraint failed, fallback applied");
    }

    cameraVideo.srcObject = cameraStream;
    await cameraVideo.play();

    if (cameraPlaceholder) {
      cameraPlaceholder.hidden = true;
    }

    setCameraResolution();
    setCameraMessage("Running");
    appendLog("CAM", "Camera stream started");

    if (currentMode === "auto") {
      startVisionOverlayPipeline();
    }
  } catch (error) {
    console.error("Camera start failed:", error);
    setCameraMessage(mapCameraErrorToStatus(error));
    appendLog("ERROR", "Camera start failed");
  }
};

const captureSnapshot = () => {
  if (!cameraVideo || !cameraCanvas || !cameraStream) {
    setCameraMessage("Start camera first");
    return;
  }

  const width = cameraVideo.videoWidth;
  const height = cameraVideo.videoHeight;

  if (!width || !height) {
    setCameraMessage("No frame available");
    return;
  }

  cameraCanvas.width = width;
  cameraCanvas.height = height;

  const context = cameraCanvas.getContext("2d");
  if (!context) {
    setCameraMessage("Capture unavailable");
    return;
  }

  context.drawImage(cameraVideo, 0, 0, width, height);
  setCameraMessage("Snapshot captured");
  appendLog("CAPTURE", `${width}x${height} frame captured`);
};

modeButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const mode = button.dataset.mode;

    if (mode === "result") {
      openResultPopup();
      return;
    }

    const targetPath = MODE_ROUTE_MAP[mode];

    if (targetPath && targetPath !== currentPath) {
      appendLog("NAV", `Move to ${mode}`);
      window.location.href = targetPath;
      return;
    }

    setMode(mode);
  });
});

if (logoutBtn) {
  logoutBtn.addEventListener("click", async () => {
    appendLog("AUTH", "Logout requested");
    await logoutAndRedirect();
  });
}

if (ttsToggle instanceof HTMLInputElement) {
  const savedTts = localStorage.getItem(TTS_ENABLED_KEY);
  ttsToggle.checked = savedTts === null ? true : savedTts === "true";
}

if (sttToggle instanceof HTMLInputElement) {
  const savedStt = localStorage.getItem(STT_ENABLED_KEY);
  setSttEnabled(savedStt === null ? true : savedStt === "true");
}

if (webSearchToggle instanceof HTMLInputElement) {
  const savedWebSearch = localStorage.getItem(WEB_SEARCH_ENABLED_KEY);
  webSearchToggle.checked = savedWebSearch === "true";
  webSearchToggle.addEventListener("change", () => {
    localStorage.setItem(WEB_SEARCH_ENABLED_KEY, webSearchToggle.checked ? "true" : "false");
    appendLog("CHAT", `Web search ${webSearchToggle.checked ? "enabled" : "disabled"}`);
  });
}

syncTtsStopButton();

if (askForm && askInput) {
  askForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const question = askInput.value.trim();
    if (!question) {
      return;
    }

    await submitQuestion(question);
    askInput.value = "";
  });
}

if (askUploadBtn instanceof HTMLButtonElement && askUploadInput instanceof HTMLInputElement) {
  askUploadBtn.addEventListener("click", () => {
    closeAskToolsMenu();
    askUploadInput.click();
  });

  askUploadInput.addEventListener("change", async () => {
    const file = askUploadInput.files && askUploadInput.files[0];
    if (!file) {
      return;
    }
    await uploadKnowledgeFile(file);
  });
}

if (micBtn instanceof HTMLButtonElement) {
  micBtn.addEventListener("click", () => {
    closeAskToolsMenu();
    toggleRecording();
  });
}

if (stopTtsBtn instanceof HTMLButtonElement) {
  stopTtsBtn.addEventListener("click", () => {
    closeAskToolsMenu();
    stopSpeech();
  });
}

if (ttsToggle instanceof HTMLInputElement) {
  ttsToggle.addEventListener("change", () => {
    localStorage.setItem(TTS_ENABLED_KEY, ttsToggle.checked ? "true" : "false");
    if (!ttsToggle.checked) {
      stopSpeech();
    } else {
      syncTtsStopButton();
    }
  });
}

if (sttToggle instanceof HTMLInputElement) {
  sttToggle.addEventListener("change", (event) => {
    const target = event.target;
    if (target instanceof HTMLInputElement) {
      setSttEnabled(target.checked);
    }
  });
}

if (askToolsMenu instanceof HTMLDetailsElement) {
  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Node)) {
      return;
    }
    if (askToolsMenu.open && !askToolsMenu.contains(target)) {
      askToolsMenu.open = false;
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && askToolsMenu.open) {
      askToolsMenu.open = false;
    }
  });
}

if (simpleQuestionList instanceof HTMLDivElement) {
  simpleQuestionList.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }

    const button = target.closest(".chat-question-btn");
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }

    const question = button.dataset.question || button.textContent || "";
    if (!question.trim()) {
      return;
    }

    const itemView = ensureSimpleItemChatView(button, question.trim());
    if (!itemView) {
      appendLog("ERROR", "Simple mode chat display is unavailable");
      return;
    }

    const { container, sessionKey, display, input } = itemView;
    container.classList.add("is-loading");
    setSimpleItemPending(container, true);

    submitQuestion(question.trim(), {
      targetDisplay: display,
      useChatFormPending: false,
      showSources: false,
      stripWebLead: true,
      disableAutoWeb: true,
    }).finally(() => {
      simpleSessionHistory.set(sessionKey, display.value);
      container.classList.remove("is-loading");
      setSimpleItemPending(container, false);
      input.focus();
    });
  });

  simpleQuestionList.addEventListener("submit", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLFormElement) || !target.classList.contains("simple-chat-item-form")) {
      return;
    }

    event.preventDefault();
    const container = target.closest(".simple-chat-item-open");
    if (!(container instanceof HTMLElement)) {
      return;
    }

    const sessionKey = container.dataset.sessionKey || "";
    if (!sessionKey.trim() || container.dataset.pending === "true") {
      return;
    }

    const display = container.querySelector(".simple-chat-item-display");
    const input = container.querySelector(".simple-chat-item-input");
    if (!(display instanceof HTMLTextAreaElement) || !(input instanceof HTMLInputElement)) {
      return;
    }

    const question = input.value.trim();
    if (!question) {
      return;
    }

    input.value = "";
    setSimpleItemPending(container, true);
    submitQuestion(question, {
      targetDisplay: display,
      useChatFormPending: false,
      showSources: false,
      stripWebLead: true,
      disableAutoWeb: true,
    }).finally(() => {
      simpleSessionHistory.set(sessionKey.trim(), display.value);
      setSimpleItemPending(container, false);
      input.focus();
    });
  });
}

if (chatTabButtons.length > 0) {
  chatTabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const tabKey = button.dataset.chatTab;
      if (!tabKey) {
        return;
      }

      renderChatTab(tabKey);
      appendLog("TAB", `Switched to ${tabKey}`);
    });
  });

  renderChatTab("simple");
}

renderHandoverBoards();
bindHandoverBoards();
setupChatThread();

if (configTabButtons.length > 0) {
  ensureDefaultConfigSpace();
  bindLanguageSettingControl();

  configTabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const tabKey = button.dataset.configTab;
      if (!tabKey) {
        return;
      }

      renderConfigTab(tabKey);
      appendLog("TAB", `Configuration tab switched to ${tabKey}`);
    });
  });

  const initialConfigTabKey = configTabButtons[0]?.dataset.configTab;
  if (initialConfigTabKey) {
    renderConfigTab(initialConfigTabKey);
  }
}

if (cameraStartBtn) {
  cameraStartBtn.addEventListener("click", () => {
    startCamera();
  });
}

if (cameraStopBtn) {
  cameraStopBtn.addEventListener("click", () => {
    stopCamera();
  });
}

if (cameraShotBtn) {
  cameraShotBtn.addEventListener("click", () => {
    captureSnapshot();
  });
}

if (cameraVideo) {
  cameraVideo.addEventListener("loadedmetadata", () => {
    setCameraResolution();
  });
}

window.addEventListener("beforeunload", () => {
  stopCamera();
  stopFaceCamera();
});

setMode(currentMode);
setOverlayCounts(0, 0);
setSignalLight("standby");
appendLog("INFO", `Dashboard initialized (mode: ${currentMode})`);
loadWorkerNameFromDb();
loadRecommendedQuestions();

// Future detector integration can call this from outside.
window.updateOverlayCounts = setOverlayCounts;
window.onStandby = () => setSignalLight("standby");
window.onOkDetected = () => setSignalLight("ok");
window.onNgDetected = () => setSignalLight("ng");
window.onEquipmentIssue = () => setSignalLight("warning");
window.appendSystemLog = (message) => appendLog("INFO", String(message));

if (currentMode === "iot" && cameraVideo) {
  // IoT mode still uses local camera permission flow.
  startCamera();
}

if (currentMode === "auto") {
  // Auto mode receives already-processed on-prem overlay stream without local camera capture.
  startOnpremOverlayOnly();
}

if (currentPath === "/configuration.html" && faceVideo) {
  startFaceCamera();
}

if (currentPath === "/configuration.html") {
  setSelectedEmployeeNo("");
  loadFaceRegistrations();

  if (faceAccountListBody instanceof HTMLDivElement) {
    faceAccountListBody.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) {
        return;
      }

      const button = target.closest(".configuration-select-btn");
      if (!(button instanceof HTMLButtonElement)) {
        return;
      }

      const employeeNo = button.dataset.employeeNo || "";
      setSelectedEmployeeNo(selectedEmployeeNo === employeeNo ? "" : employeeNo);
      renderFaceRegistrationRows(lastFaceRegistrationItems);
    });
  }

  if (faceRegisterBtn instanceof HTMLButtonElement) {
    faceRegisterBtn.addEventListener("click", () => {
      submitFaceRegistration();
    });
  }

  if (faceAccountKeywordInput instanceof HTMLInputElement) {
    faceAccountKeywordInput.addEventListener("input", () => {
      if (faceRegistrationSearchTimer) {
        clearTimeout(faceRegistrationSearchTimer);
      }

      faceRegistrationSearchTimer = setTimeout(() => {
        loadFaceRegistrations(faceAccountKeywordInput.value.trim());
      }, 250);
    });
  }
}
