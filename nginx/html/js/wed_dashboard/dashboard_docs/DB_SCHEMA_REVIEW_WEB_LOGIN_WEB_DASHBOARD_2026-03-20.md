# DB/스키마 점검 요약 (web_login + web_dashboard)

작성일: 2026-03-20  
대상: `web_login`, `web_dashboard`

참고:

- 로그인은 2트랙으로 분리되어 있음
  - `login.html` + `js/login.js`: 온디바이스(PyQt)용 로그인
  - `web_login.html` + `js/web_login/web_login.js`: `web_dashboard`용 로그인
- 본 문서는 `web_login / web_dashboard` 기준 점검을 우선으로 함

## 0. 작업 우선순위

권장 확인 순서는 아래와 같습니다.

1. 로그인 경계 확인
   - 로그인은 문서(MD) 기준으로 먼저 확인
   - `login.html + js/login.js` 는 온디바이스용
   - `web_login.html + js/web_login/web_login.js` 는 `web_dashboard`용
2. `web_dashboard` 응답 계약 확인
   - 기준 문서: `API_RESPONSE_SCHEMA.md`
   - `worker / qa / manager / promo`, `meta.line`, 날짜 필터, KPI 상세 연결을 먼저 확인
3. `web_dashboard` 서비스-DB 매핑 확인
   - 기준 문서: `SERVICE_DB_MAPPING.md`
   - 실제 조회가 `wed_dashboard.*` 중심인지 확인
4. `web_dashboard` 수정 이력 / 판단 근거 확인
   - 기준 문서: 본 문서
   - ORM, 초기화 경로, 중복 테이블 판단 흐름을 확인
5. 마지막에만 `dashboard.js` / 온디바이스 참고
   - 주 작업 대상이 아니라 경계 확인용 참고로만 사용

한 줄 기준:

- 로그인은 문서 기준으로 경계를 먼저 본다
- `dashboard`보다 `web_dashboard`를 먼저 본다
- 운영 판단은 `web_dashboard` 문서 세트를 우선 사용한다

## 1. 점검 목적

현재 코드 기준으로 DB/스키마에서

- 누락된 부분
- 불필요하거나 충돌 위험이 있는 부분
- 바로 조치가 필요한 부분

을 실무 관점으로 정리합니다.

---

## 2. 점검 범위

백엔드 코드:

- `server_api/src/modules/auth/*`
- `server_api/src/modules/dashboard/*`
- `server_api/src/modules/db/*`
- `server_api/src/init_db.py`

DB 객체:

- `public.user_table`
- `public.vector_table`
- `public.face_embedding_table`
- `wed_dashboard.*` (dashboard 집계/조회 테이블)
- `public.lines`, `public.equipment` (public 계열 기존 테이블)

---

## 3. 결론 요약

### 3.1 핵심 이슈 (우선순위 높음)

1. `UserTable` ORM의 `line_id` 매핑은 현재 반영 완료, 관련 사용 경로 점검 필요
2. `integrated_models.py`에 혼합 정의(불필요/충돌 위험)
3. `integrated_models.py`와 `dashboard.db.model`의 역할 경계가 문서상 더 명확해야 함

### 3.2 운영 영향

- 작업자 라인 배정/조회 흐름이 불안정하거나 실패 가능
- 테이블 생성 시 의도치 않은 public 테이블/컬럼 생성 위험
- 유지보수 시 스키마 기준이 모호해질 수 있음

---

## 4. 상세 점검 결과

## 4.1 누락/불일치

### A) `public.user_table`에는 `line_id` 컬럼이 존재

실DB 확인 결과:

- `public.user_table` 컬럼: `employee_no, password_hash, id_active, id_locked, login_fail_count, token_version, join_date, last_login, role, name, line_id`

### B) `UserTable` ORM `line_id` 매핑 반영

파일:

- `server_api/src/modules/db/users/db/model.py`

