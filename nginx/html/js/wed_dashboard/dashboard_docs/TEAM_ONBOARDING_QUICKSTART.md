# web_dashboard 팀원용 1페이지 온보딩

이 문서는 `web_dashboard`를 처음 보거나, 전체 구조를 아직 잘 모르는 팀원이 **최소한으로 먼저 이해해야 하는 것만** 정리한 빠른 안내서입니다.

## 1. 먼저 기억할 것

- 이 화면은 지금 **live API 기준**으로 동작합니다
- 프론트는 `/api/v1/dashboard/web/*` 를 호출합니다
- 탭은 4개입니다
  - `worker`
  - `qa`
  - `manager`
  - `promo`
- mock 데이터는 개발/비상 fallback 용도입니다

즉, 지금은 "더미 화면"을 먼저 보는 게 아니라 **실제 응답 계약**을 먼저 보는 게 맞습니다.

## 2. 제일 먼저 볼 문서

순서는 이것만 보면 됩니다.

1. [`README.md`](/home/orugu/Docker/Final_project_rss/nginx/html/js/wed_dashboard/dashboard_docs/README.md)
2. [`API_RESPONSE_SCHEMA.md`](/home/orugu/Docker/Final_project_rss/nginx/html/js/wed_dashboard/dashboard_docs/API_RESPONSE_SCHEMA.md)
3. [`SERVICE_DB_MAPPING.md`](/home/orugu/Docker/Final_project_rss/nginx/html/js/wed_dashboard/dashboard_docs/SERVICE_DB_MAPPING.md)

이 3개만 먼저 보면
- 화면 구조
- 응답 구조
- DB 집계 흐름
을 한 번에 따라올 수 있습니다.

## 3. 파일 역할

- [`dashboard_app.js`](/home/orugu/Docker/Final_project_rss/nginx/html/js/wed_dashboard/dashboard_app.js)
  - 화면 HTML 조립, 탭 전환, 모달, 클릭 이벤트
- [`dashboard_api.js`](/home/orugu/Docker/Final_project_rss/nginx/html/js/wed_dashboard/dashboard_api.js)
  - `/api/v1/dashboard/web/*` 호출
- [`dashboard_style.css`](/home/orugu/Docker/Final_project_rss/nginx/html/css/wed_dashboard/dashboard_style.css)
  - 반응형, 카드, 모달 스타일
- [`service.py`](/home/orugu/Docker/Final_project_rss/server_api/src/modules/dashboard/service.py)
  - web 응답 번들 생성
- [`repository.py`](/home/orugu/Docker/Final_project_rss/server_api/src/modules/dashboard/repository.py)
  - DB 조회/집계
- [`schemas.py`](/home/orugu/Docker/Final_project_rss/server_api/src/modules/dashboard/schemas.py)
  - 응답 모델

## 4. 지금 기준으로 중요한 규칙

- `worker.meta.line`은 항상 실제 담당 라인
- `qa / manager / promo`는 전체 라인 화면이 기본
- `status`는 `run / idle / down / maint`
- 날짜 필터는 `date_from`, `date_to`를 ISO 문자열로 처리
- 관리자 `라인별 OEE`는 0~100 범위
- 일부 KPI는 상세 모달 클릭 가능

현재 clickable KPI:

- `worker_recent_10m_ng`
- `qa_defect_rate`
- `qa_recheck`
- `mgr_oee`

## 5. 문제가 생기면 어디부터 보나

- 화면이 안 뜬다
  - `dashboard_app.js`
  - 브라우저 콘솔
- API는 오는데 값이 이상하다
  - `service.py`
  - `repository.py`
- 날짜 바꾸면 깨진다
  - `router.py`
  - `service.py`
  - `schemas.py`
- 상세 모달이 안 열린다
  - `dashboard_app.js`
  - `dashboard_api.js`
  - `/api/v1/dashboard/detail`

## 6. 지금 팀에서 운영 기준으로 보는 문서

- [`README.md`](/home/orugu/Docker/Final_project_rss/nginx/html/js/wed_dashboard/dashboard_docs/README.md)
- [`API_RESPONSE_SCHEMA.md`](/home/orugu/Docker/Final_project_rss/nginx/html/js/wed_dashboard/dashboard_docs/API_RESPONSE_SCHEMA.md)
- [`SERVICE_DB_MAPPING.md`](/home/orugu/Docker/Final_project_rss/nginx/html/js/wed_dashboard/dashboard_docs/SERVICE_DB_MAPPING.md)
- [`BACKEND_CONNECTION_CHECKLIST.md`](/home/orugu/Docker/Final_project_rss/nginx/html/js/wed_dashboard/dashboard_docs/BACKEND_CONNECTION_CHECKLIST.md)
- [`DB_SCHEMA_REVIEW_WEB_LOGIN_WEB_DASHBOARD_2026-03-20.md`](/home/orugu/Docker/Final_project_rss/nginx/html/js/wed_dashboard/dashboard_docs/DB_SCHEMA_REVIEW_WEB_LOGIN_WEB_DASHBOARD_2026-03-20.md)

나머지 문서는 참고/배경 문서로 보면 됩니다.

## 7. 한 줄 요약

처음 보는 사람은 **README -> API_RESPONSE_SCHEMA -> SERVICE_DB_MAPPING** 순서만 따라가면 됩니다.  
이 3개를 모르고 DB나 CSS부터 보면 오히려 더 헷갈립니다.
