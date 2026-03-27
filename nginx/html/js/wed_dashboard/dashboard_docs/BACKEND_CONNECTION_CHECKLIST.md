# BACKEND_CONNECTION_CHECKLIST

이 문서는 현재 `web_dashboard` live 연결 상태를 점검할 때 사용하는 체크리스트입니다.

## 1. 현재 기준

- 프론트는 `/api/v1/dashboard/web/...` 를 우선 호출합니다.
- 실패 시 `dashboard_api.js` 내부 mock fallback 으로 화면이 유지될 수 있습니다.
- 백엔드에는 `dashboard` 모듈 안에 `web` 전용 라우트와 `response_model`이 연결되어 있습니다.

## 2. 연결 대상 경로

- `GET /api/v1/dashboard/web/worker`
- `GET /api/v1/dashboard/web/qa`
- `GET /api/v1/dashboard/web/manager`
- `GET /api/v1/dashboard/web/promo`

## 3. 사전 확인

- [`server_api/src/modules/dashboard/router.py`](/home/orugu/Docker/Final_project_rss/server_api/src/modules/dashboard/router.py)
  - `web` 전용 라우트와 query parameter 정의 확인
- [`server_api/src/modules/dashboard/service.py`](/home/orugu/Docker/Final_project_rss/server_api/src/modules/dashboard/service.py)
  - `get_web_worker_dashboard()`
  - `get_web_qa_dashboard()`
  - `get_web_manager_dashboard()`
  - `get_web_promo_dashboard()`
  함수 확인
- [`server_api/src/modules/dashboard/schemas.py`](/home/orugu/Docker/Final_project_rss/server_api/src/modules/dashboard/schemas.py)
  - web 응답 모델 확인
- [`nginx/html/js/wed_dashboard/dashboard_api.js`](/home/orugu/Docker/Final_project_rss/nginx/html/js/wed_dashboard/dashboard_api.js)
  - endpointMap 이 `/api/v1/dashboard/web/...` 를 향하는지 확인

## 4. 기본 실행 체크

1. 백엔드 서버 실행
2. 로그인된 상태로 [`web_dashboard.html`](/home/orugu/Docker/Final_project_rss/nginx/html/web_dashboard.html) 접속
3. 브라우저 개발자도구 `Network` 탭 열기
4. 아래 순서로 탭 확인
   - `worker`
   - `qa`
   - `manager`
   - `promo`
5. 날짜 단일 조회와 기간 비교도 함께 확인

## 5. 정상 기준

- 상태코드가 `200 OK`
- Response JSON 안에 `meta` 존재
- Response JSON 안에 `kpis` 존재
- 탭 전환 시 화면이 깨지지 않음
- 날짜 변경(`date_from / date_to`) 시 `500` 없이 응답함
- 기간 비교 시 `meta.viewMode = period_compare` 와 `dailyCompare`가 맞게 내려옴
- 클릭 가능한 KPI는 `detailId / targetType / targetId / clickable` 메타를 포함함

## 6. 실패 시 확인표

### `200 OK`

- 정상
- response 구조만 추가 확인

### `401 Unauthorized`

- 로그인 토큰/쿠키 미전달 가능성
- `authorizedFetch()` / refresh token 흐름 확인

### `403 Forbidden`

- 인증은 되었지만 권한 제한 가능성
- 인증/권한 의존성 확인

### `404 Not Found`

- 라우트 경로 오타 가능성
- 프론트 endpointMap 과 백엔드 router 경로 일치 여부 확인

### `422 Unprocessable Entity`

- query parameter 타입 또는 validation 문제
- `date_from / date_to / line` 파라미터 정의 확인

### `500 Internal Server Error`

- `service.py` 내부 응답 생성 또는 period compare 로직 확인
- `response_model` validation 에러 여부 확인
- 서버 로그 traceback 확인

## 7. mock fallback 확인법

프론트는 API 호출 실패 시 mock 데이터로 전환될 수 있습니다.

이 경우 브라우저 `Console` 에 아래 형식의 경고가 보입니다.

```text
[dashboard_api] worker API fallback to mock bundle:
```

의미:

- 화면은 보이지만 실제 백엔드 응답은 아직 안 붙은 상태
- `Network` 와 `Console` 을 같이 봐야 함

## 8. 현재 우선 점검 포인트

- [ ] `meta.line` 정책이 탭별로 맞는지 확인
- [ ] `filters.date_from/date_to`가 ISO 문자열로 내려오는지 확인
- [ ] 관리자 `라인별 OEE`가 100%를 넘지 않는지 확인
- [ ] `worker / qa / manager` KPI 상세 클릭이 실제 detail API와 연결되는지 확인
- [ ] promo 기간 비교가 500 없이 응답하는지 확인

## 9. 확인 순서 추천

1. `worker`
2. `qa`
3. `manager`
4. `promo`

이유:

- `worker` 는 날짜/라인 기준 확인이 가장 빠름
- `qa` 는 KPI 상세와 재검 흐름 확인에 적합
- `manager` 는 라인별 OEE/알람 문맥 확인에 적합
- `promo` 는 기간 비교와 송출용 집계 확인이 마지막 점검에 적합
