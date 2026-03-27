# wed_dashboard 문서 인덱스

`wed_dashboard` 관련 문서는 현재 live API 기준으로 아래처럼 정리합니다.

## 최우선 문서

- [`TEAM_ONBOARDING_QUICKSTART.md`](./TEAM_ONBOARDING_QUICKSTART.md)
  - 처음 보는 팀원이 가장 먼저 봐야 하는 1페이지 온보딩 문서
- [`README.md`](./README.md)
  - 현재 구조, live 연결 상태, clickable KPI, 유지보수 기준
- [`API_RESPONSE_SCHEMA.md`](./API_RESPONSE_SCHEMA.md)
  - 현재 응답 계약과 탭별 번들 구조
- [`DB_SCHEMA_REVIEW_WEB_LOGIN_WEB_DASHBOARD_2026-03-20.md`](./DB_SCHEMA_REVIEW_WEB_LOGIN_WEB_DASHBOARD_2026-03-20.md)
  - DB/스키마/응답 계약 점검 요약과 최근 수정 내역

## 로그인 경계

- [`login.html`](/home/orugu/Docker/Final_project_rss/nginx/html/login.html) + [`/home/orugu/Docker/Final_project_rss/nginx/html/js/login.js`](/home/orugu/Docker/Final_project_rss/nginx/html/js/login.js)
  - 온디바이스(PyQt)용 로그인
- [`web_login.html`](/home/orugu/Docker/Final_project_rss/nginx/html/web_login.html) + [`/home/orugu/Docker/Final_project_rss/nginx/html/js/web_login/web_login.js`](/home/orugu/Docker/Final_project_rss/nginx/html/js/web_login/web_login.js)
  - `web_dashboard`용 로그인
- 현재 이 문서 세트는 `web_login.html` 기준으로 읽으면 됩니다.

## 유지할 운영 기준 문서

아래 문서는 현재 팀이 실제로 보고 유지보수해야 하는 문서입니다.

- [`README.md`](./README.md)
- [`API_RESPONSE_SCHEMA.md`](./API_RESPONSE_SCHEMA.md)
- [`SERVICE_DB_MAPPING.md`](./SERVICE_DB_MAPPING.md)
- [`BACKEND_CONNECTION_CHECKLIST.md`](./BACKEND_CONNECTION_CHECKLIST.md)
- [`DB_SCHEMA_REVIEW_WEB_LOGIN_WEB_DASHBOARD_2026-03-20.md`](./DB_SCHEMA_REVIEW_WEB_LOGIN_WEB_DASHBOARD_2026-03-20.md)

## 참고/아카이브 성격 문서

아래 문서는 지금 당장 운영 기준으로 삼기보다는, 배경 이해나 설계 참고용으로 남겨두는 편이 좋습니다.

- [`DATA_ARCHITECTURE.md`](./DATA_ARCHITECTURE.md)
  - DB / 파생 데이터 / 화면 데이터의 전체 구분
- [`SERVICE_DB_MAPPING.md`](./SERVICE_DB_MAPPING.md)
  - `service.py` 기준 화면별 DB 조회 대상과 구현 우선순위
- [`DERIVED_METRICS_SPEC.md`](./DERIVED_METRICS_SPEC.md)
  - KPI/리스크/집계값 같은 파생 지표 정의
- [`PERIOD_COMPARE_MODE_DESIGN.md`](./PERIOD_COMPARE_MODE_DESIGN.md)
  - 날짜 기간 비교 모드 설계

## DB/응답 보조 문서

- [`DB_SOURCE_DATA_SPEC.md`](./DB_SOURCE_DATA_SPEC.md)
  - DB에 저장해야 할 원천 데이터 스펙
- [`DB_TABLE_DDL_SPEC.md`](./DB_TABLE_DDL_SPEC.md)
  - PostgreSQL 기준 `CREATE TABLE` 초안
- [`API_ERROR_RESPONSE_SPEC.md`](./API_ERROR_RESPONSE_SPEC.md)
  - 에러 응답 형식과 메시지 규칙
- [`BACKEND_CONNECTION_CHECKLIST.md`](./BACKEND_CONNECTION_CHECKLIST.md)
  - 현재 live 연결/점검 체크리스트

권장 해석:

- `DATA_ARCHITECTURE.md`, `DB_SOURCE_DATA_SPEC.md`, `DB_TABLE_DDL_SPEC.md`, `DERIVED_METRICS_SPEC.md`
  - 유지하되, "현재 운영 기준"이 아니라 "참고/배경 문서"로 취급
- `PERIOD_COMPARE_MODE_DESIGN.md`
  - 기능 설계 맥락 확인용 참고 문서

## 무엇부터 보면 좋은가

- 프론트 수정
  1. `TEAM_ONBOARDING_QUICKSTART.md`
  2. `README.md`
  3. `API_RESPONSE_SCHEMA.md`

- 백엔드 수정
  1. `TEAM_ONBOARDING_QUICKSTART.md`
  2. `SERVICE_DB_MAPPING.md`
  3. `API_RESPONSE_SCHEMA.md`
  4. `DB_SCHEMA_REVIEW_WEB_LOGIN_WEB_DASHBOARD_2026-03-20.md`

- DB 설계
  1. `DB_SOURCE_DATA_SPEC.md`
  2. `DB_TABLE_DDL_SPEC.md`
  3. `DERIVED_METRICS_SPEC.md`

- 연동/운영 점검
  1. `README.md`
  2. `API_RESPONSE_SCHEMA.md`
  3. `BACKEND_CONNECTION_CHECKLIST.md`
  4. `DB_SCHEMA_REVIEW_WEB_LOGIN_WEB_DASHBOARD_2026-03-20.md`

## 한 줄 요약

- 현재 구조와 상태: `README.md`
- 처음 보는 팀원 안내: `TEAM_ONBOARDING_QUICKSTART.md`
- 응답 계약: `API_RESPONSE_SCHEMA.md`
- DB/스키마/수정 이력: `DB_SCHEMA_REVIEW_WEB_LOGIN_WEB_DASHBOARD_2026-03-20.md`
- 서비스-DB 조회 흐름: `SERVICE_DB_MAPPING.md`