현재 `UserTable` 클래스에 `line_id` 필드가 반영되어 있고,
`public.user_table.line_id` 기존 컬럼과 ORM 기준이 맞춰진 상태임.

### C) 서비스 코드는 `line_id`를 사용 중

파일:

- `server_api/src/modules/auth/service.py`

`create_user()` / `update_line_id()`에서 `user_row.line_id` 사용.

즉, **DB는 있는데 ORM이 못 받는 구조**라서 불일치.

---

## 4.2 충돌/위험 요소

### A) 통합 모델 파일에 정의 혼재

파일:

- `server_api/src/modules/db/integrated_models.py`

확인된 위험 포인트:

- `equipment`(단수) 테이블명 사용 (dashboard 쿼리는 주로 `wed_dashboard.equipments` 사용)
- `VectorTable` 클래스 내부에 `id/title/description` 필드가 섞여 있음

현재는 `server_api/src/modules/db/users/db/model.py` 에 `line_id` 매핑이 반영되었고,
`auth/service.py` 의 사용자 생성/라인 배정 로직과 ORM 기준이 맞춰진 상태임.

### B) `init_db.py`에서 통합 모델 전체 import

파일:

- `server_api/src/init_db.py`

현재는 `integrated_models.py`가 아니라 `src.modules.dashboard.db.model`을 import 하도록 정리됨.
즉 web_dashboard 기준 테이블 등록 경로는 `main.py`와 `init_db.py` 모두 `dashboard.db.model` 쪽으로 맞춰진 상태임.

다만 문서/구조 차원에서는 아래 역할 구분을 유지하는 것이 좋음.

- `src.modules.dashboard.db.model`: web_dashboard 기준 테이블 등록 경로
- `src.modules.db.integrated_models`: 별도 참조/통합 모델 경로

---

## 4.3 web_dashboard 직접 사용 기준 밖의 테이블

현재 DB에는 아래 public 테이블이 존재:

- `public.lines`
- `public.equipment`

반면 web dashboard 핵심 조회는 `wed_dashboard.lines`, `wed_dashboard.equipments` 기준.

따라서 `public.lines/equipment`는 web_dashboard 직접 조회 테이블은 아니며,
프로젝트 전체 기준에서 유지 여부를 따로 판단해야 하는 대상입니다.

- `public.equipment`는 `server_api/src/modules/report/service.py` 에서 참조 중
- `public.lines`, `public.equipment` 둘 다 `server_api/src/modules/db/integrated_models.py` 경로와 연결됨
- 다만 `server_api/src/init_db.py` 는 현재 `integrated_models.py` 가 아니라 `src.modules.dashboard.db.model` 기준으로 정리됨

즉 현재 시점에선

- `web_dashboard` 기준 직접 사용은 아님
- 하지만 프로젝트 전체 기준 즉시 제거 대상으로 단정할 단계도 아님

으로 보는 것이 정확함.

---

## 5. 현재 구조에서 필요한 테이블 (정상 사용)

### 5.1 web_login / auth

필수:

- `public.user_table`
- `public.vector_table`
- `public.face_embedding_table`

### 5.2 web_dashboard

필수:

- `wed_dashboard.factories`
- `wed_dashboard.lines`
- `wed_dashboard.equipments`
- `wed_dashboard.employees`
- `wed_dashboard.production_records`
- `wed_dashboard.equipment_status_history`
- `wed_dashboard.inspection_results`
- `wed_dashboard.defect_results`
- `wed_dashboard.alarms`
- `wed_dashboard.alarm_ack_history`
- `wed_dashboard.recheck_queue`
- `wed_dashboard.event_logs`
- `wed_dashboard.line_environment`

---

## 6. 권장 조치 순서

1. `UserTable.line_id` 사용 경로 재점검
   - worker 라인 배정/조회 흐름에서 ORM 기준이 정상 동작하는지 확인
2. `integrated_models.py`의 비일관 정의 정리
   - `equipment/equipments` 네이밍 정합성 통일
   - `VectorTable` 혼입 필드 제거
