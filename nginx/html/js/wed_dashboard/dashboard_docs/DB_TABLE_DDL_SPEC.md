# DB_TABLE_DDL_SPEC

이 문서는 `wed_dashboard` 용 데이터 저장소를 실제 구현할 때 참고할 수 있는  
**PostgreSQL 기준 `CREATE TABLE` 초안**입니다.

주의:

- 이 문서는 운영 반영 전 설계 초안입니다.
- DBMS는 PostgreSQL 기준으로 작성했습니다.
- 실제 프로젝트에서는 사내 규칙에 맞춰 스키마명, 타입, 제약조건을 조정해야 합니다.
- 화면 표시용 문구/집계값은 여기서 직접 저장하지 않고 원천 테이블 기준으로 계산하는 것을 전제로 합니다.

## 1. 설계 전제

- PK는 `bigserial` 또는 `bigint` 기반
- 코드성 값은 `varchar`
- 시계열 데이터는 `timestamptz`
- 삭제보다는 `is_active`/상태값으로 관리
- 화면 집계 성능을 위해 주요 조회 컬럼에는 인덱스 추가

## 2. 권장 생성 순서

1. `factories`
2. `lines`
3. `equipments`
4. `employees`
5. `production_records`
6. `equipment_status_history`
7. `inspection_results`
8. `defect_results`
9. `alarms`
10. `alarm_ack_history`
11. `recheck_queue`
12. `event_logs`
13. `line_environment`

## 3. DDL 초안

### 3.1 factories

