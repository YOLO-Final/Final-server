BEGIN;
CREATE SCHEMA IF NOT EXISTS wed_dashboard;
SET search_path TO wed_dashboard, public;

CREATE TABLE IF NOT EXISTS factories (
    factory_id      BIGSERIAL PRIMARY KEY,
    factory_code    VARCHAR(30) NOT NULL UNIQUE,
    factory_name    VARCHAR(100) NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lines (
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
CREATE INDEX IF NOT EXISTS idx_lines_factory_id ON lines(factory_id);
CREATE INDEX IF NOT EXISTS idx_lines_active ON lines(is_active);

CREATE TABLE IF NOT EXISTS equipments (
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
CREATE INDEX IF NOT EXISTS idx_equipments_line_id ON equipments(line_id);
CREATE INDEX IF NOT EXISTS idx_equipments_type ON equipments(equip_type);
CREATE INDEX IF NOT EXISTS idx_equipments_active ON equipments(is_active);

CREATE TABLE IF NOT EXISTS employees (
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
CREATE INDEX IF NOT EXISTS idx_employees_line_id ON employees(line_id);
CREATE INDEX IF NOT EXISTS idx_employees_role_code ON employees(role_code);

CREATE TABLE IF NOT EXISTS production_records (
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
CREATE INDEX IF NOT EXISTS idx_production_records_line_time
    ON production_records(line_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_production_records_factory_time
    ON production_records(factory_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_production_records_work_date
    ON production_records(work_date);
CREATE INDEX IF NOT EXISTS idx_production_records_lot_id
    ON production_records(lot_id);

CREATE TABLE IF NOT EXISTS equipment_status_history (
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
CREATE INDEX IF NOT EXISTS idx_equipment_status_history_equip_time
    ON equipment_status_history(equip_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_equipment_status_history_line_time
    ON equipment_status_history(line_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_equipment_status_history_status
    ON equipment_status_history(status_code);

CREATE TABLE IF NOT EXISTS inspection_results (
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
CREATE INDEX IF NOT EXISTS idx_inspection_results_line_time
    ON inspection_results(line_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_inspection_results_lot_id
    ON inspection_results(lot_id);
CREATE INDEX IF NOT EXISTS idx_inspection_results_type
    ON inspection_results(inspection_type);

CREATE TABLE IF NOT EXISTS defect_results (
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
CREATE INDEX IF NOT EXISTS idx_defect_results_line_time
    ON defect_results(line_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_defect_results_defect_code
    ON defect_results(defect_code);
CREATE INDEX IF NOT EXISTS idx_defect_results_lot_id
    ON defect_results(lot_id);
CREATE INDEX IF NOT EXISTS idx_defect_results_severity
    ON defect_results(severity);

CREATE TABLE IF NOT EXISTS alarms (
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
CREATE INDEX IF NOT EXISTS idx_alarms_line_time
    ON alarms(line_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_alarms_equip_time
    ON alarms(equip_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_alarms_status
    ON alarms(status);
CREATE INDEX IF NOT EXISTS idx_alarms_severity
    ON alarms(severity);

CREATE TABLE IF NOT EXISTS alarm_ack_history (
    ack_id             BIGSERIAL PRIMARY KEY,
    alarm_id_ref       BIGINT NOT NULL REFERENCES alarms(alarm_id),
    ack_status         VARCHAR(20) NOT NULL,
    handled_by         BIGINT REFERENCES employees(employee_id),
    handled_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    note               VARCHAR(255),
    CHECK (ack_status IN ('unack', 'hold', 'ack'))
);
CREATE INDEX IF NOT EXISTS idx_alarm_ack_history_alarm_id
    ON alarm_ack_history(alarm_id_ref, handled_at DESC);
CREATE INDEX IF NOT EXISTS idx_alarm_ack_history_status
    ON alarm_ack_history(ack_status);

CREATE TABLE IF NOT EXISTS recheck_queue (
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
CREATE INDEX IF NOT EXISTS idx_recheck_queue_line_status
    ON recheck_queue(line_id, status, queued_at DESC);
CREATE INDEX IF NOT EXISTS idx_recheck_queue_lot_id
    ON recheck_queue(lot_id);
CREATE INDEX IF NOT EXISTS idx_recheck_queue_priority
    ON recheck_queue(priority);

CREATE TABLE IF NOT EXISTS event_logs (
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
CREATE INDEX IF NOT EXISTS idx_event_logs_time
    ON event_logs(recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_event_logs_line_time
    ON event_logs(line_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_event_logs_severity
    ON event_logs(severity);

CREATE TABLE IF NOT EXISTS line_environment (
    env_id              BIGSERIAL PRIMARY KEY,
    line_id             BIGINT NOT NULL REFERENCES lines(line_id),
    sensor_type         VARCHAR(50) NOT NULL,
    metric_name         VARCHAR(50) NOT NULL,
    metric_value        NUMERIC(10,2) NOT NULL,
    unit                VARCHAR(20),
    recorded_at         TIMESTAMPTZ NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_line_environment_line_time
    ON line_environment(line_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_line_environment_metric
    ON line_environment(metric_name, recorded_at DESC);

COMMIT;