3. `dashboard.db.model` / `integrated_models.py` 역할 문서화 유지
   - web_dashboard 기준: `dashboard.db.model`
   - 별도 참조 모델: `integrated_models.py`
4. `public.lines/equipment` 유지 여부 확정
   - 유지 시 목적 문서화
   - 미사용 시 단계적 정리 계획 수립

---

## 7. 바로 실행 가능한 점검 SQL

```sql
-- user_table 컬럼 확인
SELECT column_name
FROM information_schema.columns
WHERE table_schema='public' AND table_name='user_table'
ORDER BY ordinal_position;

-- wed_dashboard 핵심 테이블 존재 확인
SELECT table_name
FROM information_schema.tables
WHERE table_schema='wed_dashboard'
ORDER BY table_name;

-- 정리 대상 후보 확인
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema='public'
  AND table_name IN ('lines', 'equipment', 'user_table', 'vector_table', 'face_embedding_table')
ORDER BY table_name;
```

---

## 8. 한 줄 결론

현재는 **DB 컬럼은 있는데 ORM 매핑이 누락된 부분(`user_table.line_id`)이 핵심 리스크**이고,  
추가로 통합 모델 경로(`integrated_models.py`)와 web_dashboard 기준 모델 경로(`dashboard.db.model`)의 역할을 분리해서 유지하면 운영 안정성이 크게 올라갑니다.

---

## 9. 추가 점검: web_dashboard API 연결 / 응답 계약 (2026-03-22 반영)

### 9.1 현재 연결 상태

현재 `wed_dashboard` 프론트는 mock 기준 화면이 아니라, 실제 `/api/v1/dashboard/web/*` 응답을 사용 중입니다.

연결 엔드포인트:

- `/api/v1/dashboard/web/worker`
- `/api/v1/dashboard/web/qa`
- `/api/v1/dashboard/web/manager`
- `/api/v1/dashboard/web/promo`

확인 결과:

- `worker`: `meta.line = LINE-C`
- `qa`: 기본 `meta.line = null`
- `manager`: 기본 `meta.line = null`
- `promo`: 기본 `meta.line = null`
- `qa / manager / promo`는 `?line=LINE-A` 요청 시 `meta.line = LINE-A`로 정상 반영

즉 현재는 **프론트-백엔드 연결 자체는 정상**이며,
라인 정책도 아래 기준으로 맞춰진 상태입니다.

- `worker`: 실제 담당 라인 기준
- `qa / manager / promo`: 전체 라인 화면이 기본, line filter가 있을 때만 `meta.line` 사용

### 9.2 이번에 정리된 계약

정리 완료:

- `worker` 응답에 `meta.line` 명시
- `worker actionQueue` / `globalNotices` 역할 분리
- `worker status`를 `run / idle / down / maint` 기준으로 통일
- `qa / manager / promo` 이벤트 제목도 `meta.line` 정책에 맞게 프론트에서 동작
- `/web/*` 응답용 Pydantic response model 추가 및 router 연결

적용 파일:

- `server_api/src/modules/dashboard/schemas.py`
- `server_api/src/modules/dashboard/router.py`
- `server_api/src/modules/dashboard/service.py`
- `nginx/html/js/wed_dashboard/dashboard_app.js`
- `nginx/html/js/wed_dashboard/dashboard_api.js`

### 9.3 DB 수정이 필요한가?

현재 판단:

- **추가 DB 컬럼/테이블 생성은 당장 필요하지 않음**
- 핵심은 DB보다 **web 응답 계약 정리**였고, 그 부분은 상당 부분 완료

굳이 DB에 더 추가하지 않는 것이 좋은 항목:

- `WAIT` 같은 별도 상태 enum 추가
- hover 전용 설명 컬럼 추가
- 라인 식별용 중복 컬럼 추가

이유:

- 현재 라인 기준값은 `meta.line`으로 해결 가능
- hover/보조 문구는 프론트 fallback으로 처리 가능
- 상태 체계는 `idle` 기준으로 정리된 상태

