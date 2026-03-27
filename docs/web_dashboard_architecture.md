# Smart Factory Platform — Web Dashboard 시스템 아키텍처

> 작성일: 2026-03-23
> 대상: PM
> 범위: `web_login.html` / `web_dashboard.html` 및 관련 JS/CSS 정적 파일
> 미포함: PyQt/on-device 흐름 (`login.html`, `js/dashboard.js`)

---

## 1. 전체 구조 개요

```
[ 브라우저 ]
     │
     ├─ /web_login.html  ─────────────────────────────────────────┐
     │    └─ js/web_login/web_login.js                            │
     │                                                             ↓
     └─ /web_dashboard.html ──── js/wed_dashboard/*.js ─── [ Nginx ]
                                                                   │
                                                         (역방향 프록시)
                                                                   │
                                                          [ 백엔드 API ]
                                                          /api/v1/auth/*
                                                          /api/v1/dashboard/*
```

- Nginx가 정적 파일을 서빙하고, `/api/` 경로는 백엔드로 프록시한다.
- 인트라넷 전용 (`INTRANET ONLY` 명시, v2.4.1 / Platform v2.4).

---

## 2. 인증 흐름

### 2-1. 진입 가드 (양방향)

```
/web_login.html 접근              /web_dashboard.html 접근

  세션 있음?                         세션 있음?
     │ YES                              │ NO
     ↓                                 ↓
/web_dashboard.html 이동         /web_login.html 이동
```

세션 유효 판단 기준:
`localStorage.dashboard_auth_v1.loggedIn === true`
**AND** `sessionStorage.sfp_access_token` 존재

둘 중 하나라도 없으면 미인증 처리.

---

### 2-2. 로그인 방식 A — ID/PW

```
[브라우저]                              [백엔드 API]

  POST /api/v1/auth/login
  { employee_no, password }
  ─────────────────────────────────────────→
                                ← { access_token, refresh_token }

  GET /api/v1/auth/web-login-profile/{employee_no}
  Authorization: Bearer {access_token}
  ─────────────────────────────────────────→
                                ← { employee_no, name, role }

  세션 저장 (localStorage + sessionStorage)
  ↓
  /web_dashboard.html 이동
```

---

### 2-3. 로그인 방식 B — Face ID (InsightFace)

```
[브라우저]                              [백엔드 API]

  카메라 스트림 시작 (HTTPS 필수)
  프레임 캡처 (JPEG quality 0.9, max 10fps)
  자동 재시도: 1,800ms 간격

  POST /api/v1/auth/login/face
  { employee_no | null, image_base64 }
  ─────────────────────────────────────────→
                                ← { verified, access_token, ... }

  이후 동일한 finalizeLogin 루틴 진행
  (프로필 조회 → 세션 저장 → 이동)
```

HTTP 상태별 처리:

| 상태 코드 | 처리 |
|---|---|
| 401 | 얼굴 불일치 |
| 404 | 등록 정보 없음 |
| 422 | 얼굴 인식 실패 (조명 부족 등) |
| 503 | 인식 엔진 준비 중 |

---

### 2-4. 세션 저장 구조

```
localStorage
  └─ dashboard_auth_v1     { loggedIn, user, role }
  └─ sfp_saved_id          사원번호 (아이디 저장 체크 시만)

sessionStorage
  └─ sfp_access_token      JWT access token
  └─ sfp_refresh_token     JWT refresh token
  └─ sfp_user              { employee_no, name, role }
```

---

### 2-5. 토큰 자동 갱신

```
API 요청
  │
  ↓ HTTP 401 수신
  POST /api/v1/auth/refresh  { refresh_token }
        │
        ├─ 성공 → 새 access_token을 sessionStorage에 저장
        │          → 원 요청 1회 재시도
        │
        └─ 실패 → 세션 키 3종 전체 삭제
                   → /web_login.html 이동
```

---

### 2-6. 역할 정규화

로그인 후 서버 role 값은 아래 규칙으로 3개 권한 중 하나로 변환된다.
`web_login.js`와 `dashboard_app.js` 양쪽에서 적용된다.

| 서버 값 | 권한 |
|---|---|
| `worker`, `operator` | worker |
| `qa`, `quality_manager` | qa |
| 그 외 | manager |

---

## 3. 역할별 탭 접근 제어

로그인 사용자의 역할에 따라 사이드바 탭이 표시/숨김 처리된다.
(`dashboard_app.js` — `applyRoleTabAccess()`)

```
역할         worker   qa   manager   promo
─────────────────────────────────────────
worker          ✓      ✗      ✗         ✗
qa              ✓      ✓      ✗         ✗
manager         ✓      ✓      ✓         ✓
```

