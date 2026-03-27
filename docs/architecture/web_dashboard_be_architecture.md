# web_dashboard.html — 백엔드 아키텍처

> 작성일: 2026-03-20
> 대상 파일: `nginx/html/web_dashboard.html`
> 범위: 대시보드 화면과 직접 연결되는 BE 파일 및 데이터 흐름

---

## 1. 전체 구조 (Docker Compose)

```
[브라우저]
    │  HTTPS :40943
    ▼
[Nginx webserver]          ← 정적 파일 서빙 + 리버스 프록시
    │  /api/* → HTTP proxy
    ▼
[FastAPI server_api :8000] ← REST API 서버 (Python 3.12)
    │  SQLAlchemy engine
    ▼
[PostgreSQL :5432]         ← 메인 DB  (schema: wed_dashboard)
    +
[Redis :6379]              ← 세션/토큰 캐시
```

---

## 2. 핵심 BE 파일 목록

### 2-1. 진입점 & 설정

| 파일 | 역할 |
|---|---|
| `server_api/src/main.py` | FastAPI 앱 생성, 시작 시 테이블 생성 + 더미 데이터 시드 |
| `server_api/src/api/v1/router.py` | 전체 모듈 라우터 집계 |
| `server_api/src/lib/database.py` | `engine`, `SessionLocal`, `get_db()` |
| `server_api/src/lib/settings.py` | DB URL, API 버전 prefix 등 환경 설정 |
| `server_api/src/lib/env_loader.py` | `.env` 파일 로드 |
| `nginx/conf.d/default.conf` | HTTP→HTTPS 리다이렉트, `/api/*` 프록시 규칙 |
| `compose.yml` | 4개 서비스(webserver/server_api/postgres/redis) 오케스트레이션 |

### 2-2. Dashboard 모듈 (`modules/dashboard/`) ★ 핵심

| 파일 | 역할 |
|---|---|
| `router.py` | 8개 엔드포인트 정의, JWT 의존성 주입 |
| `service.py` | KPI 계산, OEE 산출, 불량률 분석, 시나리오 시간 처리 |
| `repository.py` | `engine.connect()` + `text()` raw SQL로 집계 쿼리 실행 |
| `schemas.py` | Pydantic 응답 모델 (KpiItem, DashboardKPIResponse 등) |
| `db/model.py` | SQLAlchemy ORM 테이블 21개 정의 |

### 2-3. Auth 모듈 (`modules/auth/`) — 대시보드 JWT 검증 의존

| 파일 | 역할 |
|---|---|
| `router.py` | 로그인/로그아웃/토큰갱신/사용자 CRUD/얼굴인식 엔드포인트 |
| `service.py` | 비밀번호 해시 검증, JWT 발급, 얼굴 임베딩 매칭 |
| `jwt.py` | `get_current_user()` — 모든 대시보드 엔드포인트의 인증 의존성 |
| `db/model.py` | `UserTable`, `FaceEmbeddingTable`, `VectorTable` |

---

## 3. API 엔드포인트 (web_dashboard.html 직접 호출)

### 인증

```
POST /api/v1/auth/login           # 사번+비밀번호 로그인 → access_token 발급
POST /api/v1/auth/login/face      # 얼굴 인식 로그인
POST /api/v1/auth/refresh         # access_token 만료 시 자동 갱신 (401 핸들러)
POST /api/v1/auth/logout          # 로그아웃 (토큰 무효화)
```

### 대시보드 데이터 (탭별 번들)

```
GET /api/v1/dashboard/web/worker   # 작업자 탭 전체 데이터 번들
GET /api/v1/dashboard/web/qa       # 품질관리 탭 전체 데이터 번들
GET /api/v1/dashboard/web/manager  # 관리자 탭 전체 데이터 번들
GET /api/v1/dashboard/web/promo    # 공용 송출 탭 전체 데이터 번들
```

공통 쿼리 파라미터: `tz`, `factory`, `line`, `shift`, `period`, `date_from`, `date_to`

### 보조 엔드포인트

```
GET /api/v1/dashboard/kpis?screen={worker|qa|manager|promo}    # KPI만 분리 조회
GET /api/v1/dashboard/datasets?screen={worker|qa|manager|promo} # 차트 데이터만 분리 조회
GET /api/v1/dashboard/detail?detailId=&targetType=&targetId=   # 상세 모달 데이터
GET /api/v1/dashboard/status                                    # 상태 플레이스홀더
```

