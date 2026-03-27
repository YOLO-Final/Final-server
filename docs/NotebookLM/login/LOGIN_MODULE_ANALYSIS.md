# NotebookLM 업로드용 기능 분석 문서 초안

대상 기준 파일: `/nginx/html/login.html`

분석 기준

- `확인 완료`: 실제 코드에서 import, script 참조, fetch 경로, DOM selector, redirect, ORM query로 연결이 확인된 항목
- `간접 연관`: 로그인 성공 후 후속 화면, 공통 토큰 소비, Face ID 운영 기능처럼 직접 진입은 아니지만 로그인 모듈 이해에 필요한 항목
- `후보/미연결`: 파일명이나 API는 존재하지만 `login.html` 기준 실제 호출 연결은 확인되지 않은 항목

---

# 1. 기능 개요

- 로그인 화면의 목적: 생산/검사 대시보드 진입 전 사용자 인증을 수행하는 프론트 진입 화면이다.
- 기본 진입 경로: `/nginx/html/index.html`이 즉시 `/login.html`로 리다이렉트한다.
- 지원 로그인 방식:
  - 아이디/비밀번호 로그인
  - Face ID 로그인
  - Face ID는 수동 버튼 클릭뿐 아니라 Face 탭 진입 시 자동 재시도 루프도 수행한다.
- 주요 사용자 시나리오:
  - 작업자가 사원번호와 비밀번호를 입력하고 로그인한다.
  - 작업자가 Face ID 탭에서 카메라를 켜고 얼굴 인증으로 로그인한다.
  - 로그인 성공 후 `localStorage`에 인증 정보를 저장하고 `/auto.html`로 이동한다.
  - 이후 `/auto.html`의 `/js/dashboard.js`가 저장된 토큰을 사용해 사용자 이름 조회, 토큰 갱신, 로그아웃을 처리한다.
- 로그인 성공 후 도착 화면: `/nginx/html/auto.html`
- 로그인 관련 핵심 키워드:
  - DOM: `#login-form`, `#employee_no`, `#password`, `#login-error`, `#face-video`, `#face-status`, `#camera-start`, `#camera-stop`, `#face-login`, `#fix-password`
  - Storage: `rss-auth`, `rss-user-employee-no`, `rss-access-token`, `rss-refresh-token`
  - API: `/api/v1/auth/login`, `/api/v1/auth/login/face`, `/api/v1/auth/refresh`, `/api/v1/auth/users/{employee_no}`

정리 메모

- `login.html` 자체에는 API 호출이 없고, 모든 동작은 `/nginx/html/js/login.js`로 위임된다.
- `비밀번호 수정` 문구는 화면에 존재하지만, 현재 `login.html` 기준 클릭 이벤트나 API 연결은 없다.

# 2. FE 관련 파일 목록