```sql
CREATE TABLE factories (
    factory_id      BIGSERIAL PRIMARY KEY,
    factory_code    VARCHAR(30) NOT NULL UNIQUE,
    factory_name    VARCHAR(100) NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 3.2 lines

```sql
CREATE TABLE lines (
    line_id          BIGSERIAL PRIMARY KEY,
    factory_id       BIGINT NOT NULL REFERENCES factories(factory_id),
    line_code        VARCHAR(30) NOT NULL UNIQUE,
    line_name        VARCHAR(100) NOT NULL,
    line_type        VARCHAR(50),
    sort_order       INTEGER NOT NULL DEFAULT 0,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_lines_factory_id ON lines(factory_id);
CREATE INDEX idx_lines_active ON lines(is_active);
```

### 3.3 equipments

```sql
CREATE TABLE equipments (
    equip_id          BIGSERIAL PRIMARY KEY,
    line_id           BIGINT NOT NULL REFERENCES lines(line_id),
    equip_code        VARCHAR(50) NOT NULL UNIQUE,
    equip_name        VARCHAR(100) NOT NULL,
    equip_type        VARCHAR(50) NOT NULL,
    vendor            VARCHAR(100),
    model_name        VARCHAR(100),
    install_date      DATE,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_equipments_line_id ON equipments(line_id);
CREATE INDEX idx_equipments_type ON equipments(equip_type);
CREATE INDEX idx_equipments_active ON equipments(is_active);
```

### 3.4 employees

```sql
CREATE TABLE employees (
    employee_id        BIGSERIAL PRIMARY KEY,
    employee_no        VARCHAR(30) NOT NULL UNIQUE,
    employee_name      VARCHAR(100) NOT NULL,
    role_code          VARCHAR(30) NOT NULL,
    line_id            BIGINT REFERENCES lines(line_id),
    shift_code         VARCHAR(30),
    is_active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_employees_line_id ON employees(line_id);
CREATE INDEX idx_employees_role_code ON employees(role_code);
```

### 3.5 production_records

```sql
CREATE TABLE production_records (
    production_id      BIGSERIAL PRIMARY KEY,
    factory_id         BIGINT NOT NULL REFERENCES factories(factory_id),
    line_id            BIGINT NOT NULL REFERENCES lines(line_id),
    equip_id           BIGINT REFERENCES equipments(equip_id),
    lot_id             VARCHAR(60),
    model_code         VARCHAR(60),
    work_date          DATE NOT NULL,
    work_shift         VARCHAR(30) NOT NULL,
    produced_qty       INTEGER NOT NULL DEFAULT 0,
    good_qty           INTEGER NOT NULL DEFAULT 0,
    ng_qty             INTEGER NOT NULL DEFAULT 0,
    recorded_at        TIMESTAMPTZ NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_production_records_line_time
    ON production_records(line_id, recorded_at DESC);

CREATE INDEX idx_production_records_factory_time
    ON production_records(factory_id, recorded_at DESC);

CREATE INDEX idx_production_records_work_date
    ON production_records(work_date);

CREATE INDEX idx_production_records_lot_id
    ON production_records(lot_id);
```

### 3.6 equipment_status_history

```sql
CREATE TABLE equipment_status_history (
    status_id          BIGSERIAL PRIMARY KEY,
    line_id            BIGINT NOT NULL REFERENCES lines(line_id),
    equip_id           BIGINT NOT NULL REFERENCES equipments(equip_id),
    status_code        VARCHAR(20) NOT NULL,
    reason_code        VARCHAR(50),
    reason_text        VARCHAR(255),
    started_at         TIMESTAMPTZ NOT NULL,
    ended_at           TIMESTAMPTZ,
    duration_sec       INTEGER,
    recorded_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status_code IN ('run', 'idle', 'down', 'maint'))
);

CREATE INDEX idx_equipment_status_history_equip_time
    ON equipment_status_history(equip_id, started_at DESC);

CREATE INDEX idx_equipment_status_history_line_time
    ON equipment_status_history(line_id, started_at DESC);

CREATE INDEX idx_equipment_status_history_status
    ON equipment_status_history(status_code);
```

### 3.7 inspection_results

```sql
CREATE TABLE inspection_results (
    inspection_id        BIGSERIAL PRIMARY KEY,
    line_id              BIGINT NOT NULL REFERENCES lines(line_id),
    equip_id             BIGINT REFERENCES equipments(equip_id),
    lot_id               VARCHAR(60),
    model_code           VARCHAR(60),
    inspection_type      VARCHAR(50) NOT NULL,
    total_checked_qty    INTEGER NOT NULL DEFAULT 0,
    pass_qty             INTEGER NOT NULL DEFAULT 0,
    fail_qty             INTEGER NOT NULL DEFAULT 0,
    recorded_at          TIMESTAMPTZ NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_inspection_results_line_time
    ON inspection_results(line_id, recorded_at DESC);

CREATE INDEX idx_inspection_results_lot_id
    ON inspection_results(lot_id);

CREATE INDEX idx_inspection_results_type
    ON inspection_results(inspection_type);
```

### 3.8 defect_results

```sql
CREATE TABLE defect_results (
    defect_id          BIGSERIAL PRIMARY KEY,
    line_id            BIGINT NOT NULL REFERENCES lines(line_id),
    equip_id           BIGINT REFERENCES equipments(equip_id),
    lot_id             VARCHAR(60),
    model_code         VARCHAR(60),
    defect_code        VARCHAR(60) NOT NULL,
    defect_name        VARCHAR(100) NOT NULL,
    defect_count       INTEGER NOT NULL DEFAULT 0,
    severity           VARCHAR(20),
    cause_code         VARCHAR(60),
    cause_text         VARCHAR(255),
    recorded_at        TIMESTAMPTZ NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_defect_results_line_time
    ON defect_results(line_id, recorded_at DESC);

CREATE INDEX idx_defect_results_defect_code
    ON defect_results(defect_code);

CREATE INDEX idx_defect_results_lot_id
    ON defect_results(lot_id);

CREATE INDEX idx_defect_results_severity
    ON defect_results(severity);
```

### 3.9 alarms

```sql
CREATE TABLE alarms (
    alarm_id           BIGSERIAL PRIMARY KEY,
    line_id            BIGINT NOT NULL REFERENCES lines(line_id),
    equip_id           BIGINT REFERENCES equipments(equip_id),
    alarm_code         VARCHAR(60) NOT NULL,
    alarm_name         VARCHAR(120),
    cause_code         VARCHAR(60),
    severity           VARCHAR(20) NOT NULL,
    message            VARCHAR(255) NOT NULL,
    status             VARCHAR(20) NOT NULL DEFAULT 'active',
    occurred_at        TIMESTAMPTZ NOT NULL,
    cleared_at         TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (severity IN ('critical', 'warning', 'info', 'ok')),
    CHECK (status IN ('active', 'cleared', 'hold'))
);

CREATE INDEX idx_alarms_line_time
    ON alarms(line_id, occurred_at DESC);

CREATE INDEX idx_alarms_equip_time
    ON alarms(equip_id, occurred_at DESC);

CREATE INDEX idx_alarms_status
    ON alarms(status);

CREATE INDEX idx_alarms_severity
    ON alarms(severity);
```

### 3.10 alarm_ack_history

```sql
CREATE TABLE alarm_ack_history (
    ack_id             BIGSERIAL PRIMARY KEY,
    alarm_id_ref       BIGINT NOT NULL REFERENCES alarms(alarm_id),
    ack_status         VARCHAR(20) NOT NULL,
    handled_by         BIGINT REFERENCES employees(employee_id),
    handled_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    note               VARCHAR(255),
    CHECK (ack_status IN ('unack', 'hold', 'ack'))
);

CREATE INDEX idx_alarm_ack_history_alarm_id
    ON alarm_ack_history(alarm_id_ref, handled_at DESC);

CREATE INDEX idx_alarm_ack_history_status
    ON alarm_ack_history(ack_status);
```

### 3.11 recheck_queue

```sql
CREATE TABLE recheck_queue (
    recheck_id         BIGSERIAL PRIMARY KEY,
    lot_id             VARCHAR(60) NOT NULL,
    line_id            BIGINT NOT NULL REFERENCES lines(line_id),
    equip_id           BIGINT REFERENCES equipments(equip_id),
    defect_code        VARCHAR(60) NOT NULL,
    priority           VARCHAR(20) NOT NULL,
    severity           VARCHAR(20) NOT NULL,
    status             VARCHAR(20) NOT NULL DEFAULT 'queued',
    count_qty          INTEGER NOT NULL DEFAULT 0,
    cause_text         VARCHAR(255),
    owner_employee_id  BIGINT REFERENCES employees(employee_id),
    queued_at          TIMESTAMPTZ NOT NULL,
    completed_at       TIMESTAMPTZ,
    note               VARCHAR(255),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (priority IN ('LOW', 'MEDIUM', 'HIGH')),
    CHECK (severity IN ('critical', 'warning', 'info')),
    CHECK (status IN ('queued', 'in_progress', 'done', 'hold'))
);

CREATE INDEX idx_recheck_queue_line_status
    ON recheck_queue(line_id, status, queued_at DESC);

CREATE INDEX idx_recheck_queue_lot_id
    ON recheck_queue(lot_id);

CREATE INDEX idx_recheck_queue_priority
    ON recheck_queue(priority);
```

### 3.12 event_logs

```sql
CREATE TABLE event_logs (
    event_id            BIGSERIAL PRIMARY KEY,
    event_type          VARCHAR(50) NOT NULL,
    severity            VARCHAR(20),
    line_id             BIGINT REFERENCES lines(line_id),
    equip_id            BIGINT REFERENCES equipments(equip_id),
    title               VARCHAR(120) NOT NULL,
    message             VARCHAR(255) NOT NULL,
    meta_text           VARCHAR(255),
    recorded_at         TIMESTAMPTZ NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_event_logs_time
    ON event_logs(recorded_at DESC);

CREATE INDEX idx_event_logs_line_time
    ON event_logs(line_id, recorded_at DESC);

CREATE INDEX idx_event_logs_severity
    ON event_logs(severity);
```

### 3.13 line_environment

```sql
CREATE TABLE line_environment (
    env_id              BIGSERIAL PRIMARY KEY,
    line_id             BIGINT NOT NULL REFERENCES lines(line_id),
    sensor_type         VARCHAR(50) NOT NULL,
    metric_name         VARCHAR(50) NOT NULL,
    metric_value        NUMERIC(10,2) NOT NULL,
    unit                VARCHAR(20),
    recorded_at         TIMESTAMPTZ NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_line_environment_line_time
    ON line_environment(line_id, recorded_at DESC);

CREATE INDEX idx_line_environment_metric
    ON line_environment(metric_name, recorded_at DESC);
```

## 4. 뷰/집계 테이블 권장

대시보드 성능을 위해 아래 뷰 또는 집계 테이블을 권장합니다.

### 예시

- `mv_line_hourly_output`
- `mv_line_daily_output`
- `mv_line_oee_daily`
- `mv_defect_topn_daily`
- `mv_alarm_active`
- `mv_recheck_pending`

예:

```sql
CREATE MATERIALIZED VIEW mv_line_hourly_output AS
SELECT
    line_id,
    date_trunc('hour', recorded_at) AS hour_bucket,
    SUM(produced_qty) AS produced_qty,
    SUM(good_qty) AS good_qty,
    SUM(ng_qty) AS ng_qty
FROM production_records
GROUP BY line_id, date_trunc('hour', recorded_at);
```

## 5. 프론트 응답과의 관계

이 DDL은 원천 저장 구조 기준입니다.

즉 다음 값들은 이 테이블에 그대로 저장하는 개념이 아닙니다.

- `kpis`
- `riskOverall`
- `pendingActions`
- `managerLineOee`
- `promoMonthlyCompare`
- `hint`
- `추세 상태`

이 값들은:

1. 위 원천 테이블을 조회하고
2. 서버에서 계산/가공한 뒤
3. `API_RESPONSE_SCHEMA.md` 형태로 내려주는 것이 맞습니다.

## 6. 권장 다음 단계

이 문서 다음으로 이어질 작업은 보통 아래와 같습니다.

1. 실제 사용하는 DBMS 확정
2. 컬럼명/코드값 사내 표준 반영
3. enum 테이블 또는 코드 테이블 분리 여부 결정
4. materialized view / 집계 배치 전략 확정
5. `API_RESPONSE_SCHEMA.md` 와 1:1 매핑 표 작성