---

## 4. 데이터 흐름

```
[web_dashboard.html]
  │  1. sessionStorage.sfp_access_token 확인
  │  2. Bearer 토큰 포함 GET 요청 (60초 자동 갱신)
  ▼
[dashboard_api.js]
  │  endpointMap: { worker, qa, manager, promo } → /api/v1/dashboard/web/{tab}
  │  401 응답 시 → POST /api/v1/auth/refresh → 재시도
  ▼
[Nginx /api/ location]
  │  proxy_pass http://server_api:8000
  │  X-Real-IP, X-Forwarded-For 헤더 전달
  ▼
[dashboard/router.py]
  │  Depends(get_current_user) → jwt.py에서 Bearer 토큰 검증
  │  쿼리 파라미터 파싱 후 service 함수 호출
  ▼
[dashboard/service.py]
  │  get_web_{tab}_dashboard() 호출
  │  현재 시각 → KST(+09:00) 변환
  │  STALE_AFTER_HOURS=6 기준 데이터 신선도 판단
  │  repository에서 받은 스냅샷으로 KPI·데이터셋 조립
  ▼
[dashboard/repository.py]
  │  get_web_dashboard_snapshot() — 기준 날짜·라인 집계
  │  get_dashboard_live_snapshot() — 실시간 불량·알람·생산 집계
  │  engine.connect() + text() raw SQL
  ▼
[PostgreSQL wed_dashboard schema]
  │  production_records  → 시간당 생산량, 달성률, OEE
  │  inspection_results  → 검사 수량, 양품/불량
  │  defect_results      → 불량 유형별 집계 (short/open/spur/...)
  │  equipment_status_history → 설비 상태(run/idle/down/maint)
  │  alarms              → 활성 알람, 심각도
  │  lines / factories   → 필터 메타
  ▼
[dashboard/service.py] ← 집계 결과로 응답 객체 구성
  │  schemas.py의 Pydantic 모델로 직렬화
  ▼
[JSON 응답] → dashboard_app.js → Chart.js 렌더링
```

---

## 5. DB 테이블 구조 (대시보드 관련 핵심)

```
factories ──┬── lines ──┬── equipments
            │           ├── employees
            │           ├── production_records  (recorded_at 인덱스)
            │           ├── inspection_results  (recorded_at 인덱스)
            │           ├── defect_results
            │           ├── equipment_status_history
            │           └── alarms
            └── (factory_id 인덱스 전체 공유)

인증 테이블 (별도):
  users ── face_embeddings ── vectors (얼굴 임베딩)
```

---

## 6. 인증 흐름

```
[web_login.html]
  POST /api/v1/auth/login
  → { access_token, refresh_token, user_profile }
  → sessionStorage.sfp_access_token = access_token

[web_dashboard.html] (매 API 요청)
  Authorization: Bearer {access_token}
  → jwt.py: get_current_user() 검증
  → 만료(401) → POST /api/v1/auth/refresh → 새 토큰 재발급
  → 재시도 실패 → /web_login.html 리다이렉트

JWT 페이로드: employee_no, name, role_code, line_id
역할(role_code): worker | qa | manager | promo
```

---

## 7. 서비스 상수 (service.py)

| 상수 | 값 | 설명 |
|---|---|---|
| `KST` | `UTC+09:00` | 시간 기준 |
| `STALE_AFTER_HOURS` | `6` | 데이터 신선도 임계값 |
| `DAY_PLAN_TOTAL` | `40,000` | 일일 생산 계획 수량 |
| `SCENARIO_START_DATE` | `2026-03-20` | 더미 시나리오 시작일 |
| `SCENARIO_END_DATE` | `2026-03-25` | 더미 시나리오 종료일 |
| `LINE_PLAN_SHARE` | A:26% B:30% C:22% D:22% | 라인별 계획 배분율 |

---

## 8. 다이어그램 파일

- Mermaid 플로우차트: `web_dashboard_be_architecture.mmd`
  (Mermaid Live Editor 또는 VS Code Mermaid 확장에서 렌더링)
