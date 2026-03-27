# wed_dashboard README

`wed_dashboard`는 [`web_dashboard.html`](/home/orugu/Docker/Final_project_rss/nginx/html/web_dashboard.html) 에서 사용하는 대시보드 프론트엔드 모듈 폴더입니다.  
현재는 `worker / qa / manager / promo` 4개 화면이 실제 `/api/v1/dashboard/web/*` live 응답을 기준으로 동작하고, `dashboard_api.js` 안의 mock 번들은 개발/비상 fallback 용도로 유지됩니다.

## 범위 주의

- 이 폴더와 [`web_login.html`](/home/orugu/Docker/Final_project_rss/nginx/html/web_login.html), [`web_dashboard.html`](/home/orugu/Docker/Final_project_rss/nginx/html/web_dashboard.html) 이 현재 운영 web 화면 기준입니다.
- 로그인은 2트랙입니다.
  - [`login.html`](/home/orugu/Docker/Final_project_rss/nginx/html/login.html) + [`login.js`](/home/orugu/Docker/Final_project_rss/nginx/html/js/login.js): 온디바이스(PyQt)용 로그인
  - [`web_login.html`](/home/orugu/Docker/Final_project_rss/nginx/html/web_login.html) + [`web_login.js`](/home/orugu/Docker/Final_project_rss/nginx/html/js/web_login/web_login.js): `web_dashboard`용 로그인
- 즉 현재 web 로그인/대시보드 기준 문서를 볼 때는 `web_login.html` 흐름만 보면 됩니다.

## 현재 상태 요약

- 프론트는 실제 `web` 대시보드 API와 연결되어 있음
- 응답 계약은 백엔드 `response_model`과 문서 기준으로 관리 중
- `worker`는 `meta.line` 기반 단일 라인 화면
- `qa / manager / promo`는 전체 라인 화면이 기본, line filter가 있을 때만 `meta.line` 사용
- 날짜 단일 조회와 기간 비교(`date_from / date_to`) 모두 live 응답 기준으로 동작
- 일부 KPI는 `/api/v1/dashboard/detail`과 연결되어 클릭 상세가 가능

## 화면 구성

- `worker`
  - 시간당 생산량, 현재 라인 생산량, 최근 10분 NG, 가동률
  - 설비 상태, 액션 큐, 공지, NG 추세/유형, 온도 상태, 최근 이벤트
- `qa`
  - 불량률, 재검 대기, 검사 현황, 현재 총 생산량
  - 불량 원인 기여도, 불량률 추세 요약, 재검 우선순위, 품질 이슈 요약, 최근 이벤트
- `manager`
  - OEE, 목표 달성률, 현재 총 생산량, 예상 종료 생산
  - 라인별 OEE, 생산 추세, 불량률 추세, 운영 리스크, 즉시 조치, 미해결 알람, 최근 이벤트
- `promo`
  - 송출용 KPI, 주간 생산량, 라인 현황, 현재 알람, 월 비교, 하단 티커

## 주요 파일

| 파일명 | 역할 |
| --- | --- |
| `dashboard_app.js` | 탭 전환, 레이아웃 HTML 생성, 상세 모달 오픈, 이벤트 연결 담당 |
| `dashboard_api.js` | 실제 API 호출 계층. 실패 시 mock/fallback 처리 포함 |
| `dashboard_charts.js` | 각 탭의 Chart.js 렌더링 담당 |
| `dashboard_detail_views.js` | 상세 모달용 보조 렌더 유틸 |
| `dashboard_state.js` | 공통 상태 토큰/상수 |
| `dashboard_thresholds.js` | KPI 임계값 기준 |

## 렌더 흐름

1. `web_dashboard.html`이 기본 DOM/CSS/JS 로드
2. `dashboard_app.js`가 현재 탭과 필터 상태를 기준으로 `renderCurrentTab()` 실행
3. `dashboard_api.js`의 `fetchBundle(tab, params)`가 `/api/v1/dashboard/web/{tab}` 호출
4. `dashboard_app.js`의 탭별 layout 함수가 HTML 생성
5. `dashboard_charts.js`가 차트를 렌더
6. 클릭 가능한 KPI/행은 `/api/v1/dashboard/detail`로 상세 모달 연결

## 데이터 계약 기준

현재 기준 계약의 소스는 아래 두 곳입니다.