| 파일 경로 | 역할 | login 기능과의 연관성 | 핵심 함수/핵심 요소 | 반드시 봐야 하는 이유 | 연결 수준 / 근거 |
|---|---|---|---|---|---|
| `/nginx/html/index.html` | 기본 진입 HTML | 앱 첫 진입 시 로그인 화면으로 보냄 | `<meta http-equiv="refresh" content="0; url=/login.html">` | 사용자가 실제로 어떤 URL에서 로그인 화면에 도달하는지 보여준다. | `확인 완료` / `/login.html`로 즉시 리다이렉트 |
| `/nginx/html/login.html` | 로그인 UI 본체 | 분석 기준 파일 | 비밀번호 탭, Face ID 탭, `#login-form`, `#login-error`, `#face-status`, `#fix-password` | 화면 구성요소와 로그인 방식 2개가 모두 여기서 시작된다. | `확인 완료` / `<script src="/js/login.js">`, `<link rel="stylesheet" href="/css/style.css">` |
| `/nginx/html/js/login.js` | 로그인 메인 로직 | 실제 이벤트 시작점, API 호출, 토큰 저장, 리다이렉트 담당 | `storeAuthSession()`, `attemptFaceLogin()`, `setActiveLoginTab()`, `startAutoFaceLogin()` | 로그인 모듈의 핵심 코드다. 비밀번호 로그인, Face ID, 카메라, 에러 메시지, 자동 로그인 루프가 모두 여기에 있다. | `확인 완료` / `fetch("/api/v1/auth/login")`, `fetch("/api/v1/auth/login/face")`, `window.location.href="/auto.html"` |
| `/nginx/html/css/style.css` | 로그인 화면 전용 스타일 | `login.html`의 직접 CSS | `.login-tab`, `.login-pane`, `.face-video`, `.error`, `.muted` | 어떤 영역이 상태 메시지인지, Face ID 영역이 어떻게 구성되는지 UI 기준 설명에 필요하다. | `확인 완료` / `login.html`이 직접 참조 |
| `/nginx/html/auto.html` | 로그인 성공 후 도착 화면 | 성공 시 첫 이동 목적지 | `<script src="/js/dashboard.js">`, `#logout-btn`, `.worker-name` | 로그인 성공 후 사용자가 실제로 도착하는 화면이므로 “로그인 완료 후 무엇이 시작되는가”를 설명할 때 필수다. | `확인 완료` / `login.js`가 `/auto.html`로 이동 |
| `/nginx/html/js/dashboard.js` | 후속 대시보드 공통 로직 | 로그인 세션 소비, 토큰 refresh, 사용자 이름 조회, 로그아웃 담당 | `authFetch()`, `refreshAccessToken()`, `loadWorkerNameFromDb()`, logout click handler | 로그인 직후 저장한 토큰이 이후 어디서 어떻게 사용되는지 보여준다. | `확인 완료` / `rss-*` 키를 읽고 `/api/v1/auth/refresh`, `/api/v1/auth/users/{employee_no}` 호출 |
| `/nginx/html/configuration.html` | 로그인 후 Face ID 운영 화면 | Face ID 등록/조회 UI 제공 | `#face-video`, `#face-register-btn`, `#face-account-list-body` | Face ID 로그인만 보면 저장소 생성 경로가 빠지므로, 운영자가 얼굴 정보를 어떻게 등록하는지 함께 봐야 한다. | `간접 연관` / 로그인 후 메뉴 이동 화면 |
| `/nginx/html/css/ui.css` | 로그인 후 대시보드 스타일 | `/auto.html`, `/configuration.html` 등 후속 페이지 공통 스타일 | `.head-logout-btn` 등 | 로그인 성공 후 화면의 공통 헤더/로그아웃 UI를 설명할 때 필요하다. | `간접 연관` / 후속 화면들이 직접 참조 |
| `/nginx/html/js/wed_dashboard/dashboard_api.js` | 다른 대시보드 계열의 API 래퍼 | `rss-access-token`, `rss-refresh-token`를 fallback으로 읽음 | `getAccessToken()`, `getRefreshToken()`, `refreshAccessToken()` | 메인 로그인 토큰 체계가 일부 다른 화면에서도 재사용될 수 있음을 보여주는 간접 단서다. | `간접 연관` / `localStorage.getItem('rss-access-token')` fallback 존재 |

FE 관찰 포인트

- 이벤트 시작점:
  - 비밀번호 로그인: `#login-form`의 `submit`
  - Face ID 수동 로그인: `#face-login`의 `click`
  - Face ID 자동 로그인: Face 탭 활성화 후 `setInterval()`로 `attemptFaceLogin({ trigger: "auto" })`
- 에러 표시:
  - 비밀번호 로그인: `#login-error.textContent`
  - Face ID 로그인: `setFaceStatus(message, isError)`
- 토큰 저장:
  - `localStorage.setItem("rss-auth", "true")`
  - `localStorage.setItem("rss-user-employee-no", ...)`
  - `localStorage.setItem("rss-access-token", ...)`
  - `localStorage.setItem("rss-refresh-token", ...)`
- 비밀번호 수정:
  - `#fix-password` 요소는 존재하지만 `login.js`에서 selector로 읽지 않으며 클릭 이벤트도 없다.
- 쿠키/세션스토리지 사용:
  - `login.html` 메인 흐름에서는 쿠키와 `sessionStorage`를 쓰지 않는다.
  - 메인 로그인은 `localStorage` 기반이다.

# 3. BE 관련 파일 목록

