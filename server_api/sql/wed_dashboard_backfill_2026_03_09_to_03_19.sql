BEGIN;
SET search_path TO wed_dashboard, public;

-- 2026-03-20~2026-03-25 구간 더미를 기준으로
-- 1) -11일 => 2026-03-09~2026-03-14
-- 2) -5일  => 2026-03-15~2026-03-19
-- 를 백필한다.
WITH shifts(days, delta) AS (
    VALUES
      (-11, INTERVAL '-11 days'),
      (-5,  INTERVAL '-5 days')
)
INSERT INTO production_records (
    factory_id, line_id, equip_id, lot_id, model_code, work_date, work_shift,
    produced_qty, good_qty, ng_qty, recorded_at, created_at
)
SELECT
    p.factory_id,
    p.line_id,
    p.equip_id,
    p.lot_id,
    p.model_code,
    (p.work_date + s.days),
    p.work_shift,
    p.produced_qty,
    p.good_qty,
    p.ng_qty,
    p.recorded_at + s.delta,
    p.created_at + s.delta
FROM production_records p
CROSS JOIN shifts s
WHERE p.work_date BETWEEN DATE '2026-03-20' AND DATE '2026-03-25'
  AND (p.work_date + s.days) BETWEEN DATE '2026-03-09' AND DATE '2026-03-19'
  AND NOT EXISTS (
      SELECT 1
      FROM production_records x
      WHERE x.line_id = p.line_id
        AND COALESCE(x.equip_id, -1) = COALESCE(p.equip_id, -1)
        AND COALESCE(x.lot_id, '') = COALESCE(p.lot_id, '')
        AND x.recorded_at = p.recorded_at + s.delta
  );

WITH shifts(days, delta) AS (
    VALUES
      (-11, INTERVAL '-11 days'),
      (-5,  INTERVAL '-5 days')
)
INSERT INTO inspection_results (
    line_id, equip_id, lot_id, model_code, inspection_type,
    total_checked_qty, pass_qty, fail_qty, recorded_at, created_at
)
SELECT
    r.line_id,
    r.equip_id,
    r.lot_id,
    r.model_code,
    r.inspection_type,
    r.total_checked_qty,
    r.pass_qty,
    r.fail_qty,
    r.recorded_at + s.delta,
    r.created_at + s.delta
FROM inspection_results r
CROSS JOIN shifts s
WHERE (r.recorded_at AT TIME ZONE 'Asia/Seoul')::date BETWEEN DATE '2026-03-20' AND DATE '2026-03-25'
  AND ((r.recorded_at + s.delta) AT TIME ZONE 'Asia/Seoul')::date BETWEEN DATE '2026-03-09' AND DATE '2026-03-19'
  AND NOT EXISTS (
      SELECT 1
      FROM inspection_results x
      WHERE x.line_id = r.line_id
        AND COALESCE(x.equip_id, -1) = COALESCE(r.equip_id, -1)
        AND COALESCE(x.lot_id, '') = COALESCE(r.lot_id, '')
        AND x.recorded_at = r.recorded_at + s.delta
  );

WITH shifts(days, delta) AS (
    VALUES
      (-11, INTERVAL '-11 days'),
      (-5,  INTERVAL '-5 days')
)
INSERT INTO defect_results (
    line_id, equip_id, lot_id, model_code, defect_code, defect_name, defect_count,
    severity, cause_code, cause_text, recorded_at, created_at
)
SELECT
    d.line_id,
    d.equip_id,
    d.lot_id,
    d.model_code,
    d.defect_code,
    d.defect_name,
    d.defect_count,
    d.severity,
    d.cause_code,
    d.cause_text,
    d.recorded_at + s.delta,
    d.created_at + s.delta
FROM defect_results d
CROSS JOIN shifts s
WHERE (d.recorded_at AT TIME ZONE 'Asia/Seoul')::date BETWEEN DATE '2026-03-20' AND DATE '2026-03-25'
  AND ((d.recorded_at + s.delta) AT TIME ZONE 'Asia/Seoul')::date BETWEEN DATE '2026-03-09' AND DATE '2026-03-19'
  AND NOT EXISTS (
      SELECT 1
      FROM defect_results x
      WHERE x.line_id = d.line_id
        AND COALESCE(x.equip_id, -1) = COALESCE(d.equip_id, -1)
        AND COALESCE(x.lot_id, '') = COALESCE(d.lot_id, '')
        AND COALESCE(x.defect_code, '') = COALESCE(d.defect_code, '')
        AND x.recorded_at = d.recorded_at + s.delta
  );

WITH shifts(days, delta) AS (
    VALUES
      (-11, INTERVAL '-11 days'),
      (-5,  INTERVAL '-5 days')
)
INSERT INTO equipment_status_history (
    line_id, equip_id, status_code, reason_code, reason_text,
    started_at, ended_at, duration_sec, recorded_at, created_at
)
SELECT
    e.line_id,
    e.equip_id,
    e.status_code,
    e.reason_code,
    e.reason_text,
    e.started_at + s.delta,
    CASE WHEN e.ended_at IS NULL THEN NULL ELSE e.ended_at + s.delta END,
    e.duration_sec,
    e.recorded_at + s.delta,
    e.created_at + s.delta
FROM equipment_status_history e
CROSS JOIN shifts s
WHERE (e.started_at AT TIME ZONE 'Asia/Seoul')::date BETWEEN DATE '2026-03-20' AND DATE '2026-03-25'
  AND ((e.started_at + s.delta) AT TIME ZONE 'Asia/Seoul')::date BETWEEN DATE '2026-03-09' AND DATE '2026-03-19'
  AND NOT EXISTS (
      SELECT 1
      FROM equipment_status_history x
      WHERE x.line_id = e.line_id
        AND x.equip_id = e.equip_id
        AND x.started_at = e.started_at + s.delta
        AND x.status_code = e.status_code
  );

