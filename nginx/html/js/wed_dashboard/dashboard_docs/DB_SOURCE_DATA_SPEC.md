# DB_SOURCE_DATA_SPEC

이 문서는 `wed_dashboard` 구현에 필요한 **DB 원천 데이터** 기준 초안입니다.  
즉, 프론트 카드에 바로 내려주는 구조가 아니라 **무엇을 저장해야 하는가**를 기준으로 정리합니다.

## 1. 핵심 엔티티

권장 엔티티는 아래와 같습니다.

1. 공장 / 라인 / 설비 마스터
2. 생산 실적
3. 설비 상태 이력
4. 검사 결과
5. 불량 결과
6. 알람 이력
7. ACK 처리 이력
8. 재검 큐
9. 이벤트 로그
10. 근무조 / 작업자 맥락 정보

## 2. 권장 테이블 초안

### 2.1 factories

공장 마스터

주요 컬럼:

- `factory_id`
- `factory_name`
- `factory_code`
- `is_active`
- `created_at`
- `updated_at`

### 2.2 lines

라인 마스터

주요 컬럼:

- `line_id`
- `factory_id`
- `line_code`
- `line_name`
- `line_type`
- `is_active`
- `created_at`
- `updated_at`

### 2.3 equipments

설비 마스터

주요 컬럼:

- `equip_id`
- `line_id`
- `equip_code`
- `equip_name`
- `equip_type`
- `vendor`
- `install_date`
- `is_active`
- `created_at`
- `updated_at`

### 2.4 production_records

생산 실적 원천 데이터

주요 컬럼:

- `production_id`
- `factory_id`
- `line_id`
- `equip_id` 또는 `process_id`
- `work_date`
- `work_shift`
- `lot_id`
- `model_code`
- `produced_qty`
- `good_qty`
- `ng_qty`
- `recorded_at`

이 테이블로부터 계산 가능한 값:

- 시간당 생산량
- 현재 라인 생산량
- 오늘 생산량
- 이번 달 생산량
- 예상 종료 생산량

### 2.5 equipment_status_history

설비 상태 이력

주요 컬럼:

- `status_id`
- `line_id`
- `equip_id`
- `status_code`
  - 예: `run`, `idle`, `down`, `maint`
- `started_at`
- `ended_at`
- `duration_sec`
- `reason_code`
- `reason_text`
- `recorded_at`

이 테이블로부터 계산 가능한 값:

- 가동률
- 다운타임
- OEE 일부 요소
- 설비 상태 카드

### 2.6 inspection_results

검사 결과 원천 데이터

주요 컬럼:

- `inspection_id`
- `line_id`
- `equip_id`
- `lot_id`
- `model_code`
- `inspection_type`
- `total_checked_qty`
- `pass_qty`
- `fail_qty`
- `recorded_at`

이 테이블로부터 계산 가능한 값:

- 검사 현황
- 품질 추세
- 품질 비교 지표

### 2.7 defect_results

불량 결과 원천 데이터

주요 컬럼:

- `defect_id`
- `line_id`
- `equip_id`
- `lot_id`
- `model_code`
- `defect_code`
- `defect_name`
- `defect_count`
- `severity`
- `cause_code`
- `cause_text`
- `recorded_at`

이 테이블로부터 계산 가능한 값:

- 최근 10분 NG
- 불량 유형 Top N
- 불량 원인 기여도
- 불량률

### 2.8 alarms

알람 발생 이력

주요 컬럼:

- `alarm_id`
- `line_id`
- `equip_id`
- `alarm_code`
- `alarm_name`
- `severity`
- `cause_code`
- `message`
- `occurred_at`
- `cleared_at`
- `status`

이 테이블로부터 계산 가능한 값:

- 현재 알람
- 미해결 알람
- 알람 기반 리스크

### 2.9 alarm_ack_history

ACK / HOLD / 확인 이력

주요 컬럼:

- `ack_id`
- `alarm_id`
- `ack_status`
  - 예: `unack`, `hold`, `ack`
- `handled_by`
- `handled_at`
- `note`

### 2.10 recheck_queue

재검 큐

주요 컬럼:

- `recheck_id`
- `lot_id`
- `line_id`
- `equip_id`
- `defect_code`
- `priority`
- `severity`
- `queued_at`
- `status`
- `owner`
- `note`

### 2.11 event_logs

화면 하단 최근 이벤트용 로그

주요 컬럼:

- `event_id`
- `event_type`
- `severity`
- `line_id`
- `equip_id`
- `title`
- `message`
- `meta`
- `recorded_at`

### 2.12 line_environment

온도/환경 센서 데이터

주요 컬럼:

- `env_id`
- `line_id`
- `sensor_type`
- `metric_name`
- `metric_value`
- `unit`
- `recorded_at`

이 테이블로부터 계산 가능한 값:

- 현재 온도
- 경고/위험 온도 상태

## 3. DB에 저장하지 않아도 되는 것

아래 값은 DB 컬럼으로 직접 저장하지 않아도 됩니다.

- `kpis[]`
- `riskOverall`
- `pendingActions`
- `추세 상태` 문구
- `hint`
- `promoTicker`
- `managerLineOee`

이 값들은 보통

- SQL 집계
- 서비스 로직 계산
- 룰 엔진

으로 생성하는 것이 더 자연스럽습니다.

## 4. 최소 우선 도입 순서

처음부터 모든 테이블을 만드는 대신 아래 순서를 권장합니다.

1. `lines`
2. `equipments`
3. `production_records`
4. `equipment_status_history`
5. `defect_results`
6. `alarms`
7. `recheck_queue`
8. `event_logs`

이 정도만 있어도 `worker / qa / manager / promo` 화면 대부분을 mock 없이 채울 수 있습니다.
