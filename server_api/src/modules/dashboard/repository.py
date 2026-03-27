"""dashboard 원천 데이터 조회 계층.

이 파일은 SQLAlchemy ORM보다 raw SQL에 가까운 방식으로 wed_dashboard 테이블을
조회해 화면 조합에 필요한 snapshot을 만든다. service.py는 이 결과를 받아
프론트 계약 형태로 가공한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import text

from src.lib.database import engine


TIMEZONE_NAME = "Asia/Seoul"
KST = timezone(timedelta(hours=9))
DAY_MINUTES = 24 * 60
DAILY_PLAN_TOTAL = 40000
LINE_PLAN_SHARE = {
    "LINE-A": 0.26,
    "LINE-B": 0.30,
    "LINE-C": 0.22,
    "LINE-D": 0.22,
}


# 공통 SQL 실행 유틸
def _fetch_all(stmt: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(text(stmt), params or {}).mappings().all()
    return [dict(row) for row in rows]


def _fetch_one(stmt: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    rows = _fetch_all(stmt, params)
    return rows[0] if rows else None


# service 계층으로 넘기는 스냅샷 구조
@dataclass
class DashboardLiveSnapshot:
    latest_date: date | None
    summary: dict[str, Any]
    top_defects: list[dict[str, Any]]
    defect_trend: list[dict[str, Any]]
    hourly_rollups: list[dict[str, Any]]
    minute10_rollups: list[dict[str, Any]]
    recent_ng_rows: list[dict[str, Any]]
    request_rollups: list[dict[str, Any]]
    low_conf_rows: list[dict[str, Any]]


@dataclass
class WebDashboardSnapshot:
    scenario_date: date
    effective_at: datetime
    total_produced: int
    month_produced: int
    total_good: int
    total_ng: int
    total_checked: int
    defect_rate: float
    recent_10m_ng: int
    active_alarm_count: int
    elapsed_minutes: int
    elapsed_ratio: float
    focus_line_code: str
    focus_line_name: str
    focus_line_output: int
    focus_line_good: int
    focus_line_ng: int
    focus_line_availability: float
    focus_line_performance: float
    focus_line_quality: float
    focus_line_oee: float
    focus_hourly_output: int
    top_defects: list[dict[str, Any]]
    active_alarms: list[dict[str, Any]]
    hourly_production: list[dict[str, Any]]
    line_production: list[dict[str, Any]]
    recheck_rows: list[dict[str, Any]]
    focus_ng_trend: list[dict[str, Any]]
    focus_equipment_status: list[dict[str, Any]]
    focus_line_environment: list[dict[str, Any]]
    focus_events: list[dict[str, Any]]
    global_events: list[dict[str, Any]]
    issue_rows: list[dict[str, Any]]
    daily_production: list[dict[str, Any]]


# web_dashboard 시간축/라인 선택 계산 유틸
def _dashboard_time_bounds(target_date: date | None = None) -> dict[str, Any]:
    now_local = datetime.now(KST).replace(second=0, microsecond=0)
    scenario_date = target_date or now_local.date()
    shift_start = datetime.combine(scenario_date, time.min, tzinfo=KST)
    shift_end = datetime.combine(scenario_date, time(23, 59, 59), tzinfo=KST)
    if scenario_date == now_local.date():
        effective_now = min(
            shift_end,
            datetime.combine(
                scenario_date,
                time(now_local.hour, now_local.minute, now_local.second),
                tzinfo=KST,
            ),
        )
    else:
        # 과거/미래 선택 날짜는 하루 전체 범위를 조회한다.
        effective_now = shift_end
    elapsed_minutes = max(1, min(DAY_MINUTES, int((effective_now - shift_start).total_seconds() // 60) + 1))
    return {
        "shift_start": shift_start,
        "month_start": datetime.combine(scenario_date.replace(day=1), time.min, tzinfo=KST),
        "effective_now": effective_now,
        "elapsed_minutes": elapsed_minutes,
        "elapsed_ratio": round(elapsed_minutes / DAY_MINUTES, 4),
        "kst_date": scenario_date,
    }


def _resolve_web_focus_line(
    requested_line: str | None,
    line_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    normalized = str(requested_line or "").strip().upper()
    if normalized:
        for row in line_rows:
            if normalized in {str(row.get("line_code") or "").upper(), str(row.get("line_name") or "").upper()}:
                return row, row.get("line_code")

    for row in line_rows:
        if str(row.get("line_code") or "").upper() == "LINE-C":
            return row, row.get("line_code")

    if line_rows:
        worst = sorted(
            line_rows,
            key=lambda item: (
                -float(item.get("risk_score") or 0),
                float(item.get("oee") or 0),
            ),
        )[0]
        return worst, worst.get("line_code")

    return None, None


# 생산 계획/리스크 계산 보조 함수
def _line_plan_total(line_code: str, elapsed_ratio: float) -> float:
    return DAILY_PLAN_TOTAL * LINE_PLAN_SHARE.get(line_code, 0.25) * max(elapsed_ratio, 0.01)


def _normalize_line_code(value: str | None) -> str | None:
    raw = str(value or "").strip().upper()
    if not raw:
        return None
    normalized = raw.replace("_", "-").replace(" ", "-")
    if normalized.startswith("LINE") and not normalized.startswith("LINE-"):
        normalized = normalized.replace("LINE", "LINE-", 1)
    return normalized


def _normalize_factory_name(value: str | None) -> str | None:
    raw = str(value or "").strip()
    return raw or None


def _normalize_work_shift(value: str | None) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    mapping = {
        "주간": "주간",
        "day": "주간",
        "d": "주간",
        "야간": "야간",
        "night": "야간",
        "n": "야간",
    }
    return mapping.get(raw, str(value).strip())


def _risk_score(
    *,
    availability_pct: float,
    quality_pct: float,
    performance_pct: float,
    active_alarms: int,
    latest_status: str,
) -> float:
    score = 0.0
    score += max(0.0, 95.0 - availability_pct) * 1.4
    score += max(0.0, 96.0 - quality_pct) * 1.6
    score += max(0.0, 92.0 - performance_pct) * 0.9
    score += active_alarms * 12.0
    if latest_status == "down":
        score += 24.0
    elif latest_status in {"maint", "idle"}:
        score += 10.0
    return round(min(score, 99.0), 2)


# 로그인 사용자 -> line_code 해석
def get_employee_line_code(employee_no: str) -> str | None:
    normalized = str(employee_no or "").strip()
    if not normalized:
        return None

    row = _fetch_one(
        """
        SELECT l.line_code
        FROM wed_dashboard.employees e
        JOIN wed_dashboard.lines l ON l.line_id = e.line_id
        WHERE e.employee_no = :employee_no
          AND e.is_active = TRUE
          AND l.is_active = TRUE
        LIMIT 1
        """,
        {"employee_no": normalized},
    )
    if row:
        line_code = str(row.get("line_code") or "").strip()
        if line_code:
            return line_code

    row = _fetch_one(
        """
        SELECT l.line_code
        FROM public.user_table u
        JOIN wed_dashboard.lines l ON l.line_id = u.line_id
        WHERE u.employee_no = :employee_no
          AND COALESCE(u.id_active, TRUE) = TRUE
          AND l.is_active = TRUE
        LIMIT 1
        """,
        {"employee_no": normalized},
    )
    if not row:
        return None

    line_code = str(row.get("line_code") or "").strip()
    return line_code or None


# 대시보드 원천 스냅샷 조회
def get_dashboard_live_snapshot() -> DashboardLiveSnapshot:
    latest = _fetch_one(
        """
        SELECT max(created_at) AS latest_date
        FROM vision_result
        """
    )
    latest_date = latest.get("latest_date") if latest else None

    if latest_date is None:
        return DashboardLiveSnapshot(
            latest_date=None,
            summary={},
            top_defects=[],
            defect_trend=[],
            hourly_rollups=[],
            minute10_rollups=[],
            recent_ng_rows=[],
            request_rollups=[],
            low_conf_rows=[],
        )

    summary = _fetch_one(
        """
        SELECT
          created_at,
          count(*) AS total_rows,
          count(*) FILTER (WHERE lower(coalesce(result_status::text, '')) = 'ng') AS ng_rows,
          count(*) FILTER (WHERE lower(coalesce(result_status::text, '')) = 'ok') AS ok_rows,
          count(DISTINCT request_id) AS request_count,
          round(avg(confidence)::numeric, 4) AS avg_confidence
        FROM vision_result
        WHERE created_at = :latest_date
        GROUP BY created_at
        """,
        {"latest_date": latest_date},
    ) or {}

    top_defects = _fetch_all(
        """
        SELECT
          lower(coalesce(vr.defect_type::text, 'unknown')) AS defect_type,
          coalesce(dt.class_name, lower(coalesce(vr.defect_type::text, 'unknown'))) AS class_name,
          coalesce(dt.desc, '') AS defect_desc,
          count(*) AS count,
          round(avg(vr.confidence)::numeric, 4) AS avg_confidence
        FROM vision_result vr
        LEFT JOIN defect_type dt ON lower(dt.class_name::text) = lower(vr.defect_type::text)
        WHERE vr.created_at = :latest_date
          AND lower(coalesce(vr.result_status::text, '')) = 'ng'
          AND coalesce(vr.defect_type::text, '') <> ''
        GROUP BY 1, 2, 3
        ORDER BY count(*) DESC, class_name ASC
        LIMIT 5
        """,
        {"latest_date": latest_date},
    )

    defect_trend = _fetch_all(
        """
        SELECT
          created_at,
          count(*) AS total_rows,
          count(*) FILTER (WHERE lower(coalesce(result_status::text, '')) = 'ng') AS ng_rows,
          count(DISTINCT request_id) AS request_count
        FROM vision_result
        GROUP BY created_at
        ORDER BY created_at ASC
        LIMIT 14
        """
    )

    hourly_rollups = _fetch_all(
        """
        WITH parsed AS (
          SELECT
            to_timestamp(substr(request_id, 1, 14), 'YYYYMMDDHH24MISS') AS event_ts,
            lower(coalesce(result_status::text, 'unknown')) AS result_status,
            coalesce(confidence, 0) AS confidence
          FROM vision_result
          WHERE created_at = :latest_date
            AND request_id ~ '^[0-9]{14,}'
        )
        SELECT
          to_char(date_trunc('hour', event_ts), 'YYYY-MM-DD HH24:00') AS bucket,
          count(*) AS total_rows,
          count(*) FILTER (WHERE result_status = 'ng') AS ng_rows,
          count(DISTINCT date_trunc('second', event_ts)) AS request_count,
          round(avg(confidence)::numeric, 4) AS avg_confidence
        FROM parsed
        GROUP BY date_trunc('hour', event_ts)
        ORDER BY date_trunc('hour', event_ts) ASC
        """
        ,
        {"latest_date": latest_date},
    )

    minute10_rollups = _fetch_all(
        """
        WITH parsed AS (
          SELECT
            to_timestamp(substr(request_id, 1, 14), 'YYYYMMDDHH24MISS') AS event_ts,
            lower(coalesce(result_status::text, 'unknown')) AS result_status
          FROM vision_result
          WHERE created_at = :latest_date
            AND request_id ~ '^[0-9]{14,}'
        )
        SELECT
          to_char(
            date_trunc('hour', event_ts)
            + make_interval(mins => ((extract(minute FROM event_ts)::int / 10) * 10)),
            'HH24:MI'
          ) AS bucket,
          count(*) FILTER (WHERE result_status = 'ng') AS ng_rows
        FROM parsed
        GROUP BY
          date_trunc('hour', event_ts)
          + make_interval(mins => ((extract(minute FROM event_ts)::int / 10) * 10))
        ORDER BY
          date_trunc('hour', event_ts)
          + make_interval(mins => ((extract(minute FROM event_ts)::int / 10) * 10)) ASC
        """
        ,
        {"latest_date": latest_date},
    )

    recent_ng_rows = _fetch_all(
        """
        SELECT
          request_id,
          image_path,
          lower(coalesce(defect_type::text, 'unknown')) AS defect_type,
          round(coalesce(confidence, 0)::numeric, 4) AS confidence,
          created_at,
          lower(coalesce(result_status::text, 'unknown')) AS result_status
        FROM vision_result
        WHERE created_at = :latest_date
          AND lower(coalesce(result_status::text, '')) = 'ng'
        ORDER BY created_at DESC, confidence ASC, request_id DESC
        LIMIT 20
        """,
        {"latest_date": latest_date},
    )

    request_rollups = _fetch_all(
        """
        SELECT
          request_id,
          created_at,
          count(*) AS total_rows,
          count(*) FILTER (WHERE lower(coalesce(result_status::text, '')) = 'ng') AS ng_rows,
          round(avg(coalesce(confidence, 0))::numeric, 4) AS avg_confidence,
          string_agg(DISTINCT lower(coalesce(defect_type::text, 'unknown')), ', ' ORDER BY lower(coalesce(defect_type::text, 'unknown'))) AS defect_types
        FROM vision_result
        WHERE created_at = :latest_date
        GROUP BY request_id, created_at
        ORDER BY ng_rows DESC, avg_confidence ASC, request_id DESC
        LIMIT 20
        """,
        {"latest_date": latest_date},
    )

    low_conf_rows = _fetch_all(
        """
        SELECT
          request_id,
          lower(coalesce(defect_type::text, 'unknown')) AS defect_type,
          round(coalesce(confidence, 0)::numeric, 4) AS confidence,
          created_at
        FROM vision_result
        WHERE created_at = :latest_date
          AND lower(coalesce(result_status::text, '')) = 'ng'
          AND coalesce(confidence, 0) < 0.90
        ORDER BY confidence ASC, request_id DESC
        LIMIT 30
        """,
        {"latest_date": latest_date},
    )

    return DashboardLiveSnapshot(
        latest_date=latest_date,
        summary=summary,
        top_defects=top_defects,
        defect_trend=defect_trend,
        hourly_rollups=hourly_rollups,
        minute10_rollups=minute10_rollups,
        recent_ng_rows=recent_ng_rows,
        request_rollups=request_rollups,
        low_conf_rows=low_conf_rows,
    )


def get_defect_detail(defect_type: str) -> dict[str, Any] | None:
    normalized = str(defect_type or "").strip().lower()
    if not normalized:
        return None

    summary = _fetch_all(
        """
        SELECT
          lower(coalesce(vr.defect_type::text, 'unknown')) AS defect_type,
          coalesce(dt.class_name, lower(coalesce(vr.defect_type::text, 'unknown'))) AS class_name,
          coalesce(dt.desc, '') AS defect_desc,
          count(*) AS occurrence_count,
          round(avg(coalesce(vr.confidence, 0))::numeric, 4) AS avg_confidence,
          min(vr.created_at) AS first_seen_at,
          max(vr.created_at) AS last_seen_at
        FROM vision_result vr
        LEFT JOIN defect_type dt ON lower(dt.class_name::text) = lower(vr.defect_type::text)
        WHERE lower(coalesce(vr.defect_type::text, '')) = :defect_type
        GROUP BY 1, 2, 3
        """,
        {"defect_type": normalized},
    )
    if not summary:
        return None

    logs = _fetch_all(
        """
        SELECT
          request_id,
          image_path,
          lower(coalesce(result_status::text, 'unknown')) AS result_status,
          lower(coalesce(defect_type::text, 'unknown')) AS defect_type,
          round(coalesce(confidence, 0)::numeric, 4) AS confidence,
          created_at
        FROM vision_result
        WHERE lower(coalesce(defect_type::text, '')) = :defect_type
        ORDER BY created_at DESC, confidence DESC, request_id DESC
        LIMIT 30
        """,
        {"defect_type": normalized},
    )
    related = _fetch_all(
        """
        SELECT
          request_id,
          created_at,
          count(*) AS row_count,
          round(avg(coalesce(confidence, 0))::numeric, 4) AS avg_confidence
        FROM vision_result
        WHERE lower(coalesce(defect_type, '')) = :defect_type
        GROUP BY request_id, created_at
        ORDER BY created_at DESC, row_count DESC
        LIMIT 20
        """,
        {"defect_type": normalized},
    )
    return {
        "summary": summary,
        "logs": logs,
        "relatedItems": related,
        "actions": [],
    }


def get_request_detail(request_id: str) -> dict[str, Any] | None:
    normalized = str(request_id or "").strip()
    if not normalized:
        return None

    summary = _fetch_all(
        """
        SELECT
          request_id,
          created_at,
          lower(coalesce(result_status::text, 'unknown')) AS result_status,
          lower(coalesce(defect_type::text, 'unknown')) AS defect_type,
          round(coalesce(confidence, 0)::numeric, 4) AS confidence,
          image_path
        FROM vision_result
        WHERE request_id = :request_id
        ORDER BY confidence DESC NULLS LAST, defect_type ASC
        LIMIT 30
        """,
        {"request_id": normalized},
    )
    if not summary:
        return None

    related = _fetch_all(
        """
        SELECT
          lower(coalesce(defect_type::text, 'unknown')) AS defect_type,
          count(*) AS occurrence_count,
          round(avg(coalesce(confidence, 0))::numeric, 4) AS avg_confidence
        FROM vision_result
        WHERE request_id = :request_id
        GROUP BY lower(coalesce(defect_type::text, 'unknown'))
        ORDER BY occurrence_count DESC, defect_type ASC
        """,
        {"request_id": normalized},
    )

    logs = _fetch_all(
        """
        SELECT
          request_id,
          created_at,
          lower(coalesce(result_status::text, 'unknown')) AS result_status,
          image_path
        FROM vision_result
        WHERE request_id = :request_id
        ORDER BY created_at DESC
        LIMIT 10
        """,
        {"request_id": normalized},
    )
    return {
        "summary": summary,
        "logs": logs,
        "relatedItems": related,
        "actions": [],
    }


def get_alarm_detail(alarm_id: str) -> dict[str, Any] | None:
    normalized = str(alarm_id or "").strip()
    if not normalized:
        return None

    summary = _fetch_all(
        """
        SELECT
          a.alarm_code AS alarm_id,
          COALESCE(a.alarm_name, '알람') AS alarm_name,
          a.severity,
          a.status,
          l.line_code,
          COALESCE(e.equip_code, '-') AS equip_code,
          COALESCE(a.message, '') AS message,
          COALESCE(a.cause_code, '') AS cause_code,
          to_char(a.occurred_at AT TIME ZONE :tz, 'YYYY-MM-DD HH24:MI') AS occurred_at
        FROM wed_dashboard.alarms a
        JOIN wed_dashboard.lines l ON l.line_id = a.line_id
        LEFT JOIN wed_dashboard.equipments e ON e.equip_id = a.equip_id
        WHERE a.alarm_code = :alarm_id
        ORDER BY a.occurred_at DESC, a.alarm_id DESC
        LIMIT 20
        """,
        {"alarm_id": normalized, "tz": TIMEZONE_NAME},
    )

    logs = _fetch_all(
        """
        SELECT
          COALESCE(aah.ack_status::text, '') AS action_type,
          COALESCE(aah.handled_by::text, '') AS actor_name,
          COALESCE(aah.note, '') AS memo,
          to_char(aah.handled_at AT TIME ZONE :tz, 'YYYY-MM-DD HH24:MI') AS created_at
        FROM wed_dashboard.alarm_ack_history aah
        JOIN wed_dashboard.alarms a ON a.alarm_id = aah.alarm_id_ref
        WHERE a.alarm_code = :alarm_id
        ORDER BY aah.handled_at DESC, aah.ack_id DESC
        LIMIT 20
        """,
        {"alarm_id": normalized, "tz": TIMEZONE_NAME},
    )

    related = _fetch_all(
        """
        SELECT
          COALESCE(ev.event_type, 'event') AS event_type,
          COALESCE(ev.severity, 'info') AS severity,
          COALESCE(ev.title, '') AS title,
          COALESCE(ev.message, '') AS message,
          COALESCE(ev.meta_text, '') AS meta_text,
          to_char(ev.recorded_at AT TIME ZONE :tz, 'YYYY-MM-DD HH24:MI') AS recorded_at
        FROM wed_dashboard.event_logs ev
        WHERE ev.meta_text = :alarm_id
        ORDER BY ev.recorded_at DESC, ev.event_id DESC
        LIMIT 20
        """,
        {"alarm_id": normalized, "tz": TIMEZONE_NAME},
    )

    if not summary and not logs and not related:
        return None

    return {
        "summary": summary,
        "logs": logs,
        "relatedItems": related,
        "actions": [],
    }


def get_lot_detail(lot_id: str) -> dict[str, Any] | None:
    normalized = str(lot_id or "").strip()
    if not normalized:
        return None

    summary = _fetch_all(
        """
        WITH lot_checks AS (
          SELECT
            ir.lot_id,
            SUM(ir.total_checked_qty) AS checked_qty,
            MAX(ir.recorded_at) AS latest_checked_at
          FROM wed_dashboard.inspection_results ir
          WHERE ir.lot_id::text = :lot_id
          GROUP BY ir.lot_id
        ),
        lot_defects AS (
          SELECT
            dr.lot_id,
            SUM(dr.defect_count) AS defect_qty,
            STRING_AGG(DISTINCT UPPER(COALESCE(dr.defect_code, 'UNKNOWN')), ' + ' ORDER BY UPPER(COALESCE(dr.defect_code, 'UNKNOWN'))) AS defect_mix,
            MAX(COALESCE(dr.cause_text, '')) AS cause_text,
            MAX(dr.recorded_at) AS latest_defect_at
          FROM wed_dashboard.defect_results dr
          WHERE dr.lot_id::text = :lot_id
          GROUP BY dr.lot_id
        )
        SELECT
          COALESCE(d.lot_id, c.lot_id) AS lot_id,
          COALESCE(c.checked_qty, 0) AS checked_qty,
          COALESCE(d.defect_qty, 0) AS defect_qty,
          ROUND(100.0 * COALESCE(d.defect_qty, 0) / NULLIF(COALESCE(c.checked_qty, 0), 0), 2) AS defect_rate,
          COALESCE(d.defect_mix, '-') AS defect_mix,
          COALESCE(d.cause_text, '') AS cause_text,
          to_char(COALESCE(d.latest_defect_at, c.latest_checked_at) AT TIME ZONE :tz, 'YYYY-MM-DD HH24:MI') AS latest_at
        FROM lot_defects d
        FULL OUTER JOIN lot_checks c ON c.lot_id = d.lot_id
        WHERE COALESCE(d.lot_id::text, c.lot_id::text) = :lot_id
        """,
        {"lot_id": normalized, "tz": TIMEZONE_NAME},
    )

    logs = _fetch_all(
        """
        SELECT
          rq.lot_id,
          UPPER(COALESCE(rq.defect_code, 'UNKNOWN')) AS defect_code,
          rq.priority,
          rq.severity,
          rq.status,
          rq.count_qty,
          COALESCE(rq.cause_text, '') AS cause_text,
          l.line_code,
          COALESCE(e.equip_code, '-') AS equip_code,
          to_char(rq.queued_at AT TIME ZONE :tz, 'YYYY-MM-DD HH24:MI') AS queued_at
        FROM wed_dashboard.recheck_queue rq
        JOIN wed_dashboard.lines l ON l.line_id = rq.line_id
        LEFT JOIN wed_dashboard.equipments e ON e.equip_id = rq.equip_id
        WHERE rq.lot_id::text = :lot_id
        ORDER BY rq.queued_at DESC, rq.recheck_id DESC
        LIMIT 20
        """,
        {"lot_id": normalized, "tz": TIMEZONE_NAME},
    )

    related = _fetch_all(
        """
        SELECT
          ir.lot_id,
          l.line_code,
          COALESCE(e.equip_code, '-') AS equip_code,
          ir.total_checked_qty,
          ir.pass_qty,
          ir.fail_qty,
          to_char(ir.recorded_at AT TIME ZONE :tz, 'YYYY-MM-DD HH24:MI') AS recorded_at
        FROM wed_dashboard.inspection_results ir
        JOIN wed_dashboard.lines l ON l.line_id = ir.line_id
        LEFT JOIN wed_dashboard.equipments e ON e.equip_id = ir.equip_id
        WHERE ir.lot_id::text = :lot_id
        ORDER BY ir.recorded_at DESC, ir.inspection_id DESC
        LIMIT 20
        """,
        {"lot_id": normalized, "tz": TIMEZONE_NAME},
    )

    if not summary and not logs and not related:
        return None

    return {
        "summary": summary,
        "logs": logs,
        "relatedItems": related,
        "actions": [],
    }


def get_web_dashboard_snapshot(
    line_code: str | None = None,
    target_date: date | None = None,
    factory: str | None = None,
    shift: str | None = None,
) -> WebDashboardSnapshot:
    bounds = _dashboard_time_bounds(target_date)
    normalized_line_code = _normalize_line_code(line_code)
    normalized_factory = _normalize_factory_name(factory)
    normalized_shift = _normalize_work_shift(shift)
    params = {
        "shift_start": bounds["shift_start"],
        "month_start": bounds["month_start"],
        "effective_now": bounds["effective_now"],
        "tz": TIMEZONE_NAME,
        "kst_date": bounds["kst_date"],
        "week_start": bounds["kst_date"] - timedelta(days=6) if bounds.get("kst_date") else None,
        "line_code": normalized_line_code,
        "factory_name": normalized_factory,
        "work_shift": normalized_shift,
    }

    totals = _fetch_one(
        """
        SELECT
          COALESCE(SUM(produced_qty), 0) AS total_produced,
          COALESCE(SUM(good_qty), 0) AS total_good,
          COALESCE(SUM(ng_qty), 0) AS total_ng
        FROM wed_dashboard.production_records pr
        JOIN wed_dashboard.lines l ON l.line_id = pr.line_id
        JOIN wed_dashboard.factories f ON f.factory_id = l.factory_id
        WHERE recorded_at >= :shift_start
          AND recorded_at <= :effective_now
          AND (CAST(:line_code AS text) IS NULL OR UPPER(l.line_code) = CAST(:line_code AS text))
          AND (CAST(:factory_name AS text) IS NULL OR f.factory_name = CAST(:factory_name AS text))
          AND (CAST(:work_shift AS text) IS NULL OR pr.work_shift = CAST(:work_shift AS text))
        """,
        params,
    ) or {}
    total_produced = int(totals.get("total_produced") or 0)
    total_good = int(totals.get("total_good") or 0)
    total_ng = int(totals.get("total_ng") or 0)
    defect_rate = round((total_ng / total_produced) * 100, 2) if total_produced > 0 else 0.0

    month_totals = _fetch_one(
        """
        SELECT
          COALESCE(SUM(produced_qty), 0) AS month_produced
        FROM wed_dashboard.production_records pr
        JOIN wed_dashboard.lines l ON l.line_id = pr.line_id
        JOIN wed_dashboard.factories f ON f.factory_id = l.factory_id
        WHERE recorded_at >= :month_start
          AND recorded_at <= :effective_now
          AND (CAST(:line_code AS text) IS NULL OR UPPER(l.line_code) = CAST(:line_code AS text))
          AND (CAST(:factory_name AS text) IS NULL OR f.factory_name = CAST(:factory_name AS text))
          AND (CAST(:work_shift AS text) IS NULL OR pr.work_shift = CAST(:work_shift AS text))
        """,
        params,
    ) or {}
    month_produced = int(month_totals.get("month_produced") or 0)

    checked_row = _fetch_one(
        """
        SELECT COALESCE(SUM(total_checked_qty), 0) AS total_checked
        FROM wed_dashboard.inspection_results ir
        JOIN wed_dashboard.lines l ON l.line_id = ir.line_id
        JOIN wed_dashboard.factories f ON f.factory_id = l.factory_id
        WHERE recorded_at >= :shift_start
          AND recorded_at <= :effective_now
          AND (CAST(:line_code AS text) IS NULL OR UPPER(l.line_code) = CAST(:line_code AS text))
          AND (CAST(:factory_name AS text) IS NULL OR f.factory_name = CAST(:factory_name AS text))
        """,
        params,
    ) or {}
    total_checked = int(checked_row.get("total_checked") or 0)

    active_alarm_count_row = _fetch_one(
        """
        SELECT COUNT(*) AS cnt
        FROM wed_dashboard.alarms a
        JOIN wed_dashboard.lines l ON l.line_id = a.line_id
        JOIN wed_dashboard.factories f ON f.factory_id = l.factory_id
        WHERE a.status IN ('active', 'hold')
          AND a.occurred_at >= :shift_start
          AND a.occurred_at <= :effective_now
          AND (CAST(:line_code AS text) IS NULL OR UPPER(l.line_code) = CAST(:line_code AS text))
          AND (CAST(:factory_name AS text) IS NULL OR f.factory_name = CAST(:factory_name AS text))
        """,
        params,
    ) or {}
    active_alarm_count = int(active_alarm_count_row.get("cnt") or 0)

    top_defects = _fetch_all(
        """
        SELECT
          lower(COALESCE(defect_code, 'unknown')) AS defect_code,
          COALESCE(defect_name, lower(COALESCE(defect_code, 'unknown'))) AS defect_name,
          SUM(defect_count) AS cnt
        FROM wed_dashboard.defect_results dr
        JOIN wed_dashboard.lines l ON l.line_id = dr.line_id
        JOIN wed_dashboard.factories f ON f.factory_id = l.factory_id
        WHERE recorded_at >= :shift_start
          AND recorded_at <= :effective_now
          AND (CAST(:line_code AS text) IS NULL OR UPPER(l.line_code) = CAST(:line_code AS text))
          AND (CAST(:factory_name AS text) IS NULL OR f.factory_name = CAST(:factory_name AS text))
        GROUP BY 1, 2
        ORDER BY cnt DESC
        LIMIT 6
        """,
        params,
    )

    active_alarms = _fetch_all(
        """
        SELECT
          a.alarm_code,
          a.severity,
          a.status,
          a.message,
          a.cause_code,
          a.line_id,
          a.equip_id,
          l.line_code,
          l.line_name,
          COALESCE(e.equip_code, '-') AS equip_code,
          COALESCE(e.equip_name, '-') AS equip_name,
          COALESCE(ack.ack_status, CASE WHEN a.status = 'active' THEN 'unack' ELSE 'hold' END) AS ack_status,
          FLOOR(EXTRACT(EPOCH FROM (:effective_now - a.occurred_at)) / 60)::int AS elapsed_min,
          to_char(a.occurred_at AT TIME ZONE :tz, 'HH24:MI') AS occurred_at
        FROM wed_dashboard.alarms a
        JOIN wed_dashboard.lines l ON l.line_id = a.line_id
        JOIN wed_dashboard.factories f ON f.factory_id = l.factory_id
        LEFT JOIN wed_dashboard.equipments e ON e.equip_id = a.equip_id
        LEFT JOIN LATERAL (
          SELECT ack_status
          FROM wed_dashboard.alarm_ack_history h
          WHERE h.alarm_id_ref = a.alarm_id
          ORDER BY h.handled_at DESC, h.ack_id DESC
          LIMIT 1
        ) ack ON TRUE
        WHERE a.status IN ('active', 'hold')
          AND a.occurred_at >= :shift_start
          AND a.occurred_at <= :effective_now
          AND (CAST(:line_code AS text) IS NULL OR UPPER(l.line_code) = CAST(:line_code AS text))
          AND (CAST(:factory_name AS text) IS NULL OR f.factory_name = CAST(:factory_name AS text))
        ORDER BY
          CASE a.severity WHEN 'critical' THEN 1 WHEN 'warning' THEN 2 WHEN 'info' THEN 3 ELSE 4 END,
          a.occurred_at DESC
        LIMIT 40
        """,
        params,
    )

    hourly_production = _fetch_all(
        """
        SELECT
          to_char(date_trunc('hour', recorded_at AT TIME ZONE :tz), 'HH24:00') AS bucket,
          COALESCE(SUM(produced_qty), 0) AS produced,
          COALESCE(SUM(ng_qty), 0) AS ng_qty
        FROM wed_dashboard.production_records pr
        JOIN wed_dashboard.lines l ON l.line_id = pr.line_id
        JOIN wed_dashboard.factories f ON f.factory_id = l.factory_id
        WHERE recorded_at >= :shift_start
          AND recorded_at <= :effective_now
          AND (CAST(:line_code AS text) IS NULL OR UPPER(l.line_code) = CAST(:line_code AS text))
          AND (CAST(:factory_name AS text) IS NULL OR f.factory_name = CAST(:factory_name AS text))
          AND (CAST(:work_shift AS text) IS NULL OR pr.work_shift = CAST(:work_shift AS text))
        GROUP BY date_trunc('hour', recorded_at AT TIME ZONE :tz)
        ORDER BY date_trunc('hour', recorded_at AT TIME ZONE :tz) ASC
        """,
        params,
    )

    raw_line_rows = _fetch_all(
        """
        SELECT
          l.line_id,
          l.line_code,
          l.line_name,
          COALESCE(prod.produced, 0) AS produced,
          COALESCE(prod.good, 0) AS good,
          COALESCE(prod.ng, 0) AS ng,
          COALESCE(ins.total_checked, 0) AS total_checked,
          COALESCE(stat.availability_pct, 0) AS availability_pct,
          COALESCE(latest.status_code, 'idle') AS latest_status,
          COALESCE(latest.reason_text, '') AS latest_reason,
          COALESCE(alarm.active_alarm_count, 0) AS active_alarm_count,
          COALESCE(active_down.has_down, FALSE) AS has_down
        FROM wed_dashboard.lines l
        JOIN wed_dashboard.factories f ON f.factory_id = l.factory_id
        LEFT JOIN (
          SELECT
            line_id,
            SUM(produced_qty) AS produced,
            SUM(good_qty) AS good,
            SUM(ng_qty) AS ng
          FROM wed_dashboard.production_records
          WHERE recorded_at >= :shift_start
            AND recorded_at <= :effective_now
            AND (CAST(:work_shift AS text) IS NULL OR work_shift = CAST(:work_shift AS text))
          GROUP BY line_id
        ) prod ON prod.line_id = l.line_id
        LEFT JOIN (
          SELECT
            line_id,
            SUM(total_checked_qty) AS total_checked
          FROM wed_dashboard.inspection_results
          WHERE recorded_at >= :shift_start
            AND recorded_at <= :effective_now
          GROUP BY line_id
        ) ins ON ins.line_id = l.line_id
        LEFT JOIN (
          SELECT
            line_id,
            ROUND(
              100.0 * SUM(CASE WHEN status_code = 'run' THEN COALESCE(duration_sec, 0) ELSE 0 END)
              / NULLIF(SUM(COALESCE(duration_sec, 0)), 0),
              2
            ) AS availability_pct
          FROM wed_dashboard.equipment_status_history
          WHERE started_at >= :shift_start
            AND started_at <= :effective_now
          GROUP BY line_id
        ) stat ON stat.line_id = l.line_id
        LEFT JOIN (
          SELECT DISTINCT ON (line_id)
            line_id,
            status_code,
            reason_text,
            started_at
          FROM wed_dashboard.equipment_status_history
          WHERE started_at >= :shift_start
            AND started_at <= :effective_now
          ORDER BY line_id, started_at DESC, status_id DESC
        ) latest ON latest.line_id = l.line_id
        LEFT JOIN (
          SELECT
            line_id,
            COUNT(*) AS active_alarm_count
          FROM wed_dashboard.alarms
          WHERE status IN ('active', 'hold')
            AND occurred_at >= :shift_start
            AND occurred_at <= :effective_now
          GROUP BY line_id
        ) alarm ON alarm.line_id = l.line_id
        LEFT JOIN (
          SELECT
            line_id,
            BOOL_OR(status_code = 'down') AS has_down
          FROM wed_dashboard.equipment_status_history
          WHERE started_at >= :shift_start
            AND started_at <= :effective_now
          GROUP BY line_id
        ) active_down ON active_down.line_id = l.line_id
        WHERE l.is_active = TRUE
          AND (CAST(:line_code AS text) IS NULL OR UPPER(l.line_code) = CAST(:line_code AS text))
          AND (CAST(:factory_name AS text) IS NULL OR f.factory_name = CAST(:factory_name AS text))
        ORDER BY l.sort_order ASC, l.line_code ASC
        """,
        params,
    )

    line_production: list[dict[str, Any]] = []
    for row in raw_line_rows:
        line_code_value = str(row.get("line_code") or "")
        produced = int(row.get("produced") or 0)
        good = int(row.get("good") or 0)
        ng = int(row.get("ng") or 0)
        checked = int(row.get("total_checked") or 0)
        availability_pct = max(0.0, min(round(float(row.get("availability_pct") or 0), 2), 100.0))
        quality_pct = max(0.0, min(round((good / produced) * 100, 2), 100.0)) if produced > 0 else 0.0
        plan_to_now = _line_plan_total(line_code_value, bounds["elapsed_ratio"])
        performance_pct = max(0.0, min(round((produced / plan_to_now) * 100, 2), 100.0)) if plan_to_now > 0 else 0.0
        oee = max(0.0, min(round((availability_pct / 100.0) * (performance_pct / 100.0) * (quality_pct / 100.0) * 100.0, 2), 100.0))
        latest_status = "down" if row.get("has_down") else str(row.get("latest_status") or "idle").lower()
        line_row = dict(row)
        line_row.update(
            {
                "produced": produced,
                "good": good,
                "ng": ng,
                "total_checked": checked,
                "availability_pct": availability_pct,
                "quality_pct": quality_pct,
                "performance_pct": performance_pct,
                "latest_status": latest_status,
                "oee": oee,
                "risk_score": _risk_score(
                    availability_pct=availability_pct,
                    quality_pct=quality_pct,
                    performance_pct=performance_pct,
                    active_alarms=int(row.get("active_alarm_count") or 0),
                    latest_status=latest_status,
                ),
            }
        )
        line_production.append(line_row)

    focus_line, focus_line_code = _resolve_web_focus_line(line_code, line_production)
    focus_line_code = focus_line_code or "LINE-C"
    focus_line_name = str(focus_line.get("line_name") or focus_line_code) if focus_line else focus_line_code
    focus_line_id = int(focus_line.get("line_id") or 0) if focus_line else 0

    focus_hourly_row = _fetch_one(
        """
        SELECT
          COALESCE(SUM(pr.produced_qty), 0) AS produced
        FROM wed_dashboard.production_records pr
        JOIN wed_dashboard.lines l ON l.line_id = pr.line_id
        WHERE l.line_code = :line_code
          AND pr.recorded_at >= :shift_start
          AND pr.recorded_at <= :effective_now
          AND (CAST(:work_shift AS text) IS NULL OR pr.work_shift = CAST(:work_shift AS text))
          AND date_trunc('hour', pr.recorded_at AT TIME ZONE :tz) = (
            SELECT MAX(date_trunc('hour', pr2.recorded_at AT TIME ZONE :tz))
            FROM wed_dashboard.production_records pr2
            JOIN wed_dashboard.lines l2 ON l2.line_id = pr2.line_id
            WHERE l2.line_code = :line_code
              AND pr2.recorded_at >= :shift_start
              AND pr2.recorded_at <= :effective_now
              AND (CAST(:work_shift AS text) IS NULL OR pr2.work_shift = CAST(:work_shift AS text))
          )
        """,
        {**params, "line_code": focus_line_code},
    ) or {}
    focus_hourly_output = int(focus_hourly_row.get("produced") or 0)

    recheck_rows = _fetch_all(
        """
        SELECT
          rq.lot_id,
          rq.defect_code,
          rq.priority,
          rq.severity,
          rq.status,
          rq.count_qty,
          rq.cause_text,
          l.line_code,
          COALESCE(e.equip_code, '-') AS equip_code,
          to_char(rq.queued_at AT TIME ZONE :tz, 'HH24:MI') AS queued_at
        FROM wed_dashboard.recheck_queue rq
        JOIN wed_dashboard.lines l ON l.line_id = rq.line_id
        JOIN wed_dashboard.factories f ON f.factory_id = l.factory_id
        LEFT JOIN wed_dashboard.equipments e ON e.equip_id = rq.equip_id
        WHERE status IN ('queued', 'in_progress', 'hold')
          AND (CAST(:line_code AS text) IS NULL OR UPPER(l.line_code) = CAST(:line_code AS text))
          AND (CAST(:factory_name AS text) IS NULL OR f.factory_name = CAST(:factory_name AS text))
        ORDER BY
          rq.queued_at DESC,
          CASE rq.priority WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END
        LIMIT 40
        """,
        params,
    )

    focus_ng_trend = _fetch_all(
        """
        SELECT
          to_char(bucket_local, 'HH24:MI') AS bucket,
          COALESCE(SUM(bucket_ng), 0) AS ng_qty
        FROM (
          SELECT
            date_trunc('hour', dr.recorded_at AT TIME ZONE :tz)
            + make_interval(mins => ((extract(minute FROM dr.recorded_at AT TIME ZONE :tz)::int / 10) * 10)) AS bucket_local,
            dr.defect_count AS bucket_ng
          FROM wed_dashboard.defect_results dr
          JOIN wed_dashboard.lines l ON l.line_id = dr.line_id
          WHERE l.line_code = :line_code
            AND dr.recorded_at >= :shift_start
            AND dr.recorded_at <= :effective_now
        ) buckets
        GROUP BY bucket_local
        ORDER BY bucket_local ASC
        """,
        {**params, "line_code": focus_line_code},
    )
    recent_10m_ng = int(focus_ng_trend[-1].get("ng_qty") or 0) if focus_ng_trend else 0

    focus_equipment_status = _fetch_all(
        """
        SELECT
          e.equip_code,
          e.equip_name,
          e.equip_type,
          COALESCE(latest.status_code, 'idle') AS status_code,
          COALESCE(latest.reason_text, '') AS reason_text,
          COALESCE(av.availability_pct, 0) AS availability_pct,
          COALESCE(defs.ng_qty, 0) AS ng_qty,
          to_char(COALESCE(latest.started_at, :effective_now) AT TIME ZONE :tz, 'HH24:MI') AS updated_at
        FROM wed_dashboard.equipments e
        JOIN wed_dashboard.lines l ON l.line_id = e.line_id
        LEFT JOIN (
          SELECT
            equip_id,
            ROUND(
              100.0 * SUM(CASE WHEN status_code = 'run' THEN COALESCE(duration_sec, 0) ELSE 0 END)
              / NULLIF(SUM(COALESCE(duration_sec, 0)), 0),
              2
            ) AS availability_pct
          FROM wed_dashboard.equipment_status_history
          WHERE started_at >= :shift_start
            AND started_at <= :effective_now
          GROUP BY equip_id
        ) av ON av.equip_id = e.equip_id
        LEFT JOIN (
          SELECT DISTINCT ON (equip_id)
            equip_id,
            status_code,
            reason_text,
            started_at
          FROM wed_dashboard.equipment_status_history
          WHERE started_at >= :shift_start
            AND started_at <= :effective_now
          ORDER BY equip_id, started_at DESC, status_id DESC
        ) latest ON latest.equip_id = e.equip_id
        LEFT JOIN (
          SELECT equip_id, SUM(defect_count) AS ng_qty
          FROM wed_dashboard.defect_results
          WHERE recorded_at >= :shift_start
            AND recorded_at <= :effective_now
          GROUP BY equip_id
        ) defs ON defs.equip_id = e.equip_id
        WHERE l.line_code = :line_code
          AND e.is_active = TRUE
        ORDER BY e.equip_code ASC
        """,
        {**params, "line_code": focus_line_code},
    )

    focus_line_environment = _fetch_all(
        """
        SELECT
          sensor_type,
          metric_name,
          metric_value,
          unit,
          to_char(recorded_at AT TIME ZONE :tz, 'HH24:MI') AS recorded_at
        FROM (
          SELECT DISTINCT ON (sensor_type)
            sensor_type,
            metric_name,
            metric_value,
            unit,
            recorded_at
          FROM wed_dashboard.line_environment
          WHERE line_id = :line_id
            AND recorded_at >= :shift_start
            AND recorded_at <= :effective_now
          ORDER BY sensor_type, recorded_at DESC, env_id DESC
        ) env
        ORDER BY sensor_type ASC
        """,
        {**params, "line_id": focus_line_id},
    )

    if not focus_line_environment and focus_line_id:
        # 시연/더미 데이터가 현재 조회 시점보다 미래일 수 있어,
        # 기간 필터에 걸리지 않으면 해당 라인의 최신 환경값으로 한 번 더 보완한다.
        focus_line_environment = _fetch_all(
            """
            SELECT
              sensor_type,
              metric_name,
              metric_value,
              unit,
              to_char(recorded_at AT TIME ZONE :tz, 'HH24:MI') AS recorded_at
            FROM (
              SELECT DISTINCT ON (sensor_type)
                sensor_type,
                metric_name,
                metric_value,
                unit,
                recorded_at,
                env_id
              FROM wed_dashboard.line_environment
              WHERE line_id = :line_id
              ORDER BY sensor_type, recorded_at DESC, env_id DESC
            ) env
            ORDER BY sensor_type ASC
            """,
            {**params, "line_id": focus_line_id},
        )

    focus_events = _fetch_all(
        """
        SELECT
          source_type,
          severity,
          COALESCE(line_code, :line_code) AS line_code,
          COALESCE(equip_code, '-') AS equip_code,
          title,
          message,
          meta_text,
          to_char(event_at AT TIME ZONE :tz, 'HH24:MI') AS event_time
        FROM (
          SELECT
            'alarm' AS source_type,
            a.severity,
            l.line_code,
            e.equip_code,
            COALESCE(a.alarm_name, '알람') AS title,
            a.message,
            a.alarm_code AS meta_text,
            a.occurred_at AS event_at
          FROM wed_dashboard.alarms a
          JOIN wed_dashboard.lines l ON l.line_id = a.line_id
          LEFT JOIN wed_dashboard.equipments e ON e.equip_id = a.equip_id
          WHERE l.line_code = :line_code
            AND a.status IN ('active', 'hold')
            AND a.occurred_at >= :shift_start
            AND a.occurred_at <= :effective_now
          UNION ALL
          SELECT
            ev.event_type AS source_type,
            COALESCE(ev.severity, 'info') AS severity,
            l.line_code,
            e.equip_code,
            ev.title,
            ev.message,
            ev.meta_text,
            ev.recorded_at AS event_at
          FROM wed_dashboard.event_logs ev
          JOIN wed_dashboard.lines l ON l.line_id = ev.line_id
          LEFT JOIN wed_dashboard.equipments e ON e.equip_id = ev.equip_id
          WHERE l.line_code = :line_code
            AND ev.recorded_at >= :shift_start
            AND ev.recorded_at <= :effective_now
          UNION ALL
          SELECT
            'recheck' AS source_type,
            rq.severity,
            l.line_code,
            e.equip_code,
            '재검 요청' AS title,
            rq.cause_text AS message,
            rq.lot_id AS meta_text,
            rq.queued_at AS event_at
          FROM wed_dashboard.recheck_queue rq
          JOIN wed_dashboard.lines l ON l.line_id = rq.line_id
          LEFT JOIN wed_dashboard.equipments e ON e.equip_id = rq.equip_id
          WHERE l.line_code = :line_code
            AND rq.status IN ('queued', 'in_progress', 'hold')
        ) timeline
        ORDER BY event_at DESC
        LIMIT 8
        """,
        {**params, "line_code": focus_line_code},
    )

    global_events = _fetch_all(
        """
        SELECT
          source_type,
          severity,
          line_code,
          COALESCE(equip_code, '-') AS equip_code,
          title,
          message,
          meta_text,
          to_char(event_at AT TIME ZONE :tz, 'HH24:MI') AS event_time
        FROM (
          SELECT
            'alarm' AS source_type,
            a.severity,
            l.line_code,
            e.equip_code,
            COALESCE(a.alarm_name, '알람') AS title,
            a.message,
            a.alarm_code AS meta_text,
            a.occurred_at AS event_at
          FROM wed_dashboard.alarms a
          JOIN wed_dashboard.lines l ON l.line_id = a.line_id
          JOIN wed_dashboard.factories f ON f.factory_id = l.factory_id
          LEFT JOIN wed_dashboard.equipments e ON e.equip_id = a.equip_id
          WHERE a.status IN ('active', 'hold')
            AND a.occurred_at >= :shift_start
            AND a.occurred_at <= :effective_now
            AND (CAST(:factory_name AS text) IS NULL OR f.factory_name = CAST(:factory_name AS text))
          UNION ALL
          SELECT
            COALESCE(ev.event_type, 'event') AS source_type,
            COALESCE(ev.severity, 'info') AS severity,
            l.line_code,
            e.equip_code,
            ev.title,
            ev.message,
            ev.meta_text,
            ev.recorded_at AS event_at
          FROM wed_dashboard.event_logs ev
          JOIN wed_dashboard.lines l ON l.line_id = ev.line_id
          JOIN wed_dashboard.factories f ON f.factory_id = l.factory_id
          LEFT JOIN wed_dashboard.equipments e ON e.equip_id = ev.equip_id
          WHERE ev.recorded_at >= :shift_start
            AND ev.recorded_at <= :effective_now
            AND (CAST(:factory_name AS text) IS NULL OR f.factory_name = CAST(:factory_name AS text))
        ) timeline
        WHERE line_code IS NOT NULL
        ORDER BY event_at DESC
        LIMIT 40
        """,
        {**params, "line_code": focus_line_code},
    )

    issue_rows = _fetch_all(
        """
        WITH lot_checks AS (
          SELECT ir.lot_id, SUM(ir.total_checked_qty) AS checked_qty
          FROM wed_dashboard.inspection_results ir
          JOIN wed_dashboard.lines l ON l.line_id = ir.line_id
          JOIN wed_dashboard.factories f ON f.factory_id = l.factory_id
          WHERE recorded_at >= :shift_start
            AND recorded_at <= :effective_now
            AND (CAST(:line_code AS text) IS NULL OR UPPER(l.line_code) = CAST(:line_code AS text))
            AND (CAST(:factory_name AS text) IS NULL OR f.factory_name = CAST(:factory_name AS text))
          GROUP BY ir.lot_id
        ),
        lot_defect_breakdown AS (
          SELECT
            dr.lot_id,
            l.line_code,
            COALESCE(e.equip_code, '-') AS equip_code,
            UPPER(COALESCE(dr.defect_code, 'UNKNOWN')) AS defect_code,
            SUM(dr.defect_count) AS defect_count,
            MAX(dr.cause_text) AS cause_text,
            MAX(dr.recorded_at) AS latest_at
          FROM wed_dashboard.defect_results dr
          JOIN wed_dashboard.lines l ON l.line_id = dr.line_id
          JOIN wed_dashboard.factories f ON f.factory_id = l.factory_id
          LEFT JOIN wed_dashboard.equipments e ON e.equip_id = dr.equip_id
          WHERE dr.recorded_at >= :shift_start
            AND dr.recorded_at <= :effective_now
            AND (CAST(:line_code AS text) IS NULL OR UPPER(l.line_code) = CAST(:line_code AS text))
            AND (CAST(:factory_name AS text) IS NULL OR f.factory_name = CAST(:factory_name AS text))
          GROUP BY dr.lot_id, l.line_code, e.equip_code, UPPER(COALESCE(dr.defect_code, 'UNKNOWN'))
        ),
        lot_primary_defect AS (
          SELECT
            lot_id,
            line_code,
            equip_code,
            defect_code,
            defect_count,
            cause_text,
            latest_at,
            ROW_NUMBER() OVER (
              PARTITION BY lot_id, line_code, equip_code
              ORDER BY defect_count DESC, defect_code ASC
            ) AS rn
          FROM lot_defect_breakdown
        ),
        lot_defects AS (
          SELECT
            b.lot_id,
            b.line_code,
            b.equip_code,
            SUM(b.defect_count) AS defect_qty,
            STRING_AGG(DISTINCT b.defect_code, ' + ' ORDER BY b.defect_code) AS defect_mix,
            MAX(b.latest_at) AS latest_at,
            MAX(CASE WHEN p.rn = 1 THEN p.defect_code END) AS primary_defect,
            MAX(CASE WHEN p.rn = 1 THEN p.cause_text END) AS primary_cause
          FROM lot_defect_breakdown b
          LEFT JOIN lot_primary_defect p
            ON p.lot_id = b.lot_id
           AND p.line_code = b.line_code
           AND p.equip_code = b.equip_code
          GROUP BY b.lot_id, b.line_code, b.equip_code
        )
        SELECT
          d.lot_id,
          d.line_code,
          d.equip_code,
          d.defect_qty,
          COALESCE(c.checked_qty, 0) AS checked_qty,
          ROUND(100.0 * d.defect_qty / NULLIF(c.checked_qty, 0), 2) AS defect_rate,
          d.defect_mix,
          d.primary_defect,
          COALESCE(d.primary_cause, '') AS cause_text,
          to_char(d.latest_at AT TIME ZONE :tz, 'HH24:MI') AS latest_at
        FROM lot_defects d
        LEFT JOIN lot_checks c ON c.lot_id = d.lot_id
        WHERE d.defect_qty > 0
        ORDER BY
          ROUND(100.0 * d.defect_qty / NULLIF(c.checked_qty, 0), 2) DESC NULLS LAST,
          d.defect_qty DESC,
          d.latest_at DESC
        LIMIT 6
        """,
        params,
    )


    daily_production = _fetch_all(
        """
        SELECT
          work_date,
          COALESCE(SUM(produced_qty), 0) AS produced,
          COALESCE(SUM(good_qty), 0) AS good,
          COALESCE(SUM(ng_qty), 0) AS ng
        FROM wed_dashboard.production_records pr
        JOIN wed_dashboard.lines l ON l.line_id = pr.line_id
        JOIN wed_dashboard.factories f ON f.factory_id = l.factory_id
        WHERE work_date >= :week_start
          AND work_date <= :kst_date
          AND (CAST(:line_code AS text) IS NULL OR UPPER(l.line_code) = CAST(:line_code AS text))
          AND (CAST(:factory_name AS text) IS NULL OR f.factory_name = CAST(:factory_name AS text))
          AND (CAST(:work_shift AS text) IS NULL OR pr.work_shift = CAST(:work_shift AS text))
        GROUP BY work_date
        ORDER BY work_date ASC
        """,
        params,
    )

    return WebDashboardSnapshot(
        scenario_date=bounds["kst_date"],
        effective_at=bounds["effective_now"],
        total_produced=total_produced,
        month_produced=month_produced,
        total_good=total_good,
        total_ng=total_ng,
        total_checked=total_checked,
        defect_rate=defect_rate,
        recent_10m_ng=recent_10m_ng,
        active_alarm_count=active_alarm_count,
        elapsed_minutes=int(bounds["elapsed_minutes"]),
        elapsed_ratio=float(bounds["elapsed_ratio"]),
        focus_line_code=focus_line_code,
        focus_line_name=focus_line_name,
        focus_line_output=int(focus_line.get("produced") or 0) if focus_line else 0,
        focus_line_good=int(focus_line.get("good") or 0) if focus_line else 0,
        focus_line_ng=int(focus_line.get("ng") or 0) if focus_line else 0,
        focus_line_availability=float(focus_line.get("availability_pct") or 0) if focus_line else 0.0,
        focus_line_performance=float(focus_line.get("performance_pct") or 0) if focus_line else 0.0,
        focus_line_quality=float(focus_line.get("quality_pct") or 0) if focus_line else 0.0,
        focus_line_oee=float(focus_line.get("oee") or 0) if focus_line else 0.0,
        focus_hourly_output=focus_hourly_output,
        top_defects=top_defects,
        active_alarms=active_alarms,
        hourly_production=hourly_production,
        line_production=line_production,
        recheck_rows=recheck_rows,
        focus_ng_trend=focus_ng_trend,
        focus_equipment_status=focus_equipment_status,
        focus_line_environment=focus_line_environment,
        focus_events=focus_events,
        global_events=global_events,
        issue_rows=issue_rows,
        daily_production=daily_production,
    )