WITH shifts(days, delta) AS (
    VALUES
      (-11, INTERVAL '-11 days'),
      (-5,  INTERVAL '-5 days')
)
INSERT INTO line_environment (
    line_id, sensor_type, metric_name, metric_value, unit, recorded_at, created_at
)
SELECT
    l.line_id,
    l.sensor_type,
    l.metric_name,
    l.metric_value,
    l.unit,
    l.recorded_at + s.delta,
    l.created_at + s.delta
FROM line_environment l
CROSS JOIN shifts s
WHERE (l.recorded_at AT TIME ZONE 'Asia/Seoul')::date BETWEEN DATE '2026-03-20' AND DATE '2026-03-25'
  AND ((l.recorded_at + s.delta) AT TIME ZONE 'Asia/Seoul')::date BETWEEN DATE '2026-03-09' AND DATE '2026-03-19'
  AND NOT EXISTS (
      SELECT 1
      FROM line_environment x
      WHERE x.line_id = l.line_id
        AND x.sensor_type = l.sensor_type
        AND x.metric_name = l.metric_name
        AND x.recorded_at = l.recorded_at + s.delta
  );

WITH shifts(days, delta) AS (
    VALUES
      (-11, INTERVAL '-11 days'),
      (-5,  INTERVAL '-5 days')
)
INSERT INTO event_logs (
    event_type, severity, line_id, equip_id, title, message, meta_text, recorded_at, created_at
)
SELECT
    ev.event_type,
    ev.severity,
    ev.line_id,
    ev.equip_id,
    ev.title,
    ev.message,
    ev.meta_text,
    ev.recorded_at + s.delta,
    ev.created_at + s.delta
FROM event_logs ev
CROSS JOIN shifts s
WHERE (ev.recorded_at AT TIME ZONE 'Asia/Seoul')::date BETWEEN DATE '2026-03-20' AND DATE '2026-03-25'
  AND ((ev.recorded_at + s.delta) AT TIME ZONE 'Asia/Seoul')::date BETWEEN DATE '2026-03-09' AND DATE '2026-03-19'
  AND NOT EXISTS (
      SELECT 1
      FROM event_logs x
      WHERE x.event_type = ev.event_type
        AND COALESCE(x.line_id, -1) = COALESCE(ev.line_id, -1)
        AND COALESCE(x.equip_id, -1) = COALESCE(ev.equip_id, -1)
        AND x.recorded_at = ev.recorded_at + s.delta
        AND x.title = ev.title
  );

WITH shifts(days, delta) AS (
    VALUES
      (-11, INTERVAL '-11 days'),
      (-5,  INTERVAL '-5 days')
)
INSERT INTO recheck_queue (
    lot_id, line_id, equip_id, defect_code, priority, severity, status, count_qty,
    cause_text, owner_employee_id, queued_at, completed_at, note, created_at
)
SELECT
    rq.lot_id,
    rq.line_id,
    rq.equip_id,
    rq.defect_code,
    rq.priority,
    rq.severity,
    rq.status,
    rq.count_qty,
    rq.cause_text,
    rq.owner_employee_id,
    rq.queued_at + s.delta,
    CASE WHEN rq.completed_at IS NULL THEN NULL ELSE rq.completed_at + s.delta END,
    rq.note,
    rq.created_at + s.delta
FROM recheck_queue rq
CROSS JOIN shifts s
WHERE (rq.queued_at AT TIME ZONE 'Asia/Seoul')::date BETWEEN DATE '2026-03-20' AND DATE '2026-03-25'
  AND ((rq.queued_at + s.delta) AT TIME ZONE 'Asia/Seoul')::date BETWEEN DATE '2026-03-09' AND DATE '2026-03-19'
  AND NOT EXISTS (
      SELECT 1
      FROM recheck_queue x
      WHERE x.line_id = rq.line_id
        AND COALESCE(x.equip_id, -1) = COALESCE(rq.equip_id, -1)
        AND x.lot_id = rq.lot_id
        AND x.defect_code = rq.defect_code
        AND x.queued_at = rq.queued_at + s.delta
  );

WITH shifts(days, delta, suffix) AS (
    VALUES
      (-11, INTERVAL '-11 days', '_B11'),
      (-5,  INTERVAL '-5 days',  '_B05')
)
INSERT INTO alarms (
    line_id, equip_id, alarm_code, alarm_name, cause_code, severity, message, status,
    occurred_at, cleared_at, created_at
)
SELECT
    a.line_id,
    a.equip_id,
    LEFT(a.alarm_code || s.suffix, 60),
    a.alarm_name,
    a.cause_code,
    a.severity,
    a.message,
    a.status,
    a.occurred_at + s.delta,
    CASE WHEN a.cleared_at IS NULL THEN NULL ELSE a.cleared_at + s.delta END,
    a.created_at + s.delta
FROM alarms a
CROSS JOIN shifts s
WHERE (a.occurred_at AT TIME ZONE 'Asia/Seoul')::date BETWEEN DATE '2026-03-20' AND DATE '2026-03-25'
  AND ((a.occurred_at + s.delta) AT TIME ZONE 'Asia/Seoul')::date BETWEEN DATE '2026-03-09' AND DATE '2026-03-19'
  AND NOT EXISTS (
      SELECT 1
      FROM alarms x
      WHERE x.line_id = a.line_id
        AND COALESCE(x.equip_id, -1) = COALESCE(a.equip_id, -1)
        AND x.occurred_at = a.occurred_at + s.delta
        AND x.message = a.message
  );

COMMIT;
