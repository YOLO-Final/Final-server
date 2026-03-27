#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any

import psycopg
from sqlalchemy.engine import make_url

from src.lib.settings import settings

KST = timezone(timedelta(hours=9))
DEFAULT_START_DATE = date(2026, 3, 20)
DEFAULT_END_DATE = date(2026, 3, 25)
DEFAULT_SEED = 20260320
SCENARIO_ANCHOR_DATE = DEFAULT_START_DATE
DAY_SLOT_HOURS = list(range(24))
DAY_MINUTES = 24 * 60
DAILY_PLAN_TOTAL = 40000
HOUR_DISTRIBUTION_COUNTS = [
    900, 850, 800, 780, 820, 980, 1350, 1850, 2250, 2450, 2550, 2600,
    2200, 2350, 2450, 2500, 2400, 2250, 2050, 1850, 1450, 1100, 700, 520,
]
LINE_PLAN_SHARE = {
    "LINE-A": 0.26,
    "LINE-B": 0.30,
    "LINE-C": 0.22,
    "LINE-D": 0.22,
}
LINE_SORT = {
    "LINE-A": 1,
    "LINE-B": 2,
    "LINE-C": 3,
    "LINE-D": 4,
}
PRIMARY_EQUIPMENT = {
    "LINE-A": "MNT-01",
    "LINE-B": "DRV-02",
    "LINE-C": "MNT-04",
    "LINE-D": "REFLOW-01",
}
SHIFT_HOURS = {
    "주간": [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17],
    "야간": [18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5],
}
WORKER_DAILY_MAX = 15000
WORKER_DAILY_BASE_MIN = 6000
WORKER_DAILY_BASE_MAX = 8600
WORKER_DAILY_BURST_MAX = 16500
WORKER_DAILY_BURST_PROB = 0.03
DEFECT_RATE_BASE_MIN = 0.01
DEFECT_RATE_BASE_MAX = 0.04
DEFECT_RATE_SPIKE_MIN = 0.05
DEFECT_RATE_SPIKE_MAX = 0.15
DEFECT_RATE_SPIKE_PROB = 0.08
DEFECT_RATE_ALERT_LINE_BOOST = 0.02


@dataclass(frozen=True)
class FactorySeed:
    factory_code: str
    factory_name: str


@dataclass(frozen=True)
class LineSeed:
    line_code: str
    line_name: str
    line_type: str


@dataclass(frozen=True)
class EquipmentSeed:
    line_code: str
    equip_code: str
    equip_name: str
    equip_type: str
    vendor: str
    model_name: str
    install_date: date


@dataclass(frozen=True)
class EmployeeSeed:
    employee_no: str
    employee_name: str
    role_code: str
    line_code: str
    shift_code: str


@dataclass(frozen=True)
class ScenarioProfile:
    name: str
    day_total: int
    line_output_multiplier: dict[str, float]
    line_defect_rate: dict[str, float]
    line_availability_pct: dict[str, float]
    inspection_ratio: float
    active_alarm_count: int
    recheck_counts: dict[str, int]


FACTORIES = [
    FactorySeed("HQ-1", "본사 1공장"),
]

LINES = [
    LineSeed("LINE-A", "LINE A", "SMT"),
    LineSeed("LINE-B", "LINE B", "SMT"),
    LineSeed("LINE-C", "LINE C", "SMT"),
    LineSeed("LINE-D", "LINE D", "SMT"),
]

EQUIPMENTS = [
    EquipmentSeed("LINE-A", "AOI-01", "광학검사기 A1", "AOI", "Omron", "VT-S530", date(2024, 2, 1)),
    EquipmentSeed("LINE-A", "MNT-01", "마운터 A1", "MOUNT", "Fuji", "NXT-III", date(2024, 2, 10)),
    EquipmentSeed("LINE-A", "PRN-01", "프린터 A1", "PRINTER", "DEK", "NeoHorizon", date(2024, 2, 20)),
    EquipmentSeed("LINE-B", "AOI-02", "광학검사기 B1", "AOI", "Omron", "VT-S530", date(2024, 3, 1)),
    EquipmentSeed("LINE-B", "DRV-02", "드라이버 B1", "DRIVER", "Yamaha", "YSM20R", date(2024, 3, 11)),
    EquipmentSeed("LINE-B", "PRN-02", "프린터 B1", "PRINTER", "DEK", "NeoHorizon", date(2024, 3, 22)),
    EquipmentSeed("LINE-C", "AOI-03", "광학검사기 C1", "AOI", "Omron", "VT-S530", date(2024, 4, 1)),
    EquipmentSeed("LINE-C", "CMP-07", "컴포넌트 공급기 C1", "COMPONENT", "ASM", "Siplace X4", date(2024, 4, 28)),
    EquipmentSeed("LINE-C", "MNT-04", "마운터 C1", "MOUNT", "Fuji", "NXT-III", date(2024, 4, 15)),
    EquipmentSeed("LINE-C", "PRN-03", "프린터 C1", "PRINTER", "DEK", "NeoHorizon", date(2024, 4, 22)),
    EquipmentSeed("LINE-D", "AOI-04", "광학검사기 D1", "AOI", "Omron", "VT-S530", date(2024, 5, 2)),
    EquipmentSeed("LINE-D", "CMP-08", "컴포넌트 공급기 D1", "COMPONENT", "ASM", "Siplace X4", date(2024, 5, 29)),
    EquipmentSeed("LINE-D", "REFLOW-01", "리플로우 D1", "REFLOW", "Heller", "1913 MK5", date(2024, 5, 16)),
]

EMPLOYEES = [
    EmployeeSeed("EMP-1001", "김민수", "operator", "LINE-A", "주간"),
    EmployeeSeed("EMP-1002", "박지현", "operator", "LINE-A", "야간"),
    EmployeeSeed("EMP-1003", "이서준", "operator", "LINE-B", "주간"),
    EmployeeSeed("EMP-1004", "최유진", "operator", "LINE-B", "야간"),
    EmployeeSeed("EMP-1005", "한도윤", "operator", "LINE-C", "주간"),
    EmployeeSeed("EMP-1006", "오수빈", "operator", "LINE-C", "야간"),
    EmployeeSeed("EMP-1007", "정하은", "operator", "LINE-D", "주간"),
    EmployeeSeed("EMP-1008", "윤지호", "operator", "LINE-D", "야간"),
    EmployeeSeed("EMP-2001", "김현우", "qa", "LINE-A", "주간"),
    EmployeeSeed("EMP-2002", "박서영", "qa", "LINE-B", "주간"),
    EmployeeSeed("EMP-3001", "이준혁", "maintenance", "LINE-C", "주간"),
    EmployeeSeed("EMP-4001", "장예린", "manager", "LINE-D", "주간"),
]