| 파일 경로 | 계층 | 역할 | login 기능과의 연관성 | 핵심 함수 | 반드시 봐야 하는 이유 |
|---|---|---|---|---|---|
| `/server_api/src/main.py` | 앱 엔트리 | FastAPI 앱 생성, 라우터 등록, 테이블 자동 생성, admin 시드 실행 | 로그인 테이블이 런타임에 어떻게 준비되는지 보여준다. | `on_startup()` | 인증 테이블 생성과 시드가 여기서 시작된다. |
| `/server_api/src/api/v1/router.py` | 상위 라우터 | `/api/v1` 하위에 auth 라우터 포함 | FE가 호출하는 `/api/v1/auth/*` 경로의 상위 prefix를 확정한다. | `api_v1_router.include_router(auth_router)` | 프론트 경로와 백엔드 실제 prefix를 연결할 수 있다. |
| `/server_api/src/lib/settings.py` | 설정 | API prefix, DB URL 정의 | `/api/v1` prefix와 PostgreSQL 연결 문자열 근거 | `Settings.api_v1_prefix`, `Settings.database_url` | 인증 경로와 DB 연결의 기본 설정값을 제공한다. |
| `/server_api/src/lib/database.py` | DB 공통 | SQLAlchemy engine/session 생성 | auth service가 어떤 DB 세션을 쓰는지 보여준다. | `engine`, `SessionLocal`, `get_db()` | 인증 로직이 ORM 세션 기반임을 확인할 수 있다. |
| `/server_api/src/modules/auth/router.py` | route/controller 역할 | 인증 API 엔드포인트 정의 | 비밀번호 로그인, Face ID 로그인, refresh, 사용자 조회, 비밀번호 변경, logout 모두 여기서 노출된다. | `login()`, `face_login()`, `refresh_token()`, `auth_user_profile()`, `update_password()`, `logout()` | FE fetch 경로를 실제 백엔드 함수로 매핑하는 첫 지점이다. |
| `/server_api/src/modules/auth/service.py` | service | 인증 핵심 비즈니스 로직 | 사용자 조회, 비밀번호 검증, 계정 잠금, 토큰 발급, Face ID 매칭, Face 등록, password 변경 처리 | `login_with_password()`, `face_login_with_matching()`, `refresh_access_token()`, `get_auth_user_profile()`, `register_face_embedding()`, `change_password()` | 로그인 처리 흐름의 핵심이다. auth 모듈에는 별도 repository 계층이 없고 이 파일이 직접 ORM query를 수행한다. |
| `/server_api/src/modules/auth/jwt.py` | auth utility | JWT 발급/복호화/현재 사용자 조회 | access/refresh token 구조와 `token_version` 무효화 정책이 여기서 결정된다. | `create_access_token()`, `create_refresh_token()`, `decode_token()`, `get_current_user()` | 세션이 아니라 JWT 기반 인증이라는 점과 refresh 구조를 설명할 때 필수다. |
| `/server_api/src/modules/auth/vision/service.py` | Face ID 엔진 | Base64 이미지 복호화, InsightFace 임베딩 추출 | `/auth/login/face`, `/auth/face/register`의 얼굴 특징 추출에 직접 사용된다. | `_decode_base64_image()`, `_get_face_analyzer()`, `extract_face_embedding()` | Face ID가 단순 플래그가 아니라 실제 얼굴 임베딩 기반임을 보여준다. |
| `/server_api/src/modules/auth/db/schema.py` | request/response schema | 인증 API 입출력 스키마 정의 | FE가 보내는 JSON과 서버가 반환하는 payload 구조를 확인할 수 있다. | `LoginRequest`, `FaceLoginRequest`, `RefreshTokenResponse`, `ChangePasswordRequest` | 보고서에서 API 명세를 정리할 때 바로 활용 가능하다. |
| `/server_api/src/modules/auth/db/model.py` | ORM model | Face 관련 테이블 매핑 | Face ID 저장 테이블과 상태 조회용 벡터 테이블을 정의한다. | `FaceEmbeddingTable`, `VectorTable` | Face 정보가 DB에 어떻게 저장되는지 파악하는 핵심 파일이다. |
| `/server_api/src/modules/db/users/db/model.py` | ORM model | 사용자 테이블 매핑 | 로그인 성공/실패, 활성화/잠금, 권한, 마지막 로그인 시간이 모두 여기 있다. | `UserTable` | 비밀번호 로그인과 Face 로그인이 공통으로 의존하는 사용자 저장소다. |
| `/server_api/src/modules/db/users/seed.py` | seed | 개발/비운영용 admin 계정 생성 | 초기 로그인 테스트 계정 생성 로직 | `seed_test_admin_user()` | 운영/테스트 환경 차이와 기본 계정 생성 규칙을 설명할 수 있다. |
| `/server_api/src/modules/auth/logger.py` | logger | auth 전용 콘솔 로그 | 로그인 성공/실패/Face 등록/삭제 로그를 DB가 아닌 콘솔로 남긴다. | `auth_logger` | 감사 로그가 테이블이 아니라 docker logs 성격이라는 점을 설명할 때 필요하다. |