- worker/operator 역할은 필터바 전체가 숨겨진다 (`display:none`).
- worker/operator 역할은 필터 파라미터를 API에 전송하지 않는다.
- 프레젠테이션 모드 버튼(⛶)도 manager 역할에서만 노출된다.

---

## 4. 대시보드 탭 구성

| 탭 | 메뉴명 | 설명 |
|---|---|---|
| `worker` | 작업자 | 내 라인 현황 |
| `qa` | 품질관리자 | 불량·검사 현황 |
| `manager` | 관리자 | OEE·리스크 현황 |
| `promo` | 공용 송출 | 현장 브로드캐스트 |

탭 전환 시 `dashboard_app.js`가 해당 탭 API를 호출하고 `#mainContent`를 교체 렌더한다.
**자동 새로고침: 60초 인터벌** (`document.hidden` 상태 또는 세션 만료 시 중단).

---

## 5. API 구조

### 5-1. 엔드포인트 목록

| 용도 | 메서드 | 경로 |
|---|---|---|
| ID/PW 로그인 | POST | `/api/v1/auth/login` |
| Face ID 로그인 | POST | `/api/v1/auth/login/face` |
| 프로필/역할 조회 | GET | `/api/v1/auth/web-login-profile/{employee_no}` |
| 토큰 갱신 | POST | `/api/v1/auth/refresh` |
| worker 탭 번들 | GET | `/api/v1/dashboard/web/worker` |
| qa 탭 번들 | GET | `/api/v1/dashboard/web/qa` |
| manager 탭 번들 | GET | `/api/v1/dashboard/web/manager` |
| promo 탭 번들 | GET | `/api/v1/dashboard/web/promo` |
| 상세 모달 | GET | `/api/v1/dashboard/detail` |

### 5-2. 필터 쿼리 파라미터 (탭 번들 공통)

worker/operator 역할은 이 파라미터를 전송하지 않는다.

| 파라미터 | 값 |
|---|---|
| `factory` | `본사 1공장` |
| `line` | `LINE-A` / `LINE-B` / `LINE-C` / `LINE-D` |
| `shift` | `주간` / `야간` |
| `period` | (오늘) / `yesterday` / `weekly` |
| `date_from` / `date_to` | 달력 선택 시 `YYYY-MM-DD` 형식, 최대 31일 |

### 5-3. 응답 포맷

백엔드가 번들을 직접 반환하거나 `{ data: bundle }` 래핑 두 형태를 허용한다.
필수 필드: `meta`, `kpis[]`.

### 5-4. API 오류 처리

API 호출 실패 시 mock 데이터로 대체하지 않는다.
`#mainContent`에 "데이터를 불러오지 못했습니다." 메시지를 렌더하고 종료한다.

`dashboard_api.js`의 `getMockBundle(tab)`은 개발/테스트용 참조 데이터이며,
프로덕션 실패 자동 대체 경로로 사용되지 않는다.

---

## 6. 탭별 데이터 명세

### worker

| 필드 | 설명 |
|---|---|
| `kpis[]` | 시간당 생산량 / 라인 생산량 / 최근 10분 NG / 가동률 |
| `lineTemperature` | 설비 온도 (current, warning 70°C, critical 78°C) |
| `statusGrid[]` | AOI·COMPONENT·MOUNT·PRINTER 설비 상태 |
| `actionQueue[]` | 우선순위 기반 조치 목록 |
| `ngTrend[]` | 10분 단위 NG 추이 |
| `ngTypes[]` | 불량 유형별 건수 (파이 차트) |
| `hint` | 힌트 메시지 |
| `globalNotices[]` | 전체 공지 |
| `events[]` | 라인 이벤트 로그 |

### qa

| 필드 | 설명 |
|---|---|
| `kpis[]` | 불량률 / 재검 대기 / 검사 현황 / 총 생산량 |
| `topDefects[]` | 불량 유형 상위 목록 |
| `recheckQueue[]` | 재검 대기 LOT 목록 |
| `defectTrend[]` | 시간별 불량률 추이 (24시간) |
| `issues[]` | 품질 이슈 목록 (원인·조치·담당자 포함) |
| `events[]` | 이벤트 로그 |

### manager

| 필드 | 설명 |
|---|---|
| `kpis[]` | OEE / 목표 달성률 / 총 생산량 / 예상 종료 생산 |
| `managerLineOee[]` | 라인별 OEE vs 목표 (LINE-A~D) |
| `managerProductionTrend[]` | 시간별 실적 vs 계획 |
| `managerDefectTrend[]` | 시간별 불량률 |
| `riskLines[]` | 라인별 리스크 점수·등급 |
| `pendingActions[]` | 보류 조치 목록 |
| `activeAlarms[]` | 활성 알람 (alarmId, line, equip, cause, severity, ack) |
| `events[]` | 이벤트 로그 |

### promo