MODEL_CODES = ["PCB-2401", "PCB-2402", "PCB-2403", "PCB-2404"]
DEFECT_DEFS = [
    ("short", "SHORT", "critical"),
    ("open", "OPEN", "warning"),
    ("spur", "SPUR", "warning"),
    ("mouse_bite", "MOUSE_BITE", "info"),
    ("spurious_copper", "SPURIOUS_COPPER", "info"),
    ("missing_hole", "MISSING_HOLE", "info"),
]
SCENARIOS = {
    "stable": ScenarioProfile(
        name="stable",
        day_total=DAILY_PLAN_TOTAL,
        line_output_multiplier={"LINE-A": 1.00, "LINE-B": 1.02, "LINE-C": 0.95, "LINE-D": 1.03},
        line_defect_rate={"LINE-A": 0.011, "LINE-B": 0.010, "LINE-C": 0.019, "LINE-D": 0.015},
        line_availability_pct={"LINE-A": 97.0, "LINE-B": 98.2, "LINE-C": 95.8, "LINE-D": 96.4},
        inspection_ratio=0.990,
        active_alarm_count=1,
        recheck_counts={"LINE-C": 3},
    ),
    "watch": ScenarioProfile(
        name="watch",
        day_total=DAILY_PLAN_TOTAL,
        line_output_multiplier={"LINE-A": 0.99, "LINE-B": 1.03, "LINE-C": 0.92, "LINE-D": 1.04},
        line_defect_rate={"LINE-A": 0.017, "LINE-B": 0.015, "LINE-C": 0.026, "LINE-D": 0.022},
        line_availability_pct={"LINE-A": 96.0, "LINE-B": 97.8, "LINE-C": 94.5, "LINE-D": 95.2},
        inspection_ratio=0.987,
        active_alarm_count=2,
        recheck_counts={"LINE-C": 6, "LINE-D": 4},
    ),
    "warning": ScenarioProfile(
        name="warning",
        day_total=DAILY_PLAN_TOTAL,
        line_output_multiplier={"LINE-A": 0.97, "LINE-B": 1.05, "LINE-C": 0.86, "LINE-D": 1.05},
        line_defect_rate={"LINE-A": 0.024, "LINE-B": 0.020, "LINE-C": 0.048, "LINE-D": 0.037},
        line_availability_pct={"LINE-A": 95.0, "LINE-B": 97.2, "LINE-C": 91.8, "LINE-D": 93.2},
        inspection_ratio=0.982,
        active_alarm_count=3,
        recheck_counts={"LINE-C": 12, "LINE-D": 8},
    ),
    "critical": ScenarioProfile(
        name="critical",
        day_total=DAILY_PLAN_TOTAL,
        line_output_multiplier={"LINE-A": 0.98, "LINE-B": 1.10, "LINE-C": 0.74, "LINE-D": 1.08},
        line_defect_rate={"LINE-A": 0.032, "LINE-B": 0.024, "LINE-C": 0.083, "LINE-D": 0.058},
        line_availability_pct={"LINE-A": 94.0, "LINE-B": 96.8, "LINE-C": 86.0, "LINE-D": 91.5},
        inspection_ratio=0.978,
        active_alarm_count=4,
        recheck_counts={"LINE-C": 34, "LINE-D": 7, "LINE-B": 4},
    ),
    "worst": ScenarioProfile(
        name="worst",
        day_total=DAILY_PLAN_TOTAL,
        line_output_multiplier={"LINE-A": 0.96, "LINE-B": 1.12, "LINE-C": 0.66, "LINE-D": 1.10},
        line_defect_rate={"LINE-A": 0.036, "LINE-B": 0.028, "LINE-C": 0.094, "LINE-D": 0.066},
        line_availability_pct={"LINE-A": 93.0, "LINE-B": 96.0, "LINE-C": 80.5, "LINE-D": 89.0},
        inspection_ratio=0.974,
        active_alarm_count=5,
        recheck_counts={"LINE-C": 34, "LINE-D": 8, "LINE-B": 4},
    ),
    "recovery": ScenarioProfile(
        name="recovery",
        day_total=DAILY_PLAN_TOTAL,
        line_output_multiplier={"LINE-A": 1.00, "LINE-B": 1.04, "LINE-C": 0.88, "LINE-D": 1.02},
        line_defect_rate={"LINE-A": 0.019, "LINE-B": 0.016, "LINE-C": 0.041, "LINE-D": 0.031},
        line_availability_pct={"LINE-A": 96.2, "LINE-B": 97.4, "LINE-C": 92.8, "LINE-D": 94.2},
        inspection_ratio=0.986,
        active_alarm_count=2,
        recheck_counts={"LINE-C": 10, "LINE-D": 5},
    ),
}
SCENARIO_CYCLE = ["stable", "watch", "warning", "critical", "worst", "recovery"]
SCENARIO_WEIGHTS = {
    "stable": 0.18,
    "watch": 0.17,
    "warning": 0.24,
    "critical": 0.16,
    "worst": 0.07,
    "recovery": 0.18,
}
WEEKDAY_OUTPUT_MULTIPLIER = {
    0: 1.02,
    1: 1.03,
    2: 1.00,
    3: 0.98,
    4: 0.95,
    5: 0.86,
    6: 0.80,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate dummy data for wed_dashboard schema.")
    parser.add_argument("--start-date", type=date.fromisoformat, default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", type=date.fromisoformat, default=DEFAULT_END_DATE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--apply", action="store_true", help="Actually write to the database.")
    parser.add_argument("--no-truncate", action="store_true", help="Append instead of truncating wed_dashboard tables.")
    return parser.parse_args()


def get_database_url() -> str:
    raw = os.getenv("DATABASE_URL", "").strip()
    return raw or settings.database_url


def psycopg_conninfo(database_url: str) -> str:
    url = make_url(database_url)
    return (
        f"dbname={url.database} "
        f"user={url.username} "
        f"password={url.password} "
        f"host={url.host} "
        f"port={url.port or 5432}"
    )


def local_slot(day: date, hour: int, minute: int) -> datetime:
    return datetime.combine(day, time(hour=hour, minute=minute), tzinfo=KST)


def resolve_counts(total: int, weights: list[float]) -> list[int]:
    raw = [total * weight for weight in weights]
    counts = [int(value) for value in raw]
    remainder = total - sum(counts)
    ranking = sorted(range(len(weights)), key=lambda idx: raw[idx] - counts[idx], reverse=True)
    for idx in ranking[:remainder]:
        counts[idx] += 1
    return counts


def hour_weights() -> list[float]:
    total = sum(HOUR_DISTRIBUTION_COUNTS)
    return [count / total for count in HOUR_DISTRIBUTION_COUNTS]


def random_worker_daily_capacity(rng: random.Random) -> int:
    if rng.random() < WORKER_DAILY_BURST_PROB:
        return rng.randint(WORKER_DAILY_MAX + 1, WORKER_DAILY_BURST_MAX)
    return rng.randint(WORKER_DAILY_BASE_MIN, WORKER_DAILY_BASE_MAX)


def build_line_shift_targets(rng: random.Random, line_code: str, line_multiplier: float) -> dict[str, int]:
    targets: dict[str, int] = {}
    for shift_name, hours in SHIFT_HOURS.items():
        operators = [
            employee
            for employee in EMPLOYEES
            if employee.role_code == "operator" and employee.line_code == line_code and employee.shift_code == shift_name
        ]
        if not operators:
            continue
        shift_capacity = sum(random_worker_daily_capacity(rng) for _ in operators)
        utilization = rng.uniform(0.60, 0.76)
        shift_output = int(round(shift_capacity * utilization * line_multiplier))
        targets[shift_name] = max(0, min(shift_output, shift_capacity))
    return targets


def normalize_weights(raw_weights: list[float]) -> list[float]:
    total = sum(raw_weights)
    if total <= 0:
        return [1 / len(raw_weights)] * len(raw_weights)
    return [value / total for value in raw_weights]


def random_defect_weights(
    rng: random.Random,
    *,
    line_code: str,
    focus_critical_lot: bool,
) -> list[float]:
    raw = [rng.uniform(0.7, 1.4) for _ in DEFECT_DEFS]

    # 라인별로 대표 결함이 약간 더 크게 보이도록 편향을 준다.
    dominant_map = {
        "LINE-A": "mouse_bite",
        "LINE-B": "open",
        "LINE-C": "short",
        "LINE-D": "spur",
    }
    dominant_code = dominant_map.get(line_code, "short")
    dominant_idx = next((idx for idx, defect in enumerate(DEFECT_DEFS) if defect[0] == dominant_code), 0)
    raw[dominant_idx] *= rng.uniform(1.25, 1.6)

    # 보조 결함도 약간만 올려 지나치게 단일 결함으로 쏠리는 것을 막는다.
    sub_candidates = [idx for idx in range(len(DEFECT_DEFS)) if idx != dominant_idx]
    if sub_candidates:
        sub_idx = rng.choice(sub_candidates)
        raw[sub_idx] *= rng.uniform(1.05, 1.18)

    if focus_critical_lot:
        raw[0] *= 1.7  # short
        raw[1] *= 1.4  # open

    return normalize_weights(raw)


def line_equipment_weights(rng: random.Random, line_code: str, *, scenario_name: str) -> tuple[list[str], list[float]]:
    equip_codes = [equipment.equip_code for equipment in EQUIPMENTS if equipment.line_code == line_code]
    if not equip_codes:
        primary = PRIMARY_EQUIPMENT.get(line_code)
        return ([primary] if primary else [], [1.0] if primary else [])

    primary_code = PRIMARY_EQUIPMENT.get(line_code, equip_codes[0])

    # 분산은 골고루 유지하되, 라인 대표 설비에만 과도하게 쏠리지 않게 상한을 둔다.
    if line_code == "LINE-C" and scenario_name in {"critical", "worst"}:
        primary_base = 0.50
        jitter = 0.05
    else:
        primary_base = 0.45
        jitter = 0.05

    primary_weight = max(0.35, min(0.58, primary_base + rng.uniform(-jitter, jitter)))

    remain_codes = [code for code in equip_codes if code != primary_code]
    if not remain_codes:
        return [primary_code], [1.0]

    remain_total = max(1e-6, 1.0 - primary_weight)
    remain_raw = [rng.uniform(0.85, 1.15) for _ in remain_codes]
    remain_norm = normalize_weights(remain_raw)
    weights = [primary_weight] + [remain_total * value for value in remain_norm]
    return [primary_code] + remain_codes, weights


def shift_for_hour(hour: int) -> str:
    return "주간" if hour in SHIFT_HOURS["주간"] else "야간"


def sample_defect_rate(rng: random.Random, *, line_code: str, scenario_name: str) -> float:
    if rng.random() < DEFECT_RATE_SPIKE_PROB:
        rate = rng.uniform(DEFECT_RATE_SPIKE_MIN, DEFECT_RATE_SPIKE_MAX)
    else:
        rate = rng.uniform(DEFECT_RATE_BASE_MIN, DEFECT_RATE_BASE_MAX)

    if line_code == "LINE-C" and scenario_name in {"critical", "worst", "warning"}:
        rate += DEFECT_RATE_ALERT_LINE_BOOST

    return min(DEFECT_RATE_SPIKE_MAX, max(DEFECT_RATE_BASE_MIN, rate))


def smooth_defect_rate(prev_rate: float | None, sampled_rate: float) -> float:
    if prev_rate is None:
        return sampled_rate

    # 급등/급락을 줄이기 위해 이전 슬롯과 현재 샘플을 혼합한다.
    blended = (prev_rate * 0.68) + (sampled_rate * 0.32)

    # 슬롯 간 변화량을 제한해 임계값을 계속 넘나드는 노이즈를 완화한다.
    max_up = 0.020
    max_down = 0.018
    low = prev_rate - max_down
    high = prev_rate + max_up
    smoothed = max(low, min(high, blended))

    return min(DEFECT_RATE_SPIKE_MAX, max(DEFECT_RATE_BASE_MIN, smoothed))


def line_lot_id(day: date, line_code: str, scenario_name: str, lot_index: int) -> str:
    if scenario_name in {"critical", "worst"} and line_code == "LINE-C" and 11 <= lot_index <= 15:
        return "LOT-88421"
    base = 88400 + ((day.toordinal() + lot_index + LINE_SORT[line_code]) % 40)
    return f"LOT-{base}"


def _pick_scenario(rng: random.Random, *, prev: str | None, weekday: int) -> str:
    names = list(SCENARIO_WEIGHTS.keys())
    weights = [SCENARIO_WEIGHTS[name] for name in names]
    if weekday >= 5:
        weights = [
            weight * (1.20 if names[idx] in {"warning", "critical", "recovery"} else 0.92)
            for idx, weight in enumerate(weights)
        ]
    if prev:
        weights = [
            weight * (0.55 if name == prev else 1.0)
            for name, weight in zip(names, weights, strict=False)
        ]
    return rng.choices(names, weights=weights, k=1)[0]


def build_scenario_schedule(start_date: date, end_date: date, rng: random.Random) -> dict[date, str]:
    days = (end_date - start_date).days + 1
    schedule: dict[date, str] = {}
    prev: str | None = None
    for offset in range(days):
        target = start_date + timedelta(days=offset)
        picked = _pick_scenario(rng, prev=prev, weekday=target.weekday())
        if offset > 0 and offset % rng.randint(9, 12) == 0:
            picked = rng.choice(["warning", "critical", "worst"])
        schedule[target] = picked
        prev = picked
    return schedule


def load_master_ids(cur: psycopg.Cursor) -> dict[str, dict[str, int]]:
    cur.execute("SELECT factory_code, factory_id FROM wed_dashboard.factories")
    factory_ids = {code: factory_id for code, factory_id in cur.fetchall()}
    cur.execute("SELECT line_code, line_id FROM wed_dashboard.lines")
    line_ids = {code: line_id for code, line_id in cur.fetchall()}
    cur.execute("SELECT equip_code, equip_id FROM wed_dashboard.equipments")
    equip_ids = {code: equip_id for code, equip_id in cur.fetchall()}
    cur.execute("SELECT employee_no, employee_id FROM wed_dashboard.employees")
    employee_ids = {code: employee_id for code, employee_id in cur.fetchall()}
    return {
        "factories": factory_ids,
        "lines": line_ids,
        "equipments": equip_ids,
        "employees": employee_ids,
    }


def ensure_master_data(cur: psycopg.Cursor) -> dict[str, dict[str, int]]:
    for factory in FACTORIES:
        cur.execute(
            """
            INSERT INTO wed_dashboard.factories (factory_code, factory_name, is_active)
            VALUES (%s, %s, TRUE)
            ON CONFLICT (factory_code) DO UPDATE
            SET factory_name = EXCLUDED.factory_name,
                is_active = TRUE,
                updated_at = NOW()
            """,
            (factory.factory_code, factory.factory_name),
        )

    ids = load_master_ids(cur)
    factory_id = ids["factories"]["HQ-1"]

    for line in LINES:
        cur.execute(
            """
            INSERT INTO wed_dashboard.lines (
                factory_id, line_code, line_name, line_type, sort_order, is_active
            )
            VALUES (%s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (line_code) DO UPDATE
            SET factory_id = EXCLUDED.factory_id,
                line_name = EXCLUDED.line_name,
                line_type = EXCLUDED.line_type,
                sort_order = EXCLUDED.sort_order,
                is_active = TRUE,
                updated_at = NOW()
            """,
            (factory_id, line.line_code, line.line_name, line.line_type, LINE_SORT[line.line_code]),
        )

    ids = load_master_ids(cur)

    for equipment in EQUIPMENTS:
        cur.execute(
            """
            INSERT INTO wed_dashboard.equipments (
                line_id, equip_code, equip_name, equip_type, vendor, model_name, install_date, is_active
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (equip_code) DO UPDATE
            SET line_id = EXCLUDED.line_id,
                equip_name = EXCLUDED.equip_name,
                equip_type = EXCLUDED.equip_type,
                vendor = EXCLUDED.vendor,
                model_name = EXCLUDED.model_name,
                install_date = EXCLUDED.install_date,
                is_active = TRUE,
                updated_at = NOW()
            """,
            (
                ids["lines"][equipment.line_code],
                equipment.equip_code,
                equipment.equip_name,
                equipment.equip_type,
                equipment.vendor,
                equipment.model_name,
                equipment.install_date,
            ),
        )

    ids = load_master_ids(cur)

    for employee in EMPLOYEES:
        cur.execute(
            """
            INSERT INTO wed_dashboard.employees (
                employee_no, employee_name, role_code, line_id, shift_code, is_active
            )
            VALUES (%s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (employee_no) DO UPDATE
            SET employee_name = EXCLUDED.employee_name,
                role_code = EXCLUDED.role_code,
                line_id = EXCLUDED.line_id,
                shift_code = EXCLUDED.shift_code,
                is_active = TRUE,
                updated_at = NOW()
            """,
            (
                employee.employee_no,
                employee.employee_name,
                employee.role_code,
                ids["lines"][employee.line_code],
                employee.shift_code,
            ),
        )

    return load_master_ids(cur)


def truncate_dashboard_tables(cur: psycopg.Cursor) -> None:
    cur.execute(
        """
        TRUNCATE TABLE
            wed_dashboard.alarm_ack_history,
            wed_dashboard.event_logs,
            wed_dashboard.recheck_queue,
            wed_dashboard.alarms,
            wed_dashboard.defect_results,
            wed_dashboard.inspection_results,
            wed_dashboard.equipment_status_history,
            wed_dashboard.line_environment,
            wed_dashboard.production_records,
            wed_dashboard.employees,
            wed_dashboard.equipments,
            wed_dashboard.lines,
            wed_dashboard.factories
        RESTART IDENTITY CASCADE
        """
    )


def append_status_rows(
    rows: dict[str, list[tuple]],
    line_id: int,
    equip_id: int,
    day: date,
    availability_pct: float,
    *,
    down_reason: str | None = None,
    down_started_at: datetime | None = None,
    down_minutes: int | None = None,
) -> None:
    day_start = local_slot(day, 0, 0)
    day_end = day_start + timedelta(days=1)
    run_minutes = int(round(DAY_MINUTES * (availability_pct / 100.0)))
    idle_minutes = max(DAY_MINUTES - run_minutes, 0)
    cursor = day_start

    if down_started_at is not None:
        run_end = min(max(down_started_at, day_start), day_end)
        run_duration = int((run_end - day_start).total_seconds())
        if run_duration > 0:
            rows["equipment_status_history"].append(
                (line_id, equip_id, "run", None, None, day_start, run_end, run_duration, run_end)
            )
        down_end = min(day_end, down_started_at + timedelta(minutes=down_minutes or max(idle_minutes, 30)))
        down_duration = int((down_end - down_started_at).total_seconds())
        if down_duration > 0:
            rows["equipment_status_history"].append(
                (
                    line_id,
                    equip_id,
                    "down",
                    "DT-201",
                    down_reason or "장비 정지",
                    down_started_at,
                    down_end,
                    down_duration,
                    down_end,
                )
            )
        cursor = down_end
        remaining_idle_seconds = int((day_end - cursor).total_seconds())
        if remaining_idle_seconds > 0:
            rows["equipment_status_history"].append(
                (line_id, equip_id, "idle", "WAIT", "투입 대기", cursor, day_end, remaining_idle_seconds, day_end)
            )
        return

    if run_minutes > 0:
        run_end = day_start + timedelta(minutes=run_minutes)
        rows["equipment_status_history"].append(
            (line_id, equip_id, "run", None, None, day_start, run_end, run_minutes * 60, run_end)
        )
        cursor = run_end

    if idle_minutes > 0:
        rows["equipment_status_history"].append(
            (line_id, equip_id, "idle", "WAIT", "투입 대기", cursor, day_end, idle_minutes * 60, day_end)
        )


def build_alarm_rows(
    rows: dict[str, list[tuple]],
    ids: dict[str, dict[str, int]],
    active_alarm_rows: list[dict[str, Any]],
    employee_cycle: list[str],
) -> None:
    for idx, alarm in enumerate(active_alarm_rows, start=1):
        rows["alarms"].append(
            (
                ids["lines"][alarm["line_code"]],
                ids["equipments"][alarm["equip_code"]],
                alarm["alarm_code"],
                alarm["alarm_name"],
                alarm["cause_code"],
                alarm["severity"],
                alarm["message"],
                alarm["status"],
                alarm["occurred_at"],
                alarm["cleared_at"],
            )
        )
        handled_by = ids["employees"][employee_cycle[(idx - 1) % len(employee_cycle)]]
        rows["alarm_ack_history"].append(
            (idx, alarm["ack_status"], handled_by, alarm["occurred_at"] + timedelta(minutes=2), alarm["ack_note"])
        )
        rows["event_logs"].append(
            (
                "alarm",
                alarm["severity"],
                ids["lines"][alarm["line_code"]],
                ids["equipments"][alarm["equip_code"]],
                alarm["alarm_name"],
                alarm["message"],
                f"{alarm['alarm_code']} / {alarm['status']}",
                alarm["occurred_at"],
            )
        )


def scenario_alarm_candidates(day: date, scenario_name: str) -> list[tuple[str, str, str, str, str, str, datetime]]:
    candidates: dict[str, list[tuple[str, str, str, str, str, str, datetime]]] = {
        "stable": [
            ("LINE-A", "AOI-01", "SPD-001", "속도 저하 감지", "info", "AOI 처리속도 소폭 저하 감지", local_slot(day, 9, 12)),
        ],
        "watch": [
            ("LINE-D", "REFLOW-01", "QLT-110", "품질 편차 감지", "warning", "리플로우 온도 편차 감지", local_slot(day, 14, 20)),
            ("LINE-A", "AOI-01", "SPD-001", "속도 저하 감지", "info", "AOI 처리속도 소폭 저하 감지", local_slot(day, 10, 5)),
        ],
        "warning": [
            ("LINE-C", "MNT-04", "QLT-201", "불량 증가 조짐", "warning", "LINE C 불량률 상승 조짐 감지", local_slot(day, 11, 15)),
            ("LINE-D", "REFLOW-01", "QLT-144", "품질 편차 초과", "warning", "리플로우 온도 편차로 불량률 상승", local_slot(day, 15, 20)),
            ("LINE-A", "AOI-01", "SPD-001", "속도 저하 감지", "info", "AOI 처리속도 저하 감지", local_slot(day, 13, 10)),
        ],
        "critical": [
            ("LINE-C", "CMP-07", "Q-C-001", "복합 불량 경보", "critical", "SHORT + OPEN 복합 불량 감지 - LINE C, LOT-88421", local_slot(day, 11, 25)),
            ("LINE-C", "REFLOW-01", "Q-C-002", "LOT HOLD 필요", "critical", "LOT-88421 불량률 8% 초과 - HOLD 필요", local_slot(day, 12, 35)),
            ("LINE-D", "REFLOW-01", "QLT-144", "품질 편차 초과", "warning", "라인 D 품질 편차 증가", local_slot(day, 15, 20)),
            ("LINE-A", "AOI-01", "SPD-001", "속도 저하 감지", "warning", "AOI 처리속도 저하 감지", local_slot(day, 16, 10)),
        ],
        "worst": [
            ("LINE-C", "MNT-04", "DT-201", "장비 다운", "critical", "MNT-04 과열 감지 - 즉각 점검 필요", local_slot(day, 11, 50)),
            ("LINE-C", "CMP-07", "Q-C-001", "복합 불량 경보", "critical", "SHORT + OPEN 복합 불량 감지 - LINE C, LOT-88421", local_slot(day, 12, 10)),
            ("LINE-D", "AOI-04", "QLT-220", "SPUR 증가", "warning", "LINE D SPUR 증가 추세 감지", local_slot(day, 15, 20)),
            ("LINE-B", "PRN-02", "QLT-301", "OPEN 증가", "warning", "야간 OPEN 증가 추세 감지", local_slot(day, 19, 10)),
            ("LINE-A", "AOI-01", "SPD-001", "속도 저하 감지", "warning", "AOI 처리속도 저하 감지", local_slot(day, 17, 0)),
        ],
        "recovery": [
            ("LINE-C", "MNT-04", "REC-101", "회복 모니터링", "warning", "라인 C 조치 후 회복 모니터링 중", local_slot(day, 10, 30)),
            ("LINE-D", "REFLOW-01", "QLT-144", "잔여 편차 모니터링", "info", "라인 D 잔여 품질 편차 모니터링", local_slot(day, 14, 10)),
        ],
    }
    return candidates[scenario_name]


def generate_rows(
    ids: dict[str, dict[str, int]],
    start_date: date,
    end_date: date,
    current_kst: datetime,
    rng: random.Random,
) -> dict[str, list[tuple]]:
    factory_id = ids["factories"]["HQ-1"]
    rows = {
        "production_records": [],
        "equipment_status_history": [],
        "inspection_results": [],
        "defect_results": [],
        "alarms": [],
        "alarm_ack_history": [],
        "recheck_queue": [],
        "event_logs": [],
        "line_environment": [],
    }
    schedule = build_scenario_schedule(start_date, end_date, rng)
    employee_cycle = [employee.employee_no for employee in EMPLOYEES]
    hourly_weights = hour_weights()

    total_days = (end_date - start_date).days + 1
    all_alarm_rows: list[dict[str, Any]] = []
    alarm_sequence = 1

    for offset in range(total_days):
        day = start_date + timedelta(days=offset)
        scenario_name = schedule[day]
        scenario = SCENARIOS[scenario_name]
        for line in LINES:
            line_code = line.line_code
            line_id = ids["lines"][line_code]
            weekday_multiplier = WEEKDAY_OUTPUT_MULTIPLIER.get(day.weekday(), 1.0)
            day_noise = rng.uniform(0.95, 1.06)
            line_noise = rng.uniform(0.93, 1.07)
            line_multiplier = scenario.line_output_multiplier[line_code] * weekday_multiplier * day_noise * line_noise
            shift_targets = build_line_shift_targets(rng, line_code, line_multiplier)
            hourly_produced = [0] * len(DAY_SLOT_HOURS)
            for shift_name, shift_total in shift_targets.items():
                shift_hours = SHIFT_HOURS[shift_name]
                shift_hour_weights = normalize_weights([hourly_weights[hour] * rng.uniform(0.72, 1.28) for hour in shift_hours])
                shift_counts = resolve_counts(shift_total, shift_hour_weights)
                for idx, hour in enumerate(shift_hours):
                    hourly_produced[hour] = shift_counts[idx]

            produced_total = sum(hourly_produced)
            inspection_ratio = max(0.90, min(0.995, scenario.inspection_ratio + rng.uniform(-0.01, 0.01)))
            total_ng = 0
            total_good = 0

            prev_defect_rate: float | None = None
            for hour_index, hour in enumerate(DAY_SLOT_HOURS):
                slot_dt = local_slot(day, hour, 15)
                lot_id = line_lot_id(day, line_code, scenario_name, hour_index)
                model_code = MODEL_CODES[(offset + hour_index + LINE_SORT[line_code]) % len(MODEL_CODES)]
                produced_qty = hourly_produced[hour_index]
                sampled_rate = sample_defect_rate(rng, line_code=line_code, scenario_name=scenario_name)
                defect_rate = smooth_defect_rate(prev_defect_rate, sampled_rate)
                prev_defect_rate = defect_rate
                ng_qty = min(produced_qty, int(round(produced_qty * defect_rate)))
                good_qty = max(produced_qty - ng_qty, 0)
                inspected_qty = max(ng_qty, int(round(produced_qty * inspection_ratio)))
                inspected_pass_qty = max(inspected_qty - ng_qty, 0)
                total_ng += ng_qty
                total_good += good_qty

                rows["production_records"].append(
                    (
                        factory_id,
                        line_id,
                        ids["equipments"][PRIMARY_EQUIPMENT[line_code]],
                        lot_id,
                        model_code,
                        day,
                        shift_for_hour(hour),
                        produced_qty,
                        good_qty,
                        ng_qty,
                        slot_dt,
                    )
                )
                rows["inspection_results"].append(
                    (
                        line_id,
                        ids["equipments"][PRIMARY_EQUIPMENT[line_code]],
                        lot_id,
                        model_code,
                        "AOI",
                        inspected_qty,
                        inspected_pass_qty,
                        ng_qty,
                        slot_dt + timedelta(minutes=5),
                    )
                )

                bucket_pattern = resolve_counts(ng_qty, [1, 1, 1, 1, 1, 1])
                defect_equip_codes, defect_equip_weights = line_equipment_weights(
                    rng,
                    line_code,
                    scenario_name=scenario_name,
                )
                defect_equip_ids = [ids["equipments"][code] for code in defect_equip_codes]

                defect_weights = random_defect_weights(
                    rng,
                    line_code=line_code,
                    focus_critical_lot=(lot_id == "LOT-88421"),
                )
                for minute_idx, minute in enumerate([0, 10, 20, 30, 40, 50]):
                    bucket_dt = local_slot(day, hour, minute)
                    bucket_ng = bucket_pattern[minute_idx]
                    if bucket_ng <= 0:
                        continue

                    per_defect = resolve_counts(bucket_ng, defect_weights)
                    for defect_idx, defect in enumerate(DEFECT_DEFS):
                        defect_count = per_defect[defect_idx]
                        if defect_count <= 0:
                            continue
                        cause_text = f"{line.line_name} {defect[1]} 집중 발생"
                        if lot_id == "LOT-88421":
                            cause_text = "LOT-88421 집중 불량"

                        equip_splits = resolve_counts(defect_count, defect_equip_weights)
                        for split_idx, split_count in enumerate(equip_splits):
                            if split_count <= 0:
                                continue
                            rows["defect_results"].append(
                                (
                                    line_id,
                                    defect_equip_ids[split_idx],
                                    lot_id,
                                    model_code,
                                    defect[0],
                                    defect[1],
                                    split_count,
                                    defect[2],
                                    defect[0].upper(),
                                    cause_text,
                                    bucket_dt,
                                )
                            )

            availability_pct = scenario.line_availability_pct[line_code]
            down_started_at: datetime | None = None
            down_reason: str | None = None
            down_minutes: int | None = None
            if line_code == "LINE-C" and scenario_name in {"critical", "worst"}:
                down_started_at = local_slot(day, 12 if scenario_name == "critical" else 11, 40)
                down_reason = "MNT-04 과열 감지"
                down_minutes = 45 if scenario_name == "critical" else 90
            elif line_code == "LINE-D" and scenario_name == "worst":
                down_started_at = local_slot(day, 15, 15)
                down_reason = "품질 편차 확대로 일시 정지"
                down_minutes = 30

            for equipment in [item for item in EQUIPMENTS if item.line_code == line_code]:
                equip_id = ids["equipments"][equipment.equip_code]
                effective_availability = availability_pct
                if equipment.equip_code != PRIMARY_EQUIPMENT[line_code]:
                    effective_availability = min(100.0, availability_pct + 3.0)
                append_status_rows(
                    rows,
                    line_id,
                    equip_id,
                    day,
                    effective_availability,
                    down_reason=down_reason if equipment.equip_code == PRIMARY_EQUIPMENT[line_code] else None,
                    down_started_at=down_started_at if equipment.equip_code == PRIMARY_EQUIPMENT[line_code] else None,
                    down_minutes=down_minutes if equipment.equip_code == PRIMARY_EQUIPMENT[line_code] else None,
                )

            temp_line = Decimal(f"{24.1 + rng.uniform(-0.7, 0.9):.2f}")
            temp_machine = Decimal(f"{66.2 + rng.uniform(-1.1, 1.6):.2f}")
            humidity = Decimal(f"{52.3 + rng.uniform(-3.2, 3.2):.2f}")
            vibration = Decimal(f"{0.24 + rng.uniform(-0.08, 0.10):.2f}")
            if scenario_name in {"critical", "worst"} and line_code == "LINE-C":
                temp_line = Decimal("24.10")
                temp_machine = Decimal("68.40")
                humidity = Decimal("52.30")
                vibration = Decimal("0.41")

            sensor_samples = [
                ("TEMP-LINE", "temperature", temp_line, "°C"),
                (f"TEMP-{PRIMARY_EQUIPMENT[line_code]}", "temperature", temp_machine, "°C"),
                ("HUMIDITY", "humidity", humidity, "%RH"),
                ("VIBRATION", "vibration", vibration, "mm/s"),
            ]
            for sensor_type, metric_name, metric_value, unit in sensor_samples:
                recorded_at = local_slot(day, 14, 40)
                rows["line_environment"].append((line_id, sensor_type, metric_name, metric_value, unit, recorded_at))

            pending_qty = scenario.recheck_counts.get(line_code, 0)
            if pending_qty > 0:
                if line_code == "LINE-C" and scenario_name in {"critical", "worst"}:
                    defect_plan = [
                        ("short", 0.50, "HIGH", "critical", "SHORT 집중 불량"),
                        ("open", 0.30, "HIGH", "critical", "OPEN 복합 불량"),
                        ("spur", 0.20, "MEDIUM", "warning", "SPUR 증가 추세"),
                    ]
                elif line_code == "LINE-D":
                    defect_plan = [
                        ("open", 0.55, "MEDIUM", "warning", "OPEN 재검 필요"),
                        ("spur", 0.25, "MEDIUM", "warning", "SPUR 재검 필요"),
                        ("missing_hole", 0.20, "LOW", "info", "MISSING_HOLE 재검 필요"),
                    ]
                elif line_code == "LINE-B":
                    defect_plan = [
                        ("open", 0.60, "MEDIUM", "warning", "OPEN 재검 필요"),
                        ("mouse_bite", 0.40, "LOW", "info", "MOUSE_BITE 재검 필요"),
                    ]
                else:
                    defect_plan = [
                        ("open", 0.65, "MEDIUM", "warning", f"{line.line_name} OPEN 재검 필요"),
                        ("missing_hole", 0.35, "LOW", "info", f"{line.line_name} MISSING_HOLE 재검 필요"),
                    ]

                split_counts = [max(1, int(round(pending_qty * ratio))) for _, ratio, *_ in defect_plan]
                diff = pending_qty - sum(split_counts)
                if diff != 0:
                    split_counts[0] = max(1, split_counts[0] + diff)

                base_slot = 13
                owner_no = "EMP-2001" if line_code in {"LINE-A", "LINE-C"} else "EMP-2002"
                base_time = (
                    local_slot(day, 11, 40)
                    if line_code == "LINE-C"
                    else local_slot(day, 15, 20)
                    if line_code == "LINE-D"
                    else local_slot(day, 19, 10)
                )

                for idx, (defect_code, _ratio, priority, severity, cause_text) in enumerate(defect_plan):
                    qty = split_counts[idx] if idx < len(split_counts) else 0
                    if qty <= 0:
                        continue

                    lot_id = (
                        "LOT-88421"
                        if line_code == "LINE-C" and scenario_name in {"critical", "worst"} and idx == 0
                        else line_lot_id(day, line_code, scenario_name, base_slot + idx)
                    )
                    queued_at = base_time + timedelta(minutes=idx * 7)
                    recheck_equip_codes, recheck_weights = line_equipment_weights(
                        rng,
                        line_code,
                        scenario_name=scenario_name,
                    )
                    recheck_equip_code = rng.choices(recheck_equip_codes, weights=recheck_weights, k=1)[0]

                    rows["recheck_queue"].append(
                        (
                            lot_id,
                            line_id,
                            ids["equipments"][recheck_equip_code],
                            defect_code,
                            priority,
                            severity,
                            "queued",
                            qty,
                            cause_text,
                            ids["employees"][owner_no],
                            queued_at,
                            None,
                            "문서 기준 QA 재검 시나리오",
                        )
                    )

            rows["event_logs"].append(
                (
                    "production",
                    "info",
                    line_id,
                    ids["equipments"][PRIMARY_EQUIPMENT[line_code]],
                    f"{line.line_name} 생산 집계",
                    f"생산 {produced_total:,} / 양품 {total_good:,} / 불량 {total_ng:,}",
                    scenario_name,
                    local_slot(day, 23, 40),
                )
            )

        for line_code, equip_code, cause_code, alarm_name, severity, message, occurred_at in scenario_alarm_candidates(day, scenario_name)[:scenario.active_alarm_count]:
            alarm_code = f"ALM-{day:%y%m%d}-{alarm_sequence:03d}"
            alarm_sequence += 1
            all_alarm_rows.append(
                {
                    "line_code": line_code,
                    "equip_code": equip_code,
                    "alarm_code": alarm_code,
                    "alarm_name": alarm_name,
                    "cause_code": cause_code,
                    "severity": severity,
                    "message": message,
                    "status": "active" if severity == "critical" else "hold",
                    "occurred_at": occurred_at,
                    "cleared_at": None,
                    "ack_status": "unack" if severity == "critical" else "hold",
                    "ack_note": "현장 대응 필요" if severity == "critical" else "모니터링",
                }
            )

    build_alarm_rows(rows, ids, all_alarm_rows, employee_cycle)
    return rows


def insert_fact_rows(cur: psycopg.Cursor, table_name: str, stmt: str, rows: list[tuple]) -> None:
    if not rows:
        return
    cur.executemany(stmt, rows)
    print(f"{table_name}: inserted {len(rows):,} rows")


def insert_generated_rows(cur: psycopg.Cursor, rows: dict[str, list[tuple]]) -> None:
    insert_fact_rows(
        cur,
        "production_records",
        """
        INSERT INTO wed_dashboard.production_records (
            factory_id, line_id, equip_id, lot_id, model_code, work_date, work_shift,
            produced_qty, good_qty, ng_qty, recorded_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        rows["production_records"],
    )
    insert_fact_rows(
        cur,
        "equipment_status_history",
        """
        INSERT INTO wed_dashboard.equipment_status_history (
            line_id, equip_id, status_code, reason_code, reason_text, started_at,
            ended_at, duration_sec, recorded_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        rows["equipment_status_history"],
    )
    insert_fact_rows(
        cur,
        "inspection_results",
        """
        INSERT INTO wed_dashboard.inspection_results (
            line_id, equip_id, lot_id, model_code, inspection_type, total_checked_qty,
            pass_qty, fail_qty, recorded_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        rows["inspection_results"],
    )
    insert_fact_rows(
        cur,
        "defect_results",
        """
        INSERT INTO wed_dashboard.defect_results (
            line_id, equip_id, lot_id, model_code, defect_code, defect_name, defect_count,
            severity, cause_code, cause_text, recorded_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        rows["defect_results"],
    )
    insert_fact_rows(
        cur,
        "alarms",
        """
        INSERT INTO wed_dashboard.alarms (
            line_id, equip_id, alarm_code, alarm_name, cause_code, severity, message,
            status, occurred_at, cleared_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        rows["alarms"],
    )
    if rows["alarm_ack_history"]:
        cur.execute("SELECT alarm_id FROM wed_dashboard.alarms ORDER BY alarm_id ASC")
        alarm_ids = [alarm_id for (alarm_id,) in cur.fetchall()]
        ack_rows = []
        for ordinal, ack_status, handled_by, handled_at, note in rows["alarm_ack_history"]:
            ack_rows.append((alarm_ids[ordinal - 1], ack_status, handled_by, handled_at, note))
        insert_fact_rows(
            cur,
            "alarm_ack_history",
            """
            INSERT INTO wed_dashboard.alarm_ack_history (
                alarm_id_ref, ack_status, handled_by, handled_at, note
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            ack_rows,
        )
    insert_fact_rows(
        cur,
        "recheck_queue",
        """
        INSERT INTO wed_dashboard.recheck_queue (
            lot_id, line_id, equip_id, defect_code, priority, severity, status,
            count_qty, cause_text, owner_employee_id, queued_at, completed_at, note
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        rows["recheck_queue"],
    )
    insert_fact_rows(
        cur,
        "event_logs",
        """
        INSERT INTO wed_dashboard.event_logs (
            event_type, severity, line_id, equip_id, title, message, meta_text, recorded_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        rows["event_logs"],
    )
    insert_fact_rows(
        cur,
        "line_environment",
        """
        INSERT INTO wed_dashboard.line_environment (
            line_id, sensor_type, metric_name, metric_value, unit, recorded_at
        ) VALUES (%s, %s, %s, %s, %s, %s)
        """,
        rows["line_environment"],
    )


def preview_counts(rows: dict[str, list[tuple]], start_date: date, end_date: date, current_kst: datetime) -> None:
    print("Preview only. No rows were written.")
    print(f"range: {start_date.isoformat()} .. {end_date.isoformat()}")
    print(f"current KST time: {current_kst.isoformat()}")
    for table_name, table_rows in rows.items():
        print(f"{table_name}: {len(table_rows):,} rows")


def ensure_dashboard_dummy_data() -> bool:
    conninfo = psycopg_conninfo(get_database_url())
    rng = random.Random(DEFAULT_SEED)
    current_kst = datetime.now(KST).replace(second=0, microsecond=0)

    with psycopg.connect(conninfo) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT EXISTS (SELECT 1 FROM wed_dashboard.production_records LIMIT 1)")
            has_rows = bool(cur.fetchone()[0])
            if has_rows:
                conn.rollback()
                return False

            ids = ensure_master_data(cur)
            rows = generate_rows(ids, DEFAULT_START_DATE, DEFAULT_END_DATE, current_kst, rng)
            insert_generated_rows(cur, rows)
        conn.commit()
    return True


def main() -> None:
    args = parse_args()
    if args.start_date > args.end_date:
        raise SystemExit("start-date must be on or before end-date")

    rng = random.Random(args.seed)
    current_kst = datetime.now(KST).replace(second=0, microsecond=0)
    conninfo = psycopg_conninfo(get_database_url())

    with psycopg.connect(conninfo) as conn:
        with conn.cursor() as cur:
            if not args.no_truncate:
                truncate_dashboard_tables(cur)

            ids = ensure_master_data(cur)
            rows = generate_rows(ids, args.start_date, args.end_date, current_kst, rng)

            if not args.apply:
                conn.rollback()
                preview_counts(rows, args.start_date, args.end_date, current_kst)
                return

            insert_generated_rows(cur, rows)
        conn.commit()

    print("wed_dashboard dummy data generation completed successfully.")
    print(f"range: {args.start_date.isoformat()} .. {args.end_date.isoformat()}")
    print(f"seed: {args.seed}")


if __name__ == "__main__":
    main()
