#!/usr/bin/env python3
from __future__ import annotations

import argparse
import random
import time as time_module
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import psycopg

from src.scripts.generate_wed_dashboard_dummy import (
    DEFECT_DEFS,
    EQUIPMENTS,
    FACTORIES,
    KST,
    LINE_PLAN_SHARE,
    LINES,
    MODEL_CODES,
    PRIMARY_EQUIPMENT,
    ensure_master_data,
    get_database_url,
    insert_fact_rows,
    psycopg_conninfo,
)

DEFAULT_INTERVAL_SEC = 60
DEFAULT_DAILY_TARGET = 15000
DEFAULT_BASE_DEFECT_MIN = 0.05
DEFAULT_BASE_DEFECT_MAX = 0.05
DEFAULT_SPIKE_DEFECT_RATE = 0.05
DEFAULT_SPIKE_WINDOW = "09:00-10:00"
DEFAULT_PEAK_DEFECT_RATE = 0.10
DEFAULT_PEAK_WINDOW = "09:30-09:40"
DEFAULT_TARGET_DATES = "2026-03-24,2026-03-25"
DEFAULT_SPIKE_LINE = "LINE-C"
DAY_START_HOUR = 0
DAY_END_HOUR = 24

STATUS_WEIGHTS_NORMAL = (
    ("run", 0.84),
    ("idle", 0.09),
    ("down", 0.04),
    ("maint", 0.03),
)
STATUS_WEIGHTS_SPIKE = (
    ("run", 0.62),
    ("idle", 0.17),
    ("down", 0.15),
    ("maint", 0.06),
)
LINE_TEMP_BASE = {
    "LINE-A": 31.2,
    "LINE-B": 30.8,
    "LINE-C": 33.6,
    "LINE-D": 32.9,
}
LINE_HUM_BASE = {
    "LINE-A": 44.0,
    "LINE-B": 45.5,
    "LINE-C": 47.0,
    "LINE-D": 46.2,
}
DEFECT_WEIGHT_MAP = {
    "LINE-A": [("short", 0.32), ("open", 0.24), ("spur", 0.18), ("mouse_bite", 0.12), ("spurious_copper", 0.08), ("missing_hole", 0.06)],
    "LINE-B": [("short", 0.25), ("open", 0.27), ("spur", 0.18), ("mouse_bite", 0.10), ("spurious_copper", 0.10), ("missing_hole", 0.10)],
    "LINE-C": [("short", 0.20), ("open", 0.18), ("spur", 0.26), ("mouse_bite", 0.08), ("spurious_copper", 0.12), ("missing_hole", 0.16)],
    "LINE-D": [("short", 0.21), ("open", 0.24), ("spur", 0.17), ("mouse_bite", 0.15), ("spurious_copper", 0.11), ("missing_hole", 0.12)],
}
CAUSE_BY_DEFECT = {
    "short": ("QLT-201", "솔더 브리지 의심"),
    "open": ("QLT-202", "납땜 미접합 의심"),
    "spur": ("QLT-203", "패턴 돌기 증가"),
    "mouse_bite": ("QLT-204", "에칭 편차 발생"),
    "spurious_copper": ("QLT-205", "잔류 동박 발생"),
    "missing_hole": ("QLT-206", "홀 가공 누락 의심"),
}
ALARM_MESSAGES = {
    "LINE-A": ("AUTO-A", "LINE A 생산 편차 감지"),
    "LINE-B": ("AUTO-B", "LINE B 검사 변동 감지"),
    "LINE-C": ("AUTO-C", "LINE C NG 급증 경보"),
    "LINE-D": ("AUTO-D", "LINE D 공정 온도 주의"),
}


@dataclass(frozen=True)
class StreamConfig:
    interval_sec: int
    daily_target: int
    base_defect_min: float
    base_defect_max: float
    spike_defect_rate: float
    spike_start: time
    spike_end: time
    peak_defect_rate: float
    peak_start: time
    peak_end: time
    target_dates: list[date]
    reset_target_dates: bool
    seed: int
    line_codes: list[str]
    spike_line: str
    once: bool