BE 구조 요약

- route → service → model/DB 형태다.
- `auth` 모듈에는 별도 repository 계층이 없다.
- `router.py`가 사실상 controller 역할을 수행하고, `service.py`가 `Session.query(...)`로 바로 DB를 조회한다.

# 4. DB 관련 요소 목록

| 테이블/엔티티/스키마명 | 관련 컬럼 | 사용 목적 | 어떤 코드에서 참조되는지 | 실제 사용 여부 |
|---|---|---|---|---|
| `user_table` | `employee_no`, `password_hash`, `id_active`, `id_locked`, `login_fail_count`, `token_version`, `last_login`, `role`, `name` | 사용자 인증, 계정 상태 확인, 권한 확인, 마지막 로그인 시간 기록 | `auth/service.py`의 `login_with_password()`, `face_login_with_matching()`, `refresh_access_token()`, `get_auth_user_profile()`, `get_web_login_profile()` / `auth/jwt.py`의 `get_current_user()` | `실제 사용` |
| `face_embedding_table` | `employee_no`, `embedding_json` | Face ID 1:1/1:N 매칭용 원본 임베딩 저장 | `auth/service.py`의 `face_login_with_matching()`, `register_face_embedding()`, `delete_face_embedding()` / ORM: `auth/db/model.py` | `실제 사용` |
| `vector_table` | `employee_no`, `face_embedding` | Face 등록 여부 조회용 보조 저장소 | `auth/service.py`의 `list_face_registration_status()`, `register_face_embedding()`, `delete_face_embedding()` / ORM: `auth/db/model.py` | `실제 사용` |
| `lines` | `line_id` | 사용자의 라인 배정 FK 대상 | DB 인벤토리에는 `user_table.line_id -> lines.line_id`가 존재 / auth service의 `create_user()`, `update_line_id()`는 `line_id`를 의도함 | `로그인 경로에서는 미사용` |
| `login_history` 또는 별도 `audit_log` 테이블 | 확인된 컬럼 없음 | 로그인 이력/감사 로그 전용 저장소 후보 | 코드상 직접 참조 없음 / `common/audit.py`는 placeholder / `auth/logger.py`는 콘솔 로그 | `미구현 또는 미사용` |

DB 코드 근거 정리

- ORM 사용: SQLAlchemy Declarative Model
- DB 연결: PostgreSQL (`postgresql+psycopg://FP_ADMIN:FP_PASSWORD@postgres:5432/Final_Project_DB`)
- 테이블 생성 방식: `Base.metadata.create_all(bind=engine)`
- raw SQL 여부:
  - 인증 로그인 경로에서 raw SQL은 확인되지 않았다.
  - PostgreSQL 함수 호출은 `register_face_embedding()`의 `func.to_tsvector("simple", vector_literal)`만 확인됐다.

실제 사용 컬럼 vs 후보/불일치

- `확인 완료`
  - `user_table.employee_no`
  - `user_table.password_hash`
  - `user_table.id_active`
  - `user_table.id_locked`
  - `user_table.login_fail_count`
  - `user_table.token_version`
  - `user_table.last_login`
  - `user_table.role`
  - `user_table.name`
  - `face_embedding_table.employee_no`
  - `face_embedding_table.embedding_json`
  - `vector_table.employee_no`
  - `vector_table.face_embedding`
- `후보/불일치`
  - DB 인벤토리에는 `user_table.line_id`가 존재하지만, `/server_api/src/modules/db/users/db/model.py`의 `UserTable` ORM에는 해당 컬럼이 없다.
  - DB 인벤토리에는 `face_embedding_table.embedding_id`가 존재하지만, `/server_api/src/modules/auth/db/model.py` ORM에는 매핑돼 있지 않다.
  - 따라서 현재 코드와 실제 DB 스냅샷 사이에 스키마 차이가 있다.