- 백엔드 코드
  - [`server_api/src/modules/dashboard/schemas.py`](/home/orugu/Docker/Final_project_rss/server_api/src/modules/dashboard/schemas.py)
  - [`server_api/src/modules/dashboard/service.py`](/home/orugu/Docker/Final_project_rss/server_api/src/modules/dashboard/service.py)
- 문서
  - [`API_RESPONSE_SCHEMA.md`](/home/orugu/Docker/Final_project_rss/nginx/html/js/wed_dashboard/dashboard_docs/API_RESPONSE_SCHEMA.md)

즉 더 이상 `dashboard_api.js` mock 구조만을 기준으로 보는 상태는 아니고,  
**live 응답 계약이 기준이고 mock은 그 계약을 따라가는 보조 수단**입니다.

## 현재 중요한 규칙

- `worker.meta.line`은 항상 실제 담당 라인
- `worker actionQueue`는 내 라인 조치 항목만
- `worker globalNotices`는 공용/타 라인 알림만
- `status`는 `run / idle / down / maint` 기준
- 날짜 필터는 `meta.filters.date_from`, `meta.filters.date_to`에 ISO 문자열로 반영
- 관리자 `라인별 OEE`는 0~100 범위로 보정된 값 사용
- 클릭 가능한 KPI만 `detailId / targetType / targetId / clickable` 메타를 포함

## 현재 clickable KPI

- `worker_recent_10m_ng`
- `qa_defect_rate`
- `qa_recheck`
- `mgr_oee`
  - 활성 알람이 있을 때만 clickable

## 유지보수 기준

- 레이아웃/반응형/모달 UX 수정
  - `dashboard_app.js`, `dashboard_style.css`
- API 응답 구조/날짜 필터/상세 연결 수정
  - `dashboard_api.js`, `service.py`, `schemas.py`, `router.py`
- 차트 수정
  - `dashboard_charts.js`
- DB 조회/집계 로직 수정
  - `repository.py`, `service.py`

## 다음 우선순위

1. 날짜 변경 후 브라우저 UX 미세 점검
2. KPI 상세 연결 범위 확장 여부 결정
3. 관리자 카드 간 문맥(`OEE / 리스크 / 알람`) 일관성 보강
4. mock/live 차이를 계속 줄여 화면 검토 혼선 최소화

## 관련 문서

- [`TEAM_ONBOARDING_QUICKSTART.md`](/home/orugu/Docker/Final_project_rss/nginx/html/js/wed_dashboard/dashboard_docs/TEAM_ONBOARDING_QUICKSTART.md)
- [`README_INDEX.md`](/home/orugu/Docker/Final_project_rss/nginx/html/js/wed_dashboard/dashboard_docs/README_INDEX.md)
- [`API_RESPONSE_SCHEMA.md`](/home/orugu/Docker/Final_project_rss/nginx/html/js/wed_dashboard/dashboard_docs/API_RESPONSE_SCHEMA.md)
- [`SERVICE_DB_MAPPING.md`](/home/orugu/Docker/Final_project_rss/nginx/html/js/wed_dashboard/dashboard_docs/SERVICE_DB_MAPPING.md)
- [`DATA_ARCHITECTURE.md`](/home/orugu/Docker/Final_project_rss/nginx/html/js/wed_dashboard/dashboard_docs/DATA_ARCHITECTURE.md)
- [`DB_SCHEMA_REVIEW_WEB_LOGIN_WEB_DASHBOARD_2026-03-20.md`](/home/orugu/Docker/Final_project_rss/nginx/html/js/wed_dashboard/dashboard_docs/DB_SCHEMA_REVIEW_WEB_LOGIN_WEB_DASHBOARD_2026-03-20.md)

## 문서 운영 원칙

- 운영 기준으로 바로 보는 문서는 적게 유지
  - `README.md`
  - `API_RESPONSE_SCHEMA.md`
  - `SERVICE_DB_MAPPING.md`
  - `BACKEND_CONNECTION_CHECKLIST.md`
  - `DB_SCHEMA_REVIEW_WEB_LOGIN_WEB_DASHBOARD_2026-03-20.md`
- 나머지 문서는 삭제보다 `참고/아카이브` 성격으로 남김
- 즉, 지금은 문서를 더 늘리기보다 "무엇이 현재 기준 문서인지"를 분명히 하는 것이 더 중요