@dataclass(frozen=True)
class TickResult:
    target_date: date
    recorded_at: datetime | None
    produced: int
    skipped_reason: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append real-time dummy rows for wed_dashboard.")
    parser.add_argument("--interval-sec", type=int, default=DEFAULT_INTERVAL_SEC)
    parser.add_argument("--daily-target", type=int, default=DEFAULT_DAILY_TARGET)
    parser.add_argument("--base-defect-min", type=float, default=DEFAULT_BASE_DEFECT_MIN)
    parser.add_argument("--base-defect-max", type=float, default=DEFAULT_BASE_DEFECT_MAX)
    parser.add_argument("--spike-defect-rate", type=float, default=DEFAULT_SPIKE_DEFECT_RATE)
    parser.add_argument("--spike-window", default=DEFAULT_SPIKE_WINDOW)
    parser.add_argument("--peak-defect-rate", type=float, default=DEFAULT_PEAK_DEFECT_RATE)
    parser.add_argument("--peak-window", default=DEFAULT_PEAK_WINDOW)
    parser.add_argument("--target-dates", default=DEFAULT_TARGET_DATES)
    parser.add_argument("--reset-target-dates", dest="reset_target_dates", action="store_true")
    parser.add_argument("--no-reset-target-dates", dest="reset_target_dates", action="store_false")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--seed", type=int, default=20260324)
    parser.add_argument("--lines", default=",".join(line.line_code for line in LINES))
    parser.add_argument("--spike-line", default=DEFAULT_SPIKE_LINE)
    parser.set_defaults(reset_target_dates=True)
    return parser.parse_args()


def parse_time_window(raw: str) -> tuple[time, time]:
    parts = [part.strip() for part in raw.split("-", 1)]
    if len(parts) != 2:
        raise SystemExit("spike-window must look like HH:MM-HH:MM")
    return time.fromisoformat(parts[0]), time.fromisoformat(parts[1])


def parse_target_dates(raw: str) -> list[date]:
    values = [token.strip() for token in raw.split(",") if token.strip()]
    if not values:
        raise SystemExit("target-dates is required")
    return [date.fromisoformat(value) for value in values]


def parse_line_codes(raw: str) -> list[str]:
    valid = {line.line_code for line in LINES}
    values = [token.strip().upper() for token in raw.split(",") if token.strip()]
    if not values:
        raise SystemExit("lines is required")
    unknown = [value for value in values if value not in valid]
    if unknown:
        raise SystemExit(f"Unknown line codes: {', '.join(unknown)}")
    return values


def build_config(args: argparse.Namespace) -> StreamConfig:
    spike_start, spike_end = parse_time_window(args.spike_window)
    peak_start, peak_end = parse_time_window(args.peak_window)
    line_codes = parse_line_codes(args.lines)
    spike_line = args.spike_line.strip().upper()
    if spike_line not in line_codes:
        raise SystemExit("spike-line must be included in --lines")
    if args.base_defect_min < 0 or args.base_defect_max < 0:
        raise SystemExit("defect rates must be non-negative")
    if args.base_defect_min > args.base_defect_max:
        raise SystemExit("base-defect-min must be <= base-defect-max")
    if args.daily_target <= 0:
        raise SystemExit("daily-target must be positive")
    if args.interval_sec <= 0:
        raise SystemExit("interval-sec must be positive")
    return StreamConfig(
        interval_sec=args.interval_sec,
        daily_target=args.daily_target,
        base_defect_min=args.base_defect_min,
        base_defect_max=args.base_defect_max,
        spike_defect_rate=args.spike_defect_rate,
        spike_start=spike_start,
        spike_end=spike_end,
        peak_defect_rate=args.peak_defect_rate,
        peak_start=peak_start,
        peak_end=peak_end,
        target_dates=parse_target_dates(args.target_dates),
        reset_target_dates=bool(args.reset_target_dates),
        seed=args.seed,
        line_codes=line_codes,
        spike_line=spike_line,
        once=bool(args.once),
    )


