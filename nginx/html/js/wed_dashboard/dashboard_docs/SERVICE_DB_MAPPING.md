# SERVICE_DB_MAPPING

이 문서는 [`server_api/src/modules/dashboard/service.py`](/home/orugu/Docker/Final_project_rss/server_api/src/modules/dashboard/service.py) 와  
[`server_api/src/modules/dashboard/repository.py`](/home/orugu/Docker/Final_project_rss/server_api/src/modules/dashboard/repository.py) 기준으로,  
`web_dashboard` 4개 화면이 실제로 어떤 DB 집계 흐름을 타는지 정리한 문서입니다.

## 1. 공통 원칙

- 프론트 응답 shape는 가능하면 유지
- live 응답은 DB 집계 기준, mock은 fallback 기준
- 공통 날짜 필터는 `date_from`, `date_to`
- 공통 line 정책은 `meta.line` 기준
- `worker`는 focus line 중심
- `qa / manager / promo`는 전체 라인 기준 집계가 기본

## 2. 공통 메타/필터

담당 함수:

- `_web_dashboard_meta()`
- `_resolve_dashboard_dates()`
- `_resolve_period_compare_range()`
- `_apply_web_snapshot_meta()`

역할:

- 화면 공통 `meta` 생성
- 단일 날짜 / 기간 비교 모드 결정
- `requestedDate`, `scenarioDate`, `requestedDateRange` 반영
- `filters.date_from`, `filters.date_to`를 ISO 문자열로 정규화

## 3. 공통 원천 집계

핵심 스냅샷 생성:

- `get_web_dashboard_snapshot()`

주요 참조 테이블:

- `wed_dashboard.production_records`
- `wed_dashboard.inspection_results`
- `wed_dashboard.defect_results`
- `wed_dashboard.equipment_status_history`
- `wed_dashboard.alarms`
- `wed_dashboard.alarm_ack_history`
- `wed_dashboard.recheck_queue`
- `wed_dashboard.event_logs`
- `wed_dashboard.line_environment`
- `wed_dashboard.lines`
- `wed_dashboard.equipments`
- `wed_dashboard.factories`

## 4. worker 매핑

주요 함수:

- `get_web_worker_dashboard()`
- `_web_worker_dashboard_bundle()`
- `_apply_web_worker_live()`

핵심 필드 매핑:

- `kpis.worker_hourly_output`
  - `production_records.produced_qty`
- `kpis.worker_line_output`
  - focus line 누적 생산량
- `kpis.worker_recent_10m_ng`
  - `defect_results`의 최근 10분 NG 합계
- `kpis.worker_achievement`
  - focus line availability 기반
- `lineTemperature`
  - `line_environment` 기반
- `statusGrid`
  - `equipment_status_history` + `equipments` + NG 집계
- `actionQueue`
  - focus line 알람 + down 설비 + 최근 NG 급증 조합
- `globalNotices`
  - focus line 외 `global_events`
- `ngTrend`
  - focus line NG 추세
- `ngTypes`
  - top defects 고정 슬롯
- `events`
  - focus line event 조합

현재 상세 연결:

- `worker_recent_10m_ng` -> `worker.action.detail` 또는 `common.alarm.detail`

## 5. qa 매핑

주요 함수:

- `get_web_qa_dashboard()`
- `_web_qa_dashboard_bundle()`
- `_apply_web_qa_live()`

핵심 필드 매핑:

- `kpis.qa_defect_rate`
  - `total_ng / total_checked`
- `kpis.qa_recheck`
  - `recheck_queue` 집계
- `kpis.qa_inspect`
  - `inspection_results.total_checked_qty`
- `kpis.qa_total_output`
  - `production_records.produced_qty`
- `topDefects`
  - `defect_results` top defects
- `recheckQueue`
  - `recheck_queue`
- `defectTrend`
  - 시간대별 생산/NG 기반 불량률
- `issues`
  - `issue_rows` 가공 결과
- `events`
  - `recheck_queue` + `alarms`

현재 상세 연결:

- `qa_defect_rate` -> `qa.defect.detail`
- `qa_recheck` -> `qa.reinspection.queue`

## 6. manager 매핑

주요 함수:

- `get_web_manager_dashboard()`
- `_web_manager_dashboard_bundle()`
- `_apply_web_manager_live()`

핵심 필드 매핑:

- `kpis.mgr_oee`
  - `_overall_oee_components()`
- `kpis.mgr_achievement`
  - 현재 생산량 / 계획 대비
- `kpis.mgr_today_output`
  - 총 생산량
- `kpis.mgr_expected_output`
  - 시간 경과 기반 예상 종료 생산
- `managerLineOee`
  - `line_production[].oee`
  - 현재는 0~100 범위로 clamp
- `managerProductionTrend`
  - 시간대별 누적 생산 vs 계획
- `managerDefectTrend`
  - 시간대별 불량률
- `riskOverall`
  - 최상위 위험 알람 또는 총 리스크 요약
- `riskLines`
  - line risk score 정렬
- `pendingActions`
  - active alarm 기반 action 목록
- `activeAlarms`
  - `alarms` + `ack_status`
- `events`
  - 활성 알람 기반 최근 이벤트

현재 상세 연결:

- `mgr_oee` -> `common.alarm.detail`
  - 활성 알람이 있을 때만 clickable

## 7. promo 매핑

주요 함수:

- `get_web_promo_dashboard()`
- `_web_promo_dashboard_bundle()`
- `_apply_web_promo_live()`

핵심 필드 매핑:

- `promo_today_output`
  - 당일 생산량
- `promo_month_output`
  - 월 누적 생산량
- `promo_oee`
  - 전체 OEE
- `promo_defect_rate`
  - 전체 불량률
- `promo_delivery_rate`
  - 양품률/납기 달성률 성격의 송출용 KPI
- `promoWeekProduction`
  - 최근 주간/기간 생산 비교
- `promoLines`
  - 라인별 상태 요약
- `promoTopDefects`
  - top defects
- `promoCurrentAlarms`
  - 현재 알람
- `promoMonthlyCompare`
  - 월 비교 카드
- `promoTicker`
  - 송출용 롤링 메시지

현재 주의점:

- 기간 비교 로직은 `_apply_period_compare_promo()` 사용
- `promoWeekProduction[*].target`은 `daily_target` 기준

## 8. period compare 매핑

담당 함수:

- `_build_daily_compare_rows()`
- `_apply_period_compare_worker()`
- `_apply_period_compare_qa()`
- `_apply_period_compare_manager()`
- `_apply_period_compare_promo()`

규칙:

- `date_from == date_to`면 단일 날짜 live
- `date_from != date_to`면 기간 비교
- 각 탭은 `dailyCompare`를 추가로 반환
- `meta.viewMode = period_compare`
- `meta.dataMode = period_compare`

## 9. detail API 매핑

담당 함수:

- `get_dashboard_detail()`
- `_find_live_detail_content()`

live 상세 매핑:

- `defect` -> `get_defect_detail()`
- `lot` -> `get_lot_detail()`
- `alarm` -> `get_alarm_detail()`
- `inspection / event` -> `get_request_detail()`

즉 상세 연결의 핵심 target type은 현재:

- `defect`
- `lot`
- `alarm`

## 10. 한 줄 결론

현재 `SERVICE_DB_MAPPING`의 핵심은  
**web_dashboard 화면은 이미 live DB 집계 기준으로 동작하고 있고, mock은 보조 fallback일 뿐이라는 점**입니다.  
다음 유지보수는 DB 추가보다 `날짜`, `상세`, `화면 의미 일관성`을 중심으로 보면 됩니다.