### 9.4 아직 남아 있는 리스크

1. `/web/*` 응답은 이제 response model이 생겼지만, 필드 내부는 `dict[str, Any]` 중심이라 아직 느슨함
2. `dashboard_api.js` mock 데이터와 live 데이터 차이가 커서, mock 기준 화면 논의 시 혼선 가능
3. worker `detail` 같은 선택 필드는 live에서 항상 보장되지 않으므로 optional 전제로 유지하는 것이 안전

### 9.5 지금 시점 권장 우선순위

1. 현재 구조 유지
2. mock/live 차이 축소 여부 결정
3. `/web/*` 내부 item schema를 더 세분화할지 검토
4. DB 추가보다 API 계약/문서 동기화 유지에 집중

### 9.6 한 줄 결론

`web_dashboard`는 현재 **DB를 더 늘리는 단계가 아니라, 정리된 API 계약을 유지하고 문서/프론트/백엔드가 같은 기준을 보게 만드는 단계**입니다.

---

## 10. 추가 반영 사항: 날짜 필터 / KPI 상세 / 관리자 OEE 보정 (2026-03-23 반영)

### 10.1 날짜 필터 500 원인과 수정

증상:

- 다른 날짜 또는 기간 비교 선택 시 일부 탭에서 `데이터를 가지고 오지 못함`
- 실제 원인은 프론트가 아니라 `/api/v1/dashboard/web/*` 응답의 `response_model` 검증 실패

원인:

- `meta.filters.date_from`, `meta.filters.date_to`가 `datetime.date` 객체로 내려감
- web response schema는 위 두 필드를 `string`으로 기대
- response model 연결 이후 FastAPI가 `ResponseValidationError`를 발생시킴

조치:

- `server_api/src/modules/dashboard/service.py`
- `_web_dashboard_meta()`에서 `filters.date_from`, `filters.date_to`를 `YYYY-MM-DD` 문자열로 변환

결과:

- 단일 날짜 조회 정상화
- `worker / qa / manager / promo` 기간 비교 응답 정상화

### 10.2 promo 기간 비교 500 원인과 수정

증상:

- `promo` 탭만 기간 비교(`date_from != date_to`) 시 `500 Internal Server Error`

원인:

- `_apply_period_compare_promo()` 내부에서 `daily_target`으로 계산해 놓고,
  아래 `promoWeekProduction` 생성 시 존재하지 않는 `daily_plan` 변수를 참조

조치:

- `server_api/src/modules/dashboard/service.py`
- `promoWeekProduction[*].target` 값을 `daily_target`으로 정정

결과:

- `promo` 기간 비교도 다른 탭과 동일하게 정상 응답

### 10.3 관리자 라인별 OEE 100% 초과 문제

증상:

- 관리자 화면 `라인별 OEE`에서 `184%`, `213%`, `346%` 같은 비정상 수치 노출

원인:

- 라인별 OEE 계산 시 `performance_pct = produced / plan_to_now * 100`
  값을 그대로 사용
- 계획 대비 생산이 많이 앞서면 `performance_pct`가 100을 초과
- line-level OEE 계산에는 상한 clamp가 없어 최종 OEE도 100을 넘김

조치:

- `server_api/src/modules/dashboard/repository.py`
- `availability_pct`, `quality_pct`, `performance_pct`, `oee`를 모두 `0~100` 범위로 clamp

결과:

- live 검증 기준:
  - `LINE-A`: `96.0`
  - `LINE-B`: `86.02`
  - `LINE-C`: `94.07`
  - `LINE-D`: `96.41`

### 10.4 KPI 상세 연결

정리 완료:

- 상세 API(`/api/v1/dashboard/detail`)와 KPI 연결 시작
- 현재 clickable KPI:
  - `worker_recent_10m_ng`
  - `qa_defect_rate`
  - `qa_recheck`
  - `mgr_oee` (활성 알람이 있을 때만)