def current_shift(recorded_at: datetime) -> str:
    return "주간" if 6 <= recorded_at.hour < 18 else "야간"


def choose_weighted(rng: random.Random, weighted_values: tuple[tuple[str, float], ...]) -> str:
    roll = rng.random()
    cumulative = 0.0
    for value, weight in weighted_values:
        cumulative += weight
        if roll <= cumulative:
            return value
    return weighted_values[-1][0]


def equipment_map() -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for equipment in EQUIPMENTS:
        mapping.setdefault(equipment.line_code, []).append(equipment.equip_code)
    return mapping


def fetch_day_total(cur: psycopg.Cursor, target_date: date) -> int:
    cur.execute(
        """
        SELECT COALESCE(SUM(produced_qty), 0)
        FROM wed_dashboard.production_records
        WHERE work_date = %s
        """,
        (target_date,),
    )
    row = cur.fetchone()
    return int(row[0] or 0)


def fetch_next_recorded_at(cur: psycopg.Cursor, target_date: date) -> datetime:
    start_dt = datetime.combine(target_date, time(6, 0), tzinfo=KST)
    cur.execute(
        """
        SELECT MAX(recorded_at)
        FROM wed_dashboard.production_records
        WHERE work_date = %s
        """,
        (target_date,),
    )
    row = cur.fetchone()
    max_recorded_at = row[0] if row else None
    if max_recorded_at is None:
        return start_dt
    next_dt = max_recorded_at.astimezone(KST) + timedelta(minutes=1)
    return next_dt


def reset_target_date_rows(cur: psycopg.Cursor, target_dates: list[date]) -> None:
    ranges = [
        (
            datetime.combine(target_date, time.min, tzinfo=KST),
            datetime.combine(target_date + timedelta(days=1), time.min, tzinfo=KST),
        )
        for target_date in target_dates
    ]
    work_dates = tuple(target_dates)

    cur.execute(
        """
        DELETE FROM wed_dashboard.alarm_ack_history aah
        USING wed_dashboard.alarms a
        WHERE aah.alarm_id_ref = a.alarm_id
          AND a.occurred_at >= %s
          AND a.occurred_at < %s
        """,
        ranges[0],
    )
    if len(ranges) > 1:
        for bound in ranges[1:]:
            cur.execute(
                """
                DELETE FROM wed_dashboard.alarm_ack_history aah
                USING wed_dashboard.alarms a
                WHERE aah.alarm_id_ref = a.alarm_id
                  AND a.occurred_at >= %s
                  AND a.occurred_at < %s
                """,
                bound,
            )

    cur.execute("DELETE FROM wed_dashboard.production_records WHERE work_date = ANY(%s)", (list(work_dates),))

    for start_dt, end_dt in ranges:
        cur.execute(
            "DELETE FROM wed_dashboard.inspection_results WHERE recorded_at >= %s AND recorded_at < %s",
            (start_dt, end_dt),
        )
        cur.execute(
            "DELETE FROM wed_dashboard.defect_results WHERE recorded_at >= %s AND recorded_at < %s",
            (start_dt, end_dt),
        )
        cur.execute(
            """
            DELETE FROM wed_dashboard.equipment_status_history
            WHERE (recorded_at >= %s AND recorded_at < %s)
               OR (started_at >= %s AND started_at < %s)
            """,
            (start_dt, end_dt, start_dt, end_dt),
        )
        cur.execute(
            "DELETE FROM wed_dashboard.line_environment WHERE recorded_at >= %s AND recorded_at < %s",
            (start_dt, end_dt),
        )
        cur.execute(
            "DELETE FROM wed_dashboard.recheck_queue WHERE queued_at >= %s AND queued_at < %s",
            (start_dt, end_dt),
        )
        cur.execute(
            "DELETE FROM wed_dashboard.event_logs WHERE recorded_at >= %s AND recorded_at < %s",
            (start_dt, end_dt),
        )
        cur.execute(
            "DELETE FROM wed_dashboard.alarms WHERE occurred_at >= %s AND occurred_at < %s",
            (start_dt, end_dt),
        )