# 5. 로그인 기능 호출 흐름

## 5-1. 비밀번호 로그인 흐름

1. 사용자가 `/nginx/html/login.html`의 `#employee_no`, `#password`를 입력한다.
2. `#login-form` submit 이벤트가 `/nginx/html/js/login.js`에서 가로채진다.
3. 입력값이 비어 있으면 `#login-error`에 `"사번과 비밀번호를 모두 입력해 주세요."`를 표시하고 종료한다.
4. 값이 있으면 `fetch("/api/v1/auth/login", { method: "POST" ... })`로 `employee_no`, `password`를 전송한다.
5. `/server_api/src/modules/auth/router.py`의 `POST /auth/login`이 `login_with_password()`를 호출한다.
6. `/server_api/src/modules/auth/service.py`의 `login_with_password()`가 `user_table`에서 `employee_no`로 사용자를 조회한다.
7. 서버는 다음 순서로 검증한다.
   - 사용자 존재 여부
   - `id_active` 여부
   - `id_locked` 여부
   - `_verify_password()`로 비밀번호 검증
8. 비밀번호 검증 로직은 해시 형식에 따라 분기한다.
   - 64자리 SHA-256이면 `_legacy_sha256()`로 비교
   - bcrypt 해시(`$2` prefix)면 `bcrypt.checkpw()`로 비교
9. 실패 시 `login_fail_count`를 1 증가시키고, 5회 이상이면 `id_locked = True`, `token_version += 1`로 잠근 뒤 `401`을 반환한다.
10. 성공 시 필요하면 legacy SHA-256 해시를 bcrypt로 업그레이드하고, `login_fail_count = 0`, `last_login = datetime.utcnow()`로 갱신한다.
11. 서버는 `create_access_token()`과 `create_refresh_token()`으로 JWT 2개를 발급해 응답한다.
12. 프론트는 `storeAuthSession()`에서 아래 값을 `localStorage`에 저장한다.
   - `rss-auth = "true"`
   - `rss-user-employee-no = employee_no`
   - `rss-access-token`
   - `rss-refresh-token`
13. 프론트는 `window.location.href = "/auto.html"`로 이동한다.
14. `/nginx/html/js/dashboard.js`는 진입 후 `rss-auth`를 검사하고, `loadWorkerNameFromDb()`에서 `/api/v1/auth/users/{employee_no}`를 호출해 사용자명을 표시한다.
15. 이후 보호 API가 `401`을 반환하면 `authFetch()`가 `/api/v1/auth/refresh`로 access token을 재발급받는다.

## 5-2. Face ID 로그인 흐름

1. 사용자가 `/nginx/html/login.html`에서 `Face ID` 탭으로 전환한다.
2. `setActiveLoginTab("panel-face")`가 실행되며 `startCamera()`가 호출된다.
3. 카메라가 준비되면 `startAutoFaceLogin()`이 시작되고, 1.8초마다 `attemptFaceLogin({ trigger: "auto" })`가 실행된다.
4. 사용자가 직접 `#face-login` 버튼을 누르면 `attemptFaceLogin({ trigger: "manual" })`가 실행된다.
5. `attemptFaceLogin()`은 다음 순서로 동작한다.
   - Face 탭 활성 여부 확인
   - 카메라 준비
   - 비디오 프레임 준비 대기
   - `canvas.toDataURL("image/jpeg", 0.9)`로 얼굴 프레임 캡처
   - `/api/v1/auth/login/face`로 `employee_no`, `image_base64` 전송
6. 서버의 `face_login_with_matching()`은 `/server_api/src/modules/auth/vision/service.py`의 `extract_face_embedding()`으로 얼굴 임베딩을 생성한다.
7. 매칭 방식은 두 갈래다.
   - `employee_no`가 있으면 `face_embedding_table` 한 건만 조회하는 1:1 비교
   - `employee_no`가 없으면 `face_embedding_table` 전체를 순회하는 1:N 비교