| 필드 | 설명 |
|---|---|
| `kpis[]` | 오늘 생산량 / 이번 달 생산 / OEE / 불량률 / 납기 달성률 |
| `promoWeekProduction[]` | 주간 생산 실적 vs 목표 |
| `promoLines[]` | 라인별 상태·생산량·OEE |
| `promoTopDefects[]` | 불량 유형 상위 목록 |
| `promoCurrentAlarms[]` | 현재 알람 |
| `promoMonthlyCompare[]` | 월간 지표 비교 |
| `promoTicker[]` | 현장 브로드캐스트 문자열 목록 |

---

## 7. 임계값 정의

`dashboard_thresholds.js`에 하드코딩된 값이다. 백엔드에서 동적으로 받지 않는다.

| KPI | Warning | Critical | 판정 방향 |
|---|---|---|---|
| `worker_recent_10m_ng` | 10건 | 15건 | 높을수록 위험 |
| `qa_defect_rate` | 2.0% | 4.0% | 높을수록 위험 |
| `mgr_oee` | 75% | 65% | 낮을수록 위험 |
| `mgr_achievement` | 80% | 65% | 낮을수록 위험 |

---

## 8. JS 모듈 의존성

HTML 내 로드 순서가 의존성 순서와 동일하다.
`dashboard_app.js`가 아래 전역 객체를 모두 조합한다.

```
[1] dashboard_state.js
      └─ DASH_STATE (현재 탭, 필터, 선택날짜, 다크모드, 번들 캐시)
            ↓
[2] dashboard_thresholds.js
      └─ DASHBOARD_THRESHOLDS (KPI 임계값, 등급 판정 함수)
            ↓
[3] dashboard_api.js
      └─ DASHBOARD_API (fetch, 토큰 갱신, mock 참조 데이터)
            ↓
[4] dashboard_detail_views.js
      └─ 상세 모달 렌더 함수
            ↓
[5] dashboard_charts.js
      └─ CHARTS (Chart.js 래퍼: NG추이, 파이, 바, 생산추이, 불량률, 주간)
            ↓
[6] dashboard_app.js
      └─ 전체 UI 조합 및 렌더 (1~5를 모두 사용)
```

Chart.js 4.4.1 로컬 번들(`js/vendor/chart.umd.min.js`) 우선,
로드 실패 시 CDN 자동 대체.

---

## 9. UI 레이아웃 구조

```
┌─────────────────────────────────────────────────────────┐
│  .app-shell                                             │
│  ┌──────────┐  ┌──────────────────────────────────────┐ │
│  │ .sidebar │  │ .main-area                           │ │
│  │          │  │ ┌──────────────────────────────────┐ │ │
│  │ [브랜드] │  │ │ .top-header                      │ │ │
│  │          │  │ │  breadcrumb | 날짜 | 알림 | 테마  │ │ │
│  │ [worker] │  │ └──────────────────────────────────┘ │ │
│  │ [qa]     │  │ ┌──────────────────────────────────┐ │ │
│  │ [manager]│  │ │ .filter-bar (worker 역할 시 숨김)│ │ │
│  │ ─────── │  │ │  공장 | 라인 | 근무조 | 기간     │ │ │
│  │ [promo]  │  │ └──────────────────────────────────┘ │ │
│  │          │  │ ┌──────────────────────────────────┐ │ │
│  │ [사용자] │  │ │ .date-banner (날짜 선택 시 노출) │ │ │
│  │ [로그아웃]│  │ └──────────────────────────────────┘ │ │
│  └──────────┘  │ ┌──────────────────────────────────┐ │ │
│                │ │ .content-scroll > #mainContent   │ │ │
│                │ │   ← 탭 전환 시 교체 렌더          │ │ │
│                │ └──────────────────────────────────┘ │ │
│                └──────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘

#detailModal  ← 목록 클릭 시 overlay로 노출되는 공용 상세 모달
```

---

## 10. 보안 사항 (코드 명시 기준)

| 항목 | 내용 |
|---|---|
| 인증 방식 | bcrypt + JWT (로그인 페이지 하단 표기) |
| 전송 암호화 | AES-256 (로그인 페이지 하단 표기) |
| Face ID 카메라 | `window.isSecureContext` 체크 → HTTPS/localhost 환경만 허용 |
| XSS 방어 | `dashboard_app.js`의 `esc()` 함수로 모든 동적 HTML 출력 이스케이프 |
| 인증 오류 | 세션 키 3종 전체 삭제 후 `/web_login.html` 이동 |

---

## 11. 버전 관리

JS/CSS 파일에 쿼리스트링 버전 태그를 수동으로 붙여 캐시를 무효화한다.

```
dashboard_app.js?v=20260323-role-tabs3
dashboard_api.js?v=20260319-api-live-only1
dashboard_charts.js?v=20260320-xaxis-format1
dashboard_style.css?v=20260323-promo-balance3
```