def is_spike_window(recorded_at: datetime, config: StreamConfig, line_code: str) -> bool:
    if line_code != config.spike_line:
        return False
    current_t = recorded_at.time()
    return config.spike_start <= current_t < config.spike_end


def is_peak_window(recorded_at: datetime, config: StreamConfig, line_code: str) -> bool:
    if line_code != config.spike_line:
        return False
    current_t = recorded_at.time()
    return config.peak_start <= current_t < config.peak_end


def resolve_defect_rate(recorded_at: datetime, config: StreamConfig, line_code: str, rng: random.Random) -> float:
    if is_peak_window(recorded_at, config, line_code):
        return config.peak_defect_rate
    if is_spike_window(recorded_at, config, line_code):
        return config.spike_defect_rate
    return rng.uniform(config.base_defect_min, config.base_defect_max)


def allocate_by_share(total: int, line_codes: list[str], rng: random.Random) -> dict[str, int]:
    weights = []
    for line_code in line_codes:
        weights.append(LINE_PLAN_SHARE.get(line_code, 1.0 / len(line_codes)) * rng.uniform(0.92, 1.08))
    total_weight = sum(weights) or 1.0

    allocation: dict[str, int] = {line_code: 0 for line_code in line_codes}
    remaining = total
    for index, line_code in enumerate(line_codes):
        if index == len(line_codes) - 1:
            allocation[line_code] += remaining
            break
        qty = int(round(total * (weights[index] / total_weight)))
        qty = max(0, min(qty, remaining))
        allocation[line_code] += qty
        remaining -= qty
    return allocation


def allocate_integer(total: int, keys: list[str], rng: random.Random) -> dict[str, int]:
    if not keys:
        return {}
    if total <= 0:
        return {key: 0 for key in keys}

    weights = [rng.uniform(0.9, 1.1) for _ in keys]
    total_weight = sum(weights) or 1.0
    allocation = {key: 0 for key in keys}
    remaining = total
    for index, key in enumerate(keys):
        if index == len(keys) - 1:
            allocation[key] += remaining
            break
        qty = int(round(total * (weights[index] / total_weight)))
        qty = max(0, min(qty, remaining))
        allocation[key] += qty
        remaining -= qty
    return allocation