8. 유사도 계산은 `_cosine_similarity()`로 수행하고, 임계값은 환경변수 `FACE_MATCH_THRESHOLD` 또는 기본값 `0.30`을 사용한다.
9. 매칭 성공 시 `user_table`에서 해당 사용자를 조회해 `id_active`, `id_locked`를 다시 검증한다.
10. 성공하면 `last_login`을 갱신하고 access/refresh token을 발급한다.
11. 프론트는 비밀번호 로그인과 동일하게 `storeAuthSession()`을 수행하고 `/auto.html`로 이동한다.
12. 실패 시 상태 코드는 프론트에서 다음 문구로 매핑된다.
   - `401`: 얼굴 불일치
   - `404`: 등록된 Face ID 없음
   - `422`: 얼굴 인식/이미지 처리 실패
   - `503`: Face 엔진 준비 실패

## 5-3. 자동 로그인 / 토큰 재사용 흐름

1. 메인 로그인 화면의 “자동 로그인” 체크박스는 없다.
2. 대신 Face ID 탭에는 자동 얼굴 재시도 루프가 있다.
3. 로그인 성공 후에는 `localStorage`의 refresh token을 사용해 `/nginx/html/js/dashboard.js`가 `/api/v1/auth/refresh`를 호출한다.
4. refresh 성공 시 새 access token만 갱신하고, 실패하면 저장된 인증 정보를 삭제한 뒤 `/login.html`로 되돌린다.

## 5-4. Face ID 등록 흐름

1. 로그인 후 `/configuration.html`로 이동한다.
2. `/nginx/html/js/dashboard.js`가 `/api/v1/auth/face/registrations`를 호출해 등록 상태 목록을 불러온다.
3. 운영자가 사원번호를 선택하고 카메라 프레임을 캡처한 뒤 `/api/v1/auth/face/register`를 호출한다.
4. 서버의 `register_face_embedding()`은 같은 이미지를 임베딩으로 변환한 후:
   - `vector_table`을 upsert
   - `face_embedding_table`을 upsert
5. 이 등록 경로가 있어야 Face ID 로그인 경로가 정상적으로 동작한다.

## 5-5. 비밀번호 수정 흐름

1. 백엔드에는 `PATCH /api/v1/auth/users/{employee_no}/password`가 존재한다.
2. 서버는 `current_password`, `new_password`, `new_password_confirm`를 검증하고 성공 시 `password_hash`를 갱신하며 `token_version += 1`을 수행한다.
3. 그러나 현재 `login.html` 기준 프론트에서는 이 API를 호출하는 코드가 없다.
4. 결론적으로 “비밀번호 수정”은 UI 텍스트와 서버 API는 있으나, 메인 로그인 화면에서는 미연결 상태다.

## 5-6. 로그아웃 흐름

1. 백엔드에는 `POST /api/v1/auth/logout`이 존재하며, 호출 시 `token_version += 1`로 서버 토큰을 무효화한다.
2. 하지만 현재 `/nginx/html/js/dashboard.js`의 로그아웃 버튼은 이 API를 호출하지 않는다.
3. 실제 프론트 동작은 `localStorage`에서 인증 키를 지우고 `/login.html`로 이동하는 것뿐이다.
4. 따라서 현재 메인 대시보드 로그아웃은 “클라이언트 측 세션 정리”이며, 서버 측 refresh/access token 강제 무효화 API는 미사용이다.

# 6. 보고서/PPT 작성용 모듈 설명

## 모듈 A. 로그인 화면 모듈

- 화면(UI) 관점: 하나의 카드 안에 `아이디/비밀번호`와 `Face ID` 두 탭이 공존하는 구조다. 비밀번호 폼과 카메라 비디오 패널이 같은 페이지에서 전환된다.
- 기능 관점: 비밀번호 로그인, Face ID 로그인, Face ID 자동 재시도, 에러/상태 메시지 표시까지 한 파일(`/js/login.js`)에 모여 있다.
- 데이터 관점: 입력 데이터는 `employee_no`, `password`, `image_base64` 세 종류이며, 출력 데이터는 `employee_no`, access token, refresh token이다.
- 기술 관점: 바닐라 JS, Fetch API, `navigator.mediaDevices.getUserMedia`, Canvas Base64 캡처, `localStorage`를 사용한다.
- 발표 때 설명하면 좋은 포인트: “한 화면에서 텍스트 기반 인증과 비전 기반 인증을 동시에 제공한다”는 점, 그리고 Face ID 탭 진입 시 자동 재시도 루프가 돈다는 점이 눈에 띈다.
- 아직 확인이 더 필요한 부분: `#fix-password` 문구는 존재하지만 실제 비밀번호 변경 화면/모달/라우팅은 연결되지 않았다.