추가 반영:

- KPI 카드 hover/focus 강조
- 클릭 가능한 KPI에 `상세` 힌트 칩 표시
- 상세 모달에서 `심각도 / ACK / 상태 / 우선순위` 값 강조 배지 적용

적용 파일:

- `server_api/src/modules/dashboard/service.py`
- `server_api/src/modules/dashboard/repository.py`
- `nginx/html/js/wed_dashboard/dashboard_app.js`
- `nginx/html/js/wed_dashboard/dashboard_api.js`
- `nginx/html/css/wed_dashboard/dashboard_style.css`

### 10.5 현재 기준 다음 우선순위

1. 날짜 변경 후 브라우저 UX 미세 점검
2. KPI 상세 범위를 어디까지 확장할지 기준 정리
3. 관리자 카드 문맥(`OEE / 리스크 / 알람`) 간 설명 일관성 점검

### 10.6 한 줄 결론

현재 `web_dashboard`는 **연결 장애를 잡는 단계에서 벗어나, 날짜/상세/관리자 지표를 안정화한 상태**이며,
다음 단계는 기능 추가보다 **UX 완성도와 해석 일관성 정리**에 가깝습니다.

---

## 11. 추가 반영 사항: 로그인 경계 정리 / UX 문구 정리 (2026-03-23 추가 반영)

### 11.1 로그인 경계 정리

정리 기준:

- 로그인은 2트랙으로 유지
  - `login.html` + `js/login.js`: 온디바이스(PyQt)용 로그인
  - `web_login.html` + `js/web_login/web_login.js`: `web_dashboard`용 로그인
- 본 문서와 `wed_dashboard` 문서 세트는 `web_login / web_dashboard` 기준으로 해석

조치:

- `dashboard.js`, `web_login.js`, `dashboard_api.js`, `dashboard_app.js`
  - 파일 상단에 역할/범위 주석 추가
- `README.md`, `README_INDEX.md`
  - `온디바이스(PyQt)` 기준 표현으로 정리
  - 온디바이스 쪽은 로그인 경계까지만 명시

효과:

- `dashboard.js`를 현재 web 대시보드 기준 코드로 오해할 가능성 감소
- 팀원이 로그인 흐름을 볼 때 `온디바이스용`과 `web_dashboard용`을 바로 구분 가능

### 11.2 worker / manager / promo UX 정리

정리 완료:

- `worker` 액션 큐 / 공지
  - 실제 클릭 동작이 없는 항목은 버튼 형태 제거
  - 정보 카드로만 보이게 조정
- `manager` 미해결 알람
  - 알람이 있을 때만 `전체 보기 →` 노출
- `promo`
  - `2월 vs 3월` 하드코딩 제거
  - `meta.requestedDate` 기준 월 비교 배지로 동적화

효과:

- 클릭 가능한 것처럼 보이는데 실제로는 안 눌리는 UX 혼선 감소
- 탭 간 `전체 보기` 노출 규칙 일관성 개선
- 월/기간 배지가 실제 조회 시점과 더 잘 맞도록 정리

### 11.3 notice bar 정리

정리 기준:

- notice 구조는 유지
- 실제 공지 메시지가 있을 때만 노출
- placeholder 성격 값은 화면에 올리지 않음

조치:

- `renderNoticeBar()`에서 아래 값은 notice 미노출 처리
  - 빈 문자열
  - `null`
  - `-`
  - `없음`
  - `none`
  - `n/a`

효과:

- 상단 공지 영역이 평소에는 조용하게 유지
- 운영 공지가 실제로 들어왔을 때만 notice bar를 활용

### 11.4 clickable KPI / 상세 모달 문구 통일

정리 완료:

- 클릭 가능한 KPI에는 `상세` 칩 외에 `클릭 시 상세 보기 →` 안내 추가
- 상세 모달 제목 톤 통일
  - `상세 정보`
  - `상세 보기`
  - `상세 목록`