def resolve_tick_production(current_total: int, recorded_at: datetime, config: StreamConfig, rng: random.Random) -> int:
    remaining = config.daily_target - current_total
    if remaining <= 0:
        return 0

    day_start = datetime.combine(recorded_at.date(), time(DAY_START_HOUR, 0), tzinfo=KST)
    day_end = datetime.combine(recorded_at.date(), time(0, 0), tzinfo=KST) + timedelta(hours=DAY_END_HOUR)
    total_minutes = max(int((day_end - day_start).total_seconds() // 60), 1)
    elapsed_minutes = max(int((recorded_at - day_start).total_seconds() // 60) + 1, 1)

    target_cumulative = int(round(config.daily_target * (elapsed_minutes / total_minutes)))
    backlog = max(target_cumulative - current_total, 0)

    per_minute_base = config.daily_target / total_minutes
    if is_spike_window(recorded_at, config, config.spike_line):
        minute_target = per_minute_base * rng.uniform(1.25, 1.60)
    else:
        minute_target = per_minute_base * rng.uniform(0.85, 1.15)

    qty = max(int(round(minute_target)), 1)
    if backlog > 0:
        qty = max(qty, min(backlog, int(round(per_minute_base * 3))))

    return max(0, min(qty, remaining))


def split_defects(line_code: str, total_defects: int, rng: random.Random) -> list[tuple[str, int]]:
    if total_defects <= 0:
        return []
    weighted = DEFECT_WEIGHT_MAP[line_code]
    names = [name for name, _weight in weighted]
    weights = [weight for _name, weight in weighted]
    bucket_count = min(3, max(1, total_defects))
    chosen = rng.choices(names, weights=weights, k=bucket_count)
    result: dict[str, int] = {}
    remaining = total_defects
    for index, defect_code in enumerate(chosen):
        if index == bucket_count - 1:
            qty = remaining
        else:
            max_pick = max(1, remaining - (bucket_count - index - 1))
            qty = rng.randint(1, max_pick)
        remaining -= qty
        result[defect_code] = result.get(defect_code, 0) + qty
    return list(result.items())


def insert_rows(
    cur: psycopg.Cursor,
    table_name: str,
    stmt: str,
    rows: list[tuple],
) -> None:
    if rows:
        insert_fact_rows(cur, table_name, stmt, rows)


def append_tick(
    cur: psycopg.Cursor,
    ids: dict[str, dict[str, int]],
    config: StreamConfig,
    target_date: date,
    defect_carry: dict[tuple[date, str], float],
    rng: random.Random,
) -> TickResult:
    current_total = fetch_day_total(cur, target_date)
    recorded_at = fetch_next_recorded_at(cur, target_date)
    batch_total = resolve_tick_production(current_total, recorded_at, config, rng)
    if batch_total <= 0:
        return TickResult(target_date=target_date, recorded_at=None, produced=0, skipped_reason="daily_target_reached")

    equip_by_line = equipment_map()
    factory_id = ids["factories"][FACTORIES[0].factory_code]
    allocations = allocate_by_share(batch_total, config.line_codes, rng)
    shift = current_shift(recorded_at)

    production_rows: list[tuple] = []
    inspection_rows: list[tuple] = []
    defect_rows: list[tuple] = []
    status_rows: list[tuple] = []
    env_rows: list[tuple] = []
    event_rows: list[tuple] = []
    alarm_rows: list[tuple] = []
    recheck_rows: list[tuple] = []

    tick_id = recorded_at.strftime("%Y%m%d%H%M")

    for line_code, produced_qty in allocations.items():
        if produced_qty <= 0:
            continue
        line_id = ids["lines"][line_code]
        line_equip_codes = sorted(equip_by_line[line_code])
        produced_by_equip = allocate_integer(produced_qty, line_equip_codes, rng)
        line_temp_bonus = 2.0 if is_peak_window(recorded_at, config, line_code) else 1.4 if is_spike_window(recorded_at, config, line_code) else 0.0
        env_rows.extend(
            [
                (
                    line_id,
                    "temp_sensor",
                    "temperature",
                    round(LINE_TEMP_BASE[line_code] + line_temp_bonus + rng.uniform(-0.8, 1.2), 2),
                    "C",
                    recorded_at,
                ),
                (
                    line_id,
                    "humidity_sensor",
                    "humidity",
                    round(LINE_HUM_BASE[line_code] + rng.uniform(-2.0, 2.0), 2),
                    "%",
                    recorded_at,
                ),
            ]
        )

        for equip_code, equip_produced_qty in produced_by_equip.items():
            equip_id = ids["equipments"][equip_code]
            model_code = rng.choice(MODEL_CODES)
            lot_id = f"RT-{line_code}-{equip_code}-{tick_id}-{rng.randint(100, 999)}"
            defect_rate = resolve_defect_rate(recorded_at, config, line_code, rng)
            carry_key = (target_date, equip_code)
            expected_ng = equip_produced_qty * defect_rate + defect_carry.get(carry_key, 0.0)
            ng_qty = min(equip_produced_qty, int(expected_ng))
            defect_carry[carry_key] = max(expected_ng - ng_qty, 0.0)
            good_qty = max(equip_produced_qty - ng_qty, 0)

            production_rows.append(
                (
                    factory_id,
                    line_id,
                    equip_id,
                    lot_id,
                    model_code,
                    target_date,
                    shift,
                    equip_produced_qty,
                    good_qty,
                    ng_qty,
                    recorded_at,
                )
            )

            checked_qty = equip_produced_qty + rng.randint(0, max(2, max(equip_produced_qty, 1) // 20))
            fail_qty = min(max(ng_qty, 0), checked_qty)
            pass_qty = max(checked_qty - fail_qty, 0)
            inspection_rows.append(
                (
                    line_id,
                    equip_id,
                    lot_id,
                    model_code,
                    "AOI",
                    checked_qty,
                    pass_qty,
                    fail_qty,
                    recorded_at,
                )
            )

            for defect_code, defect_count in split_defects(line_code, fail_qty, rng):
                severity = next((severity for code, _name, severity in DEFECT_DEFS if code == defect_code), "warning")
                cause_code, cause_text = CAUSE_BY_DEFECT[defect_code]
                defect_rows.append(
                    (
                        line_id,
                        equip_id,
                        lot_id,
                        model_code,
                        defect_code,
                        defect_code.upper(),
                        defect_count,
                        severity,
                        cause_code,
                        cause_text,
                        recorded_at,
                    )
                )

            status_weights = STATUS_WEIGHTS_SPIKE if (is_spike_window(recorded_at, config, line_code) or is_peak_window(recorded_at, config, line_code)) else STATUS_WEIGHTS_NORMAL
            status_code = choose_weighted(rng, status_weights)
            reason_text = None
            if status_code == "down":
                reason_text = "실시간 시연용 장비 정지"
            elif status_code == "idle":
                reason_text = "자재 교체 대기"
            elif status_code == "maint":
                reason_text = "예방 정비"
            status_rows.append(
                (
                    line_id,
                    equip_id,
                    status_code,
                    "AUTO-STREAM" if status_code != "run" else None,
                    reason_text,
                    recorded_at - timedelta(seconds=config.interval_sec),
                    recorded_at,
                    config.interval_sec,
                    recorded_at,
                )
            )

            event_severity = "warning" if fail_qty > 0 or status_code in {"down", "maint"} else "info"
            event_rows.append(
                (
                    "quality" if fail_qty > 0 else "production",
                    event_severity,
                    line_id,
                    equip_id,
                    f"{line_code} {equip_code} 실시간 반영",
                    f"생산 {equip_produced_qty}pcs, NG {fail_qty}건, 상태 {status_code.upper()}",
                    f"lot={lot_id} shift={shift}",
                    recorded_at,
                )
            )

            if is_spike_window(recorded_at, config, line_code) or is_peak_window(recorded_at, config, line_code) or (status_code == "down" and rng.random() < 0.6):
                alarm_code, alarm_message = ALARM_MESSAGES[line_code]
                alarm_rows.append(
                    (
                        line_id,
                        equip_id,
                        f"{alarm_code}-{equip_code}-{tick_id}",
                        f"{line_code} {equip_code} 자동 경보",
                        "AUTO-STREAM",
                        "critical" if (is_spike_window(recorded_at, config, line_code) or is_peak_window(recorded_at, config, line_code)) else "warning",
                        alarm_message,
                        "active",
                        recorded_at,
                        None,
                    )
                )

            if fail_qty >= max(1, equip_produced_qty // 8):
                recheck_rows.append(
                    (
                        lot_id,
                        line_id,
                        equip_id,
                        "spur" if line_code == config.spike_line else "open",
                        "HIGH" if (is_spike_window(recorded_at, config, line_code) or is_peak_window(recorded_at, config, line_code)) else "MEDIUM",
                        "critical" if (is_spike_window(recorded_at, config, line_code) or is_peak_window(recorded_at, config, line_code)) else "warning",
                        "queued",
                        fail_qty,
                        "실시간 더미 적재에서 생성된 재검 건",
                        None,
                        recorded_at,
                        None,
                        "auto-stream",
                    )
                )

    insert_rows(
        cur,
        "production_records",
        """
        INSERT INTO wed_dashboard.production_records (
            factory_id, line_id, equip_id, lot_id, model_code, work_date, work_shift,
            produced_qty, good_qty, ng_qty, recorded_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        production_rows,
    )
    insert_rows(
        cur,
        "inspection_results",
        """
        INSERT INTO wed_dashboard.inspection_results (
            line_id, equip_id, lot_id, model_code, inspection_type, total_checked_qty,
            pass_qty, fail_qty, recorded_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        inspection_rows,
    )
    insert_rows(
        cur,
        "defect_results",
        """
        INSERT INTO wed_dashboard.defect_results (
            line_id, equip_id, lot_id, model_code, defect_code, defect_name, defect_count,
            severity, cause_code, cause_text, recorded_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        defect_rows,
    )
    insert_rows(
        cur,
        "equipment_status_history",
        """
        INSERT INTO wed_dashboard.equipment_status_history (
            line_id, equip_id, status_code, reason_code, reason_text, started_at,
            ended_at, duration_sec, recorded_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        status_rows,
    )
    insert_rows(
        cur,
        "line_environment",
        """
        INSERT INTO wed_dashboard.line_environment (
            line_id, sensor_type, metric_name, metric_value, unit, recorded_at
        ) VALUES (%s, %s, %s, %s, %s, %s)
        """,
        env_rows,
    )
    insert_rows(
        cur,
        "event_logs",
        """
        INSERT INTO wed_dashboard.event_logs (
            event_type, severity, line_id, equip_id, title, message, meta_text, recorded_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        event_rows,
    )
    insert_rows(
        cur,
        "alarms",
        """
        INSERT INTO wed_dashboard.alarms (
            line_id, equip_id, alarm_code, alarm_name, cause_code, severity, message,
            status, occurred_at, cleared_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        alarm_rows,
    )
    insert_rows(
        cur,
        "recheck_queue",
        """
        INSERT INTO wed_dashboard.recheck_queue (
            lot_id, line_id, equip_id, defect_code, priority, severity, status,
            count_qty, cause_text, owner_employee_id, queued_at, completed_at, note
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        recheck_rows,
    )

    return TickResult(target_date=target_date, recorded_at=recorded_at, produced=batch_total)


def run_stream(config: StreamConfig) -> None:
    rng = random.Random(config.seed)
    conninfo = psycopg_conninfo(get_database_url())
    pending_reset_dates = set(config.target_dates) if config.reset_target_dates else set()
    defect_carry: dict[tuple[date, str], float] = {}

    with psycopg.connect(conninfo) as conn:
        while True:
            now_kst = datetime.now(KST)
            active_dates = [target_date for target_date in config.target_dates if target_date == now_kst.date()]
            results: list[TickResult] = []

            with conn.cursor() as cur:
                ids = ensure_master_data(cur)

                reset_now = [target_date for target_date in active_dates if target_date in pending_reset_dates]
                if reset_now:
                    reset_target_date_rows(cur, reset_now)
                    pending_reset_dates.difference_update(reset_now)
                    for reset_date in reset_now:
                        for line_code in config.line_codes:
                            defect_carry.pop((reset_date, line_code), None)

                for target_date in active_dates:
                    results.append(append_tick(cur, ids, config, target_date, defect_carry, rng))
                conn.commit()

            if not active_dates:
                print(
                    "[stream] idle"
                    f" today={now_kst.date().isoformat()}"
                    f" target_dates={','.join(target.isoformat() for target in config.target_dates)}"
                )

            for result in results:
                if result.skipped_reason:
                    print(
                        "[stream] skipped"
                        f" work_date={result.target_date.isoformat()}"
                        f" reason={result.skipped_reason}"
                    )
                else:
                    print(
                        "[stream] inserted"
                        f" work_date={result.target_date.isoformat()}"
                        f" recorded_at={result.recorded_at.isoformat() if result.recorded_at else '-'}"
                        f" produced={result.produced}"
                    )

            if config.once:
                return
            time_module.sleep(config.interval_sec)


def main() -> None:
    config = build_config(parse_args())
    run_stream(config)


if __name__ == "__main__":
    main()