## 모듈 B. 인증 API 모듈

- 화면(UI) 관점: 프론트에서는 보이지 않지만, 실제 사용자가 경험하는 모든 성공/실패 메시지의 근거가 되는 서버 계층이다.
- 기능 관점: 비밀번호 검증, 계정 활성/잠금 확인, JWT 발급, refresh, 사용자 프로필 조회를 담당한다.
- 데이터 관점: `user_table`의 `password_hash`, `id_active`, `id_locked`, `login_fail_count`, `token_version`, `last_login`을 직접 사용한다.
- 기술 관점: FastAPI + SQLAlchemy + bcrypt + JOSE(JWT) 조합이며, repository 계층 없이 service에서 DB를 직접 조회한다.
- 발표 때 설명하면 좋은 포인트: “단순 로그인”이 아니라, 실패 횟수 누적과 계정 잠금, refresh token, token version 무효화까지 포함한 인증 설계라는 점을 강조하면 좋다.
- 아직 확인이 더 필요한 부분: `LoginResponse` 스키마에는 `name`, `role` 필드가 있으나, `login_with_password()`와 `face_login_with_matching()`은 실제로 이를 채워주지 않는다.

## 모듈 C. Face ID 인식 및 저장소 모듈

- 화면(UI) 관점: 사용자는 카메라 영상만 보지만, 서버에서는 등록/로그인 모두 임베딩 벡터 기반으로 처리된다.
- 기능 관점: 로그인 시에는 얼굴 벡터를 추출해 1:1 또는 1:N 매칭을 수행하고, 등록 시에는 벡터를 DB에 upsert한다.
- 데이터 관점: `face_embedding_table.embedding_json`은 실제 매칭용 원본 벡터이고, `vector_table.face_embedding`은 등록 상태 조회용 보조 저장소로 사용된다.
- 기술 관점: OpenCV + NumPy로 이미지 복호화, InsightFace `buffalo_l` 모델로 얼굴 임베딩 추출, cosine similarity 비교를 사용한다.
- 발표 때 설명하면 좋은 포인트: “Face ID 로그인”이 단순 카메라 캡처가 아니라, 별도 등록 저장소와 임계값 비교 로직을 가진 얼굴 인식 파이프라인이라는 점이 핵심이다.
- 아직 확인이 더 필요한 부분: DB 인벤토리의 `embedding_id` 컬럼은 ORM에 반영돼 있지 않아 실제 운영 스키마와 코드 간 차이가 존재한다.

## 모듈 D. 로그인 후 세션 브리지 모듈

- 화면(UI) 관점: 로그인 후 사용자는 `/auto.html`로 이동해 작업자명, 로그아웃 버튼, 검사 화면을 본다.
- 기능 관점: 저장된 토큰을 바탕으로 사용자명 조회, access token refresh, 인증 실패 시 로그인 화면 복귀를 처리한다.
- 데이터 관점: 프론트는 `rss-auth`, `rss-user-employee-no`, `rss-access-token`, `rss-refresh-token`를 소비한다.
- 기술 관점: `authFetch()`가 `401` 발생 시 refresh를 자동 시도하는 구조다.
- 발표 때 설명하면 좋은 포인트: 로그인은 `/login.html`에서 끝나는 것이 아니라 `/auto.html`과 `/js/dashboard.js`에서 이어지는 “세션 브리지”까지 봐야 전체 흐름이 보인다.
- 아직 확인이 더 필요한 부분: 현재 로그아웃은 백엔드 `/auth/logout`을 호출하지 않기 때문에 서버 측 토큰 무효화 설계가 프론트에서는 활용되지 않는다.

## 모듈 E. Face ID 운영/등록 모듈