- 통합 상세 API 모달 섹션 제목 정리
  - `기본 요약`
  - `이력 로그`
  - `연관 항목`

효과:

- 어떤 KPI가 클릭 가능한지 더 직관적으로 구분 가능
- QA / manager 상세 모달을 오갈 때 제목/섹션 톤이 덜 들쭉날쭉함

### 11.5 날짜 문구 정리

정리 완료:

- 날짜성 문구를 `meta.requestedDate`, `viewMode` 기준으로 표기
- 과거 단일 날짜 조회 시:
  - `오늘` → `선택일`
- 기간 비교 시:
  - `기간`
- 적용 예:
  - worker `최근 10분 NG 추세` 계열 문구
  - 이벤트 카드 badge
  - promo 불량 요약 badge

효과:

- 과거 날짜를 볼 때도 화면 문구가 “오늘 기준”처럼 보이는 어색함 감소
- 기간 비교 / 단일 날짜 / 오늘 조회의 문맥이 더 자연스럽게 구분됨

### 11.6 현재 기준 다음 우선순위

1. 실제 브라우저 기준 최종 UX 점검
2. clickable KPI 범위를 더 넓힐지 유지할지 결정
3. 관리자 / 품질 화면의 문맥 설명을 더 다듬을지 검토

### 11.7 한 줄 결론

현재 `web_dashboard`는 **백엔드 연결과 응답 계약 안정화 단계를 지나, 로그인 경계와 화면 UX 해석을 정리하는 단계**까지 왔습니다.  
지금 이후 우선순위는 DB 확장보다 **사용자가 덜 헷갈리게 읽히는 화면 완성도**에 가깝습니다.

---

## 12. 추가 반영 사항: 최종 화면 폴리시 정리 (2026-03-23 추가 반영)

### 12.1 promo 전체화면 비율 보정

정리 완료:

- `promo` 전체화면에서 컨테이너를 세로 가운데 배치하지 않고, 화면 상단부터 넓게 사용하도록 조정
- KPI 카드, 중단 차트 카드, 하단 3개 카드의 세로 비율 확대
- `전월 대비` 비교 카드 레이아웃을 전체화면에서 3열 기준으로 정리
- `공지` ticker를 하단에 자연스럽게 붙도록 정렬

효과:

- 전체화면인데 카드가 중앙에 몰려 작게 보이던 느낌 완화
- 하단 공백 및 비교 카드의 빈 사분면 같은 인상 감소
- 송출 화면다운 비율과 밀도 확보

### 12.2 promo 빈 상태 처리

정리 완료:

- `현재 알람` 0건일 때 빈 박스 대신 중앙 정렬 상태 메시지 노출
- `미해결 0건`은 위험 배지 대신 안정 상태 톤으로 표시
- 하단 ticker 공지가 비어 있을 때 `운영 공지 없음`으로 표시

효과:

- 데이터가 없을 때도 화면이 덜 허전하고 덜 오작동처럼 보임
- 송출 화면에서 빈 상태를 의도된 상태로 읽을 수 있음

### 12.3 이벤트 카드 빈 상태 처리

정리 완료:

- `events`가 0건이면 이벤트 카드 내부에 `표시할 이벤트가 없습니다.` 문구 노출

효과:

- `manager`, `promo`처럼 이벤트가 비는 탭에서도 카드가 깨진 것처럼 보이지 않음

### 12.4 현재 기준 마감 판단

현재 상태:

- 응답 계약 정리 완료
- 날짜/기간 비교 흐름 안정화
- 상세 모달/KPI 클릭 흐름 정리 완료
- `promo` 전체화면 레이아웃과 빈 상태 처리까지 보정 완료

판단:

- `web_dashboard`는 현재 **구조 변경 단계보다 최종 감수 및 미세조정 단계**로 보는 것이 적절함
- 이후 수정은 대규모 리팩터링보다, 실제 브라우저 감수 결과에 따른 소폭 조정 위주가 적합함