- 화면(UI) 관점: `/configuration.html`의 `FaceID 설정` 탭에서 카메라, 등록 버튼, 사원 목록이 제공된다.
- 기능 관점: Face ID 로그인 자체보다 한 단계 뒤의 운영 업무인 “누구의 얼굴을 등록할 것인가”를 담당한다.
- 데이터 관점: 사용자 목록은 `user_table`, 등록 상태는 `vector_table`, 실제 얼굴 매칭 데이터는 `face_embedding_table`과 연결된다.
- 기술 관점: 같은 `/js/dashboard.js`가 로그인 후 화면과 운영 등록 화면을 공통 관리한다.
- 발표 때 설명하면 좋은 포인트: Face 로그인 기능이 동작하려면 운영자가 별도 등록 화면에서 임베딩을 생성해야 한다는 점을 설명하면 전체 시스템 그림이 명확해진다.
- 아직 확인이 더 필요한 부분: 등록 삭제 API는 서버에 있으나, 현재 확인한 운영 화면 코드 범위에서는 삭제 버튼 연결은 보이지 않았다.

# 7. 핵심 코드 경로 요약

이 로그인 기능을 빠르게 이해하려면 최소한 아래 순서로 보는 것이 효율적이다.

1. `/nginx/html/login.html`
2. `/nginx/html/js/login.js`
3. `/nginx/html/auto.html`
4. `/nginx/html/js/dashboard.js`
5. `/server_api/src/modules/auth/router.py`
6. `/server_api/src/modules/auth/service.py`
7. `/server_api/src/modules/auth/jwt.py`
8. `/server_api/src/modules/db/users/db/model.py`
9. `/server_api/src/modules/auth/db/model.py`
10. `/server_api/src/modules/auth/vision/service.py`

보조 확인용 파일

- `/server_api/src/modules/auth/db/schema.py`
- `/server_api/src/main.py`
- `/docs/db_inventory/20260314_150341_db_inventory_report.md`
- `/nginx/html/configuration.html`
- `/nginx/html/index.html`

# 8. 불확실하거나 추가 확인이 필요한 지점

- `비밀번호 수정`은 `login.html`에 텍스트만 있고, 메인 프론트에서 실제 클릭 이벤트나 API 호출이 없다.
- `POST /api/v1/auth/logout`은 서버에 존재하지만 현재 `/nginx/html/js/dashboard.js`에서는 호출하지 않는다.
- `/server_api/src/modules/auth/db/crud.py`는 placeholder이며 로그인 경로에서 사용되지 않는다.
- `/server_api/src/modules/common/audit.py`와 `/server_api/src/modules/common/rbac.py`는 placeholder 성격이며, 현재 auth 경로의 실제 권한 처리는 `get_current_user()`와 `current_user.role` 비교로 이뤄진다.
- `/nginx/html/web_login.html`과 `/nginx/html/js/web_login/web_login.js`는 같은 auth API를 사용하는 별도 웹 대시보드용 병렬 로그인 구현이다. `login.html`에서 직접 연결되지는 않는다.
- `/nginx/html/js/wed_dashboard/dashboard_api.js`는 `rss-access-token`과 `rss-refresh-token`를 fallback으로 읽지만, 자체 로그인 화면은 `/web_login.html`을 사용한다. 즉 “간접 공용 토큰 소비 흔적”으로 보는 것이 맞다.
- DB 인벤토리에는 `user_table.line_id`, `face_embedding_table.embedding_id`가 존재하지만, 현재 auth ORM 모델에는 완전히 반영돼 있지 않다.
- 로그인 전용 이력 테이블이나 감사 로그 테이블은 확인되지 않았다. 현재 확인된 기록 수단은 `user_table.last_login`과 `auth_logger` 콘솔 로그뿐이다.
- Face ID 등록 삭제 API(`DELETE /auth/face/{employee_no}`)는 서버에 있으나, 현재 확인한 운영 화면에서 직접 호출하는 FE 코드는 찾지 못했다.

---

최종 판단 요약

- `login.html` 중심 메인 로그인 모듈은 `login.html → login.js → /api/v1/auth/* → auth/router.py → auth/service.py → UserTable / FaceEmbeddingTable / VectorTable → JWT 발급 → auto.html → dashboard.js` 흐름으로 정리된다.
- 메인 로그인 경로의 핵심 저장소는 `user_table`, `face_embedding_table`, `vector_table` 세 개다.
- 보고서 작성 시 “화면 자체”만 보면 놓치기 쉬운 부분은 로그인 후 세션 재사용(`/auto.html`, `/js/dashboard.js`)과 Face ID 사전 등록(`/configuration.html`, `/api/v1/auth/face/register`)이다.
