"""dashboard 서비스 조합 로직.

repository가 가져온 원천 데이터를 화면별 bundle 형태로 가공하고,
KPI 응답/detail 응답/web_dashboard 응답 계약을 맞추는 계층이다.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from fastapi import HTTPException

from src.modules.dashboard.repository import (
    DashboardLiveSnapshot,
    WebDashboardSnapshot,
    get_employee_line_code,
    get_web_dashboard_snapshot,
    get_dashboard_live_snapshot,
    get_alarm_detail,
    get_defect_detail,
    get_lot_detail,
    get_request_detail,
)
from src.modules.dashboard.schemas import (
    AssistiveItem,
    DashboardAssistiveGroup,
    DashboardDetailRequest,
    DashboardDetailResponse,
    DashboardDatasetsResponse,
    DashboardKPIResponse,
    DashboardKpiGroup,
    KpiItem,
)

KST = timezone(timedelta(hours=9))
TIMEZONE_NAME = "Asia/Seoul"
STALE_AFTER_HOURS = 6

SCREEN_ID_MAP = {
    "worker": "SCR-001",
    "qa": "SCR-002",
    "manager": "SCR-003",
    "promo": "SCR-004",
}
VALID_SCREENS = set(SCREEN_ID_MAP)
VALID_TARGET_TYPES = {"line", "equipment", "lot", "defect", "inspection", "alarm", "event", "shift"}
COMMON_DETAIL_IDS = {"common.alarm.detail"}
SCREEN_DETAIL_IDS = {
    "worker": {"worker.line.detail", "worker.equipment.detail", "worker.event.detail", "worker.action.detail"},
    "qa": {"qa.defect.detail", "qa.reinspection.queue", "qa.inspection.detail", "qa.lot.detail", "qa.cause.detail", "qa.recheck.detail", "qa.trend.detail", "qa.issue.detail"},
    "manager": {"manager.line.detail", "manager.risk.detail", "manager.bottleneck.detail", "manager.plan.detail", "manager.pareto.detail", "manager.event.detail", "manager.action.detail", "manager.alarm.detail"},
    "promo": set(),
}
REQUIRED_LIVE_DATASETS = {
    "worker": {"statusGrid", "activeAlarms", "eventTimeline", "ngTrend10m", "topDefects", "ngLogs", "downtimeHistory", "pendingActions", "handoffLogs"},
    "qa": {"defectTrend", "topDefects", "ngRows", "recheckQueue", "handoffLogs", "summaryLine"},
    "manager": {"statusGrid", "activeAlarms", "hourly", "lineCompare", "statusDistribution", "downtimePareto", "riskLines", "pendingActions", "handoffLogs", "recommendation"},
    "promo": {"statusGrid", "lineTrend", "top3", "topIssues", "rollingMessage"},
}
REQUIRED_LIVE_KPIS = {
    "worker": {"worker_recent_10m_ng", "worker_total_produced", "worker_achievement", "worker_attention_count"},
    "qa": {"qa_defect_rate", "qa_recheck", "qa_summary"},
    "manager": {"mgr_oee", "mgr_achievement", "mgr_expected_output"},
    "promo": {"promo_total", "promo_achievement", "promo_yield"},
}
DEFECT_COLORS = {
    "short": "#f25f5c",
    "open": "#ff8c42",
    "mouse_bite": "#ef476f",
    "spur": "#ffd166",
    "missing_hole": "#5dade2",
    "spurious_copper": "#2ec4b6",
}
DEFECT_SLOT_ORDER = [
    "short",
    "open",
    "spur",
    "mouse_bite",
    "spurious_copper",
    "missing_hole",
]
DAY_PLAN_TOTAL = 40000
DAY_MINUTES = 24 * 60
SCENARIO_START_DATE = date(2026, 3, 20)
SCENARIO_END_DATE = date(2026, 3, 25)
SCENARIO_DAY_COUNT = (SCENARIO_END_DATE - SCENARIO_START_DATE).days + 1
LINE_PLAN_SHARE = {
    "LINE-A": 0.26,
    "LINE-B": 0.30,
    "LINE-C": 0.22,
    "LINE-D": 0.22,
}


# 공통 시간 / 날짜 유틸
def _now() -> datetime:
    return datetime.now(KST)


def _now_iso() -> str:
    return _now().isoformat()


def _coerce_filter_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _map_to_scenario_date(value: date) -> date:
    # 운영/더미 공통으로 사용자가 선택한 날짜를 그대로 조회 기준으로 사용한다.
    return value


def _resolve_dashboard_dates(filters: dict[str, Any]) -> tuple[date, date]:
    requested = (
        _coerce_filter_date(filters.get("date_to"))
        or _coerce_filter_date(filters.get("date_from"))
        or _now().date()
    )
    return requested, _map_to_scenario_date(requested)


def _resolve_period_range(filters: dict[str, Any]) -> tuple[date, date] | None:
    date_from = _coerce_filter_date(filters.get("date_from"))
    date_to = _coerce_filter_date(filters.get("date_to"))
    if not date_from or not date_to:
        return None
    if date_from > date_to:
        raise HTTPException(status_code=400, detail={"code": "invalid_date_range", "message": "date_from must be earlier than or equal to date_to"})
    if (date_to - date_from).days + 1 > 31:
        raise HTTPException(status_code=400, detail={"code": "date_range_too_large", "message": "Maximum date range is 31 days"})
    if date_from == date_to:
        return None
    return (date_from, date_to)


# worker는 로그인 사용자 라인으로 강제 필터링
def _enforce_worker_line_filter(filters: dict[str, Any]) -> dict[str, Any]:
    current_user = filters.get("current_user")
    if current_user is None:
        return filters

    role = str(getattr(current_user, "role", "") or "").strip().lower()
    if role not in {"worker", "operator"}:
        return filters

    employee_no = str(getattr(current_user, "employee_no", "") or "").strip()
    if not employee_no:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "worker_identity_missing",
                "message": "작업자 인증 정보가 없습니다. 다시 로그인해주세요.",
            },
        )

    line_code = get_employee_line_code(employee_no)
    if not line_code:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "worker_line_not_assigned",
                "message": "작업자 라인 정보가 없습니다. 관리자에게 라인 배정을 요청하세요.",
            },
        )

    filters["line"] = line_code
    return filters


# 반복적으로 쓰는 보조 유틸
def _iter_dates(start: date, end: date) -> list[date]:
    days: list[date] = []
    cursor = start
    while cursor <= end:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def _apply_web_snapshot_meta(bundle: dict[str, Any], snap: WebDashboardSnapshot, requested_date: date, scenario_date: date, **filters: Any) -> None:
    # repository snapshot에서 받은 시간/라인 정보를 화면 bundle meta에 덮어쓴다.
    bundle["meta"] = _web_dashboard_meta(
        bundle["meta"]["screen"],
        effective_at=snap.effective_at.isoformat(),
        updated_at=_now_iso(),
        requested_date=requested_date.isoformat(),
        scenario_date=scenario_date.isoformat(),
        **filters,
    )
    if not bundle["meta"].get("line"):
        bundle["meta"]["line"] = (
            bundle.get("lineTemperature", {}).get("line")
            or bundle["meta"].get("filters", {}).get("line")
        )


def _iso_from_date(value: date | None) -> str | None:
    if value is None:
        return None
    return datetime.combine(value, time(23, 59, 59), tzinfo=KST).isoformat()


def _summary_rate(summary: dict[str, Any]) -> float | None:
    total = int(summary.get("total_rows") or 0)
    ng = int(summary.get("ng_rows") or 0)
    if total <= 0:
        return None
    return round((ng / total) * 100, 2)


def _is_delayed(latest_date: date | None) -> bool:
    if latest_date is None:
        return False
    latest_dt = datetime.combine(latest_date, time(23, 59, 59), tzinfo=KST)
    return (_now() - latest_dt) > timedelta(hours=STALE_AFTER_HOURS)


def _base_meta(
    screen: str,
    *,
    data_mode: str,
    effective_at: str | None,
    updated_at: str | None,
    is_partial: bool,
    is_delayed: bool,
) -> dict[str, Any]:
    return {
        "screen": screen,
        "screenId": SCREEN_ID_MAP[screen],
        "timezone": TIMEZONE_NAME,
        "dataMode": data_mode,
        "effectiveAt": effective_at or _now_iso(),
        "updatedAt": updated_at or effective_at or _now_iso(),
        "isPartial": is_partial,
        "isDelayed": is_delayed,
        "staleLabel": "지연" if is_delayed else "정상",
    }


# 상태 확인 / 상세 요청 검증
def dashboard_status_placeholder() -> dict[str, Any]:
    snapshot = get_dashboard_live_snapshot()
    return {
        "module": "dashboard",
        "message": "Dashboard API is ready.",
        "screens": sorted(VALID_SCREENS),
        "detailEndpoint": "/api/v1/dashboard/detail",
        "liveSources": {
            "vision_result": bool(snapshot.latest_date),
            "latestDate": str(snapshot.latest_date) if snapshot.latest_date else None,
        },
    }


def _canonical_target_type(value: str) -> str:
    raw = str(value or "").strip().lower()
    alias = {
        "line": "line",
        "lines": "line",
        "equipment": "equipment",
        "equip": "equipment",
        "machine": "equipment",
        "lot": "lot",
        "defect": "defect",
        "inspection": "inspection",
        "inspect": "inspection",
        "alarm": "alarm",
        "event": "event",
        "shift": "shift",
    }
    normalized = alias.get(raw, raw)
    if normalized not in VALID_TARGET_TYPES:
        raise HTTPException(status_code=400, detail={"code": "unsupported", "message": f"Unsupported targetType: {value}"})
    return normalized


def _validate_detail_id(screen: str, detail_id: str) -> str:
    normalized = str(detail_id or "").strip()
    allowed = SCREEN_DETAIL_IDS.get(screen, set()) | COMMON_DETAIL_IDS
    if normalized not in allowed:
        raise HTTPException(status_code=400, detail={"code": "unsupported", "message": f"Unsupported detailId for {screen}: {detail_id}"})
    return normalized


# 화면 계산용 색상/우선순위 유틸
def _defect_color(defect_type: str) -> str:
    return DEFECT_COLORS.get(str(defect_type or "").strip().lower(), "#8fa6bf")


def _build_fixed_defect_slots(rows: list[dict[str, Any]] | None, limit: int = 6) -> list[dict[str, Any]]:
    slot_codes = DEFECT_SLOT_ORDER[: max(0, limit)]
    counts: dict[str, int] = {}
    names: dict[str, str] = {}

    for row in rows or []:
        code = str(row.get("defect_code") or "").strip().lower().replace(" ", "_")
        if not code:
            continue
        counts[code] = counts.get(code, 0) + int(row.get("cnt") or 0)
        display_name = str(row.get("defect_name") or "").strip()
        if display_name:
            names[code] = display_name

    return [
        {
            "code": code,
            "name": names.get(code) or code,
            "count": counts.get(code, 0),
            "color": DEFECT_COLORS.get(code, "#6B7280"),
        }
        for code in slot_codes
    ]


def _priority(ng_rows: int, avg_confidence: float | None) -> str:
    if ng_rows >= 8 or (avg_confidence is not None and avg_confidence < 0.87):
        return "P1"
    if ng_rows >= 4 or (avg_confidence is not None and avg_confidence < 0.92):
        return "P2"
    return "P3"


def _copy_item(item: KpiItem) -> KpiItem:
    return KpiItem(**item.model_dump())


def _copy_assistive(item: AssistiveItem) -> AssistiveItem:
    return AssistiveItem(**item.model_dump())


def _build_mock_bundles() -> dict[str, dict[str, Any]]:
    worker_datasets = {
        "statusGrid": [
            {"lineId": "LINE A", "equipmentId": "AOI-01", "status": "RUN", "severity": "info", "updatedAt": "2026-03-15T08:00:08+09:00", "sourceType": "actual", "targetType": "equipment", "targetId": "AOI-01"},
            {"lineId": "LINE A", "equipmentId": "DRV-01", "status": "RUN", "severity": "info", "updatedAt": "2026-03-15T08:00:08+09:00", "sourceType": "actual", "targetType": "equipment", "targetId": "DRV-01"},
            {"lineId": "LINE B", "equipmentId": "PRN-02", "status": "IDLE", "severity": "warning", "updatedAt": "2026-03-15T07:58:42+09:00", "sourceType": "derived", "targetType": "equipment", "targetId": "PRN-02"},
            {"lineId": "LINE C", "equipmentId": "MNT-04", "status": "DOWN", "severity": "critical", "updatedAt": "2026-03-15T07:55:18+09:00", "sourceType": "actual", "targetType": "equipment", "targetId": "MNT-04"},
        ],
        "activeAlarms": [
            {"alarmId": "ALM-2401", "severity": "critical", "status": "DOWN", "occurredAt": "2026-03-15T07:55:18+09:00", "lineId": "LINE C", "equipmentId": "MNT-04", "causeCode": "DT-201", "ackState": "UNACK", "sourceType": "actual", "targetType": "alarm", "targetId": "ALM-2401"},
            {"alarmId": "ALM-2402", "severity": "warning", "status": "IDLE", "occurredAt": "2026-03-15T07:58:42+09:00", "lineId": "LINE B", "equipmentId": "PRN-02", "causeCode": "MAT-103", "ackState": "HOLD", "sourceType": "derived", "targetType": "alarm", "targetId": "ALM-2402"},
        ],
        "eventTimeline": [
            {"time": "08:00", "category": "알람", "title": "LINE C MNT-04 다운", "detailId": "worker.event.detail", "targetType": "event", "targetId": "ALM-2401"},
            {"time": "07:58", "category": "조치", "title": "자재 투입 대기 확인", "detailId": "worker.event.detail", "targetType": "event", "targetId": "ALM-2402"},
        ],
        "ngTrend10m": [{"time": "07:52", "ng": 8}, {"time": "07:54", "ng": 9}, {"time": "07:56", "ng": 10}, {"time": "07:58", "ng": 11}, {"time": "08:00", "ng": 12}],
        "topDefects": [{"class_name": "short", "count": 180, "color": "#f25f5c"}, {"class_name": "open", "count": 120, "color": "#ff8c42"}, {"class_name": "spur", "count": 95, "color": "#ffd166"}],
        "ngLogs": [{"time": "2026-03-15T08:00:41+09:00", "line": "LINE D", "cls": "open", "conf": 83}, {"time": "2026-03-15T07:59:21+09:00", "line": "LINE B", "cls": "short", "conf": 97}],
        "downtimeHistory": [{"startedAt": "07:55", "lineId": "LINE C", "equipmentId": "MNT-04", "reason": "헤드 정렬 오차", "restartedAt": "-"}],
        "pendingActions": [{"owner": "A조", "title": "미조치 알람 2건", "dueAt": "즉시", "targetType": "alarm", "targetId": "ALM-2401"}],
        "handoffLogs": [{"actionId": "ACT-1001", "targetId": "ALM-2401", "actionType": "조치 등록", "memo": "MNT 헤드 캘리브레이션 요청", "actor": "Kim", "shift": "A", "createdAt": "2026-03-15T07:57:10+09:00", "handoffStatus": "진행중"}],
    }
    qa_datasets = {
        "defectTrend": [{"time": "04:00", "actual": 2.7, "predicted": 2.9}, {"time": "05:00", "actual": 3.1, "predicted": 3.4}, {"time": "06:00", "actual": 3.3, "predicted": 3.7}, {"time": "07:00", "actual": 3.0, "predicted": 3.5}, {"time": "08:00", "actual": 2.8, "predicted": 3.2}],
        "topDefects": [{"class_name": "short", "count": 312, "color": "#f25f5c", "causeCode": "DEF-011"}, {"class_name": "open", "count": 168, "color": "#ff8c42", "causeCode": "DEF-024"}, {"class_name": "spur", "count": 141, "color": "#ffd166", "causeCode": "DEF-031"}],
        "ngRows": [{"detectedAt": "2026-03-15T07:57:21+09:00", "lineName": "LINE D", "boardId": "BRD-10211", "lotId": "LOT-88421", "equipmentId": "AOI-07", "defectType": "open", "defectClass": "open", "confidencePct": 83, "occurredAt": "2026-03-15T07:57:21+09:00", "targetType": "lot", "targetId": "LOT-88421"}],
        "recheckQueue": [{"inspectionId": "INSP-2002", "lotId": "LOT-88421", "defectClass": "open", "queuedAt": "2026-03-15T07:58:20+09:00", "priority": "P1", "recheckStatus": "대기", "owner": "Park"}],
        "handoffLogs": [{"actionId": "QA-1001", "targetId": "INSP-2002", "actionType": "재검 등록", "memo": "AOI 원본 이미지 재판독", "actor": "Park", "shift": "A", "createdAt": "2026-03-15T07:58:30+09:00", "handoffStatus": "진행중"}],
        "summaryLine": "재검 우선: 신뢰도 90% 미만 24건",
        # qa.issue.detail 렌더러(renderQaIssueDetail)가 activeAlarms 접근 — QA 화면 품질 이슈 알람 부분 공유
        "activeAlarms": [
            {"alarmId": "ALM-2401", "severity": "critical", "status": "DOWN", "occurredAt": "2026-03-15T07:55:18+09:00", "lineId": "LINE C", "equipmentId": "MNT-04", "causeCode": "DT-201", "ackState": "UNACK", "sourceType": "actual", "targetType": "alarm", "targetId": "ALM-2401"},
            {"alarmId": "ALM-2403", "severity": "warning", "status": "IDLE", "occurredAt": "2026-03-15T07:57:04+09:00", "lineId": "LINE D", "equipmentId": "CMP-07", "causeCode": "QLT-144", "ackState": "ACK", "sourceType": "derived", "targetType": "alarm", "targetId": "ALM-2403"},
        ],
        "pendingActions": [
            {"title": "재검 대기 초과", "dueAt": "즉시", "targetType": "lot", "targetId": "LOT-88421"},
        ],
    }
    manager_datasets = {
        "statusGrid": [
            {"lineId": "LINE A", "equipmentId": "AOI-01", "status": "RUN", "severity": "info", "updatedAt": "2026-03-15T08:00:08+09:00", "sourceType": "actual", "targetType": "equipment", "targetId": "AOI-01"},
            {"lineId": "LINE C", "equipmentId": "MNT-04", "status": "DOWN", "severity": "critical", "updatedAt": "2026-03-15T07:55:18+09:00", "sourceType": "actual", "targetType": "equipment", "targetId": "MNT-04"},
        ],
        "activeAlarms": [{"alarmId": "ALM-2401", "severity": "critical", "status": "DOWN", "occurredAt": "2026-03-15T07:55:18+09:00", "lineId": "LINE C", "equipmentId": "MNT-04", "causeCode": "DT-201", "ackState": "UNACK", "sourceType": "actual", "targetType": "alarm", "targetId": "ALM-2401"}],
        "hourly": [{"time": "06:00", "produced": 1410, "defectRate": 2.9, "target": 1300, "forecast": 1350}, {"time": "07:00", "produced": 1210, "defectRate": 3.2, "target": 1300, "forecast": 1140}, {"time": "08:00", "produced": 980, "defectRate": 3.4, "target": 1300, "forecast": 1020}],
        "lineCompare": [{"line": "LINE A", "actual": 5520, "plan": 6000}, {"line": "LINE C", "actual": 3980, "plan": 6000}],
        "statusDistribution": [{"label": "가동중", "value": 2, "color": "#2ec4b6"}, {"label": "대기", "value": 1, "color": "#ffd166"}, {"label": "정지", "value": 1, "color": "#ef476f"}],
        "downtimePareto": [{"causeCode": "DT-201", "downtimeMinutes": 96, "occurrenceCount": 4, "lineId": "LINE C", "timeRange": "TODAY"}],
        "riskLines": [{"lineId": "LINE C", "riskScore": 87, "summary": "다운타임과 알람 동시 증가"}],
        "pendingActions": [{"kind": "미해결 알람", "count": 2, "summary": "Critical 1 / Warning 1"}],
        "handoffLogs": [{"actionId": "ACT-2001", "targetId": "ALM-2401", "actionType": "보전 호출", "memo": "라인 C MNT-04 긴급 호출", "actor": "Han", "shift": "A", "createdAt": "2026-03-15T07:56:00+09:00", "handoffStatus": "진행중"}],
        "recommendation": "라인 C 점검 인력 우선 배치",
    }
    promo_datasets = {
        "statusGrid": [
            {"lineId": "LINE A", "equipmentId": "A", "status": "RUN", "severity": "info", "updatedAt": "2026-03-15T08:00:08+09:00", "sourceType": "actual"},
            {"lineId": "LINE C", "equipmentId": "C", "status": "DOWN", "severity": "critical", "updatedAt": "2026-03-15T07:55:18+09:00", "sourceType": "actual"},
        ],
        "lineTrend": [{"time": "06:00", "produced": 1410}, {"time": "07:00", "produced": 1210}, {"time": "08:00", "produced": 980}],
        "top3": [{"class_name": "short", "count": 312, "color": "#f25f5c"}, {"class_name": "open", "count": 168, "color": "#ff8c42"}, {"class_name": "spur", "count": 141, "color": "#ffd166"}],
        "topIssues": [{"rank": 1, "title": "LINE C 다운 지속", "summary": "MNT-04 5분 이상 정지"}],
        "rollingMessage": "현재 주의 포인트: 라인 C 다운타임 증가",
    }

    return {
        "worker": {
            "kpis": DashboardKpiGroup(items=[
                KpiItem(key="worker_recent_10m_ng", label="최근 10분 NG", value=12, unit="건", sourceType="actual", dataMode="live", detailId="worker.equipment.detail", targetType="equipment", targetId="AOI-01", clickable=True),
                KpiItem(key="worker_total_produced", label="누적 생산량", value=13200, unit="pcs", sourceType="actual", dataMode="live"),
                KpiItem(key="worker_achievement", label="목표 달성률", value=66.0, unit="%", sourceType="derived", dataMode="live"),
                KpiItem(key="worker_attention_count", label="현재 확인 필요 건수", value=2, unit="건", sourceType="derived", dataMode="live", detailId="common.alarm.detail", targetType="alarm", targetId="ALM-2401", clickable=True),
            ]),
            "assistive": DashboardAssistiveGroup(items=[AssistiveItem(key="worker_ml_hint", label="ML 이상 징후", value="라인 C 10분 내 NG 증가 위험", sourceType="simulated", dataMode="live", reasonSummary="최근 10분 NG 상승 패턴", confidence=0.71, severity="warning", status="warning")]),
            "datasets": worker_datasets,
        },
        "qa": {
            "kpis": DashboardKpiGroup(items=[
                KpiItem(key="qa_defect_rate", label="현재 불량률", value=4.2, unit="%", sourceType="derived", dataMode="live"),
                KpiItem(key="qa_recheck", label="재검 필요 수량", value=24, unit="건", sourceType="derived", dataMode="live", detailId="qa.reinspection.queue", targetType="lot", targetId="LOT-88421", clickable=True),
                KpiItem(key="qa_summary", label="검사 현황 요약", value={"totalInspected": 8420, "okCount": 8065, "ngCount": 355}, sourceType="actual", dataMode="live"),
            ]),
            "assistive": DashboardAssistiveGroup(items=[
                AssistiveItem(key="qa_alert_status", label="품질 경보", value="warning", sourceType="derived", dataMode="live", severity="warning", status="warning"),
                AssistiveItem(key="qa_pattern_hint", label="패턴 탐지", value="라인 D 급증 구간 감지", sourceType="predicted", dataMode="live", reasonSummary="동일 모델 반복 패턴", detailId="qa.defect.detail", targetType="defect", targetId="open", clickable=True),
            ]),
            "datasets": qa_datasets,
        },
        "manager": {
            "kpis": DashboardKpiGroup(items=[
                KpiItem(key="mgr_oee", label="전체 라인 OEE", value=71.2, unit="%", sourceType="derived", dataMode="live"),
                KpiItem(key="mgr_achievement", label="목표 달성률", value=66.0, unit="%", sourceType="derived", dataMode="live"),
                KpiItem(key="mgr_expected_output", label="예상 종료 생산량", value=18600, unit="pcs", sourceType="derived", dataMode="live"),
            ]),
            "assistive": DashboardAssistiveGroup(items=[AssistiveItem(key="mgr_risk", label="운영 리스크 수준", value=54, sourceType="simulated", dataMode="live", reasonSummary="라인 C,D 생산 편차 확대", confidence=0.68, severity="warning", status="warning", detailId="manager.risk.detail", targetType="line", targetId="LINE C", clickable=True)]),
            "datasets": manager_datasets,
        },
        "promo": {
            "kpis": DashboardKpiGroup(items=[
                KpiItem(key="promo_total", label="오늘 총 생산량", value=13200, unit="pcs", sourceType="actual", dataMode="live"),
                KpiItem(key="promo_achievement", label="목표 달성률", value=66.0, unit="%", sourceType="derived", dataMode="live"),
                KpiItem(key="promo_yield", label="당일 양품률", value=95.8, unit="%", sourceType="derived", dataMode="live"),
            ]),
            "assistive": DashboardAssistiveGroup(items=[]),
            "datasets": promo_datasets,
        },
    }


MOCK_BUNDLES = _build_mock_bundles()


def _copy_mock_bundle(screen: str) -> dict[str, Any]:
    bundle = MOCK_BUNDLES[screen]
    return {
        "kpis": DashboardKpiGroup(items=[_copy_item(item) for item in bundle["kpis"].items]),
        "assistive": DashboardAssistiveGroup(items=[_copy_assistive(item) for item in bundle["assistive"].items]),
        "datasets": {**bundle["datasets"]},
    }


def _ensure_screen(screen: str) -> str:
    if screen not in VALID_SCREENS:
        raise HTTPException(status_code=400, detail={"code": "unsupported", "message": f"Unsupported screen: {screen}"})
    return screen


def _build_top_defects(snapshot: DashboardLiveSnapshot, limit: int = 5) -> list[dict[str, Any]]:
    return [
        {
            "class_name": row["class_name"],
            "count": int(row["count"] or 0),
            "color": _defect_color(row["defect_type"]),
            "causeCode": row["defect_type"],
        }
        for row in snapshot.top_defects[:limit]
    ]


def _build_recent_ng_rows(snapshot: DashboardLiveSnapshot) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in snapshot.recent_ng_rows:
        request_id = str(row.get("request_id") or "").strip()
        rows.append(
            {
                "detectedAt": _iso_from_date(row.get("created_at")),
                "lineName": "",
                "boardId": request_id,
                "lotId": request_id,
                "equipmentId": "",
                "defectType": row.get("defect_type") or "unknown",
                "defectClass": row.get("defect_type") or "unknown",
                "confidencePct": round(float(row.get("confidence") or 0) * 100, 1),
                "occurredAt": _iso_from_date(row.get("created_at")),
                "targetType": "lot",
                "targetId": request_id,
            }
        )
    return rows


def _build_recheck_queue(snapshot: DashboardLiveSnapshot) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in snapshot.request_rollups[:10]:
        request_id = str(row.get("request_id") or "").strip()
        if not request_id:
            continue
        avg_conf = float(row.get("avg_confidence") or 0) if row.get("avg_confidence") is not None else None
        first_defect = str(row.get("defect_types") or "unknown").split(",")[0].strip() or "unknown"
        items.append(
            {
                "inspectionId": request_id,
                "lotId": request_id,
                "defectClass": first_defect,
                "queuedAt": _iso_from_date(row.get("created_at")),
                "priority": _priority(int(row.get("ng_rows") or 0), avg_conf),
                "recheckStatus": "대기",
                "owner": "",
            }
        )
    return items


def _build_defect_trend(snapshot: DashboardLiveSnapshot) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in snapshot.defect_trend:
        total_rows = int(row.get("total_rows") or 0)
        ng_rows = int(row.get("ng_rows") or 0)
        actual = round((ng_rows / total_rows) * 100, 2) if total_rows else 0
        rows.append({"time": str(row.get("created_at")), "actual": actual, "predicted": None})
    return rows


def _build_daily_volume_trend(snapshot: DashboardLiveSnapshot) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in snapshot.defect_trend:
        rows.append({"time": str(row.get("created_at")), "produced": int(row.get("request_count") or row.get("total_rows") or 0)})
    return rows


def _build_hourly_proxy(snapshot: DashboardLiveSnapshot) -> list[dict[str, Any]]:
    if snapshot.hourly_rollups:
        rows: list[dict[str, Any]] = []
        for row in snapshot.hourly_rollups:
            total_rows = int(row.get("total_rows") or 0)
            ng_rows = int(row.get("ng_rows") or 0)
            produced = int(row.get("request_count") or 0)
            defect_rate = round((ng_rows / total_rows) * 100, 2) if total_rows else 0
            rows.append({"time": str(row.get("bucket")), "produced": produced, "defectRate": defect_rate, "target": None, "forecast": None})
        return rows
    rows: list[dict[str, Any]] = []
    for row in snapshot.defect_trend:
        total_rows = int(row.get("total_rows") or 0)
        ng_rows = int(row.get("ng_rows") or 0)
        produced = int(row.get("request_count") or 0)
        defect_rate = round((ng_rows / total_rows) * 100, 2) if total_rows else 0
        rows.append({"time": str(row.get("created_at")), "produced": produced, "defectRate": defect_rate, "target": None, "forecast": None})
    return rows


def _build_ng_10m(snapshot: DashboardLiveSnapshot) -> list[dict[str, Any]]:
    if snapshot.minute10_rollups:
        return [{"time": str(row.get("bucket")), "ng": int(row.get("ng_rows") or 0)} for row in snapshot.minute10_rollups[-6:]]
    return []


def _build_worker_live(bundle: dict[str, Any], snapshot: DashboardLiveSnapshot) -> tuple[set[str], set[str]]:
    datasets = bundle["datasets"]
    live_dataset_keys: set[str] = set()
    live_kpi_keys: set[str] = set()

    ng10 = _build_ng_10m(snapshot)
    if ng10:
        datasets["ngTrend10m"] = ng10
        recent = next((item for item in bundle["kpis"].items if item.key == "worker_recent_10m_ng"), None)
        if recent:
            recent.value = int(ng10[-1]["ng"])
            recent.sourceType = "actual"
            live_kpi_keys.add("worker_recent_10m_ng")
        live_dataset_keys.add("ngTrend10m")

    if snapshot.top_defects:
        datasets["topDefects"] = _build_top_defects(snapshot, limit=3)
        live_dataset_keys.add("topDefects")
    if snapshot.recent_ng_rows:
        datasets["ngLogs"] = [
            {
                "time": _iso_from_date(row.get("created_at")),
                "line": "",
                "cls": row.get("defect_type") or "unknown",
                "conf": round(float(row.get("confidence") or 0) * 100, 1),
            }
            for row in snapshot.recent_ng_rows[:10]
        ]
        datasets["eventTimeline"] = [
            {
                "time": str(row.get("created_at")),
                "category": "검사",
                "title": f"{row.get('defect_type') or 'unknown'} 검출 / {row.get('request_id')}",
                "detailId": "worker.event.detail",
                "targetType": "event",
                "targetId": row.get("request_id"),
            }
            for row in snapshot.recent_ng_rows[:8]
        ]
        live_dataset_keys.update({"ngLogs", "eventTimeline"})

    if snapshot.low_conf_rows:
        datasets["pendingActions"] = [
            {
                "owner": "",
                "title": f"재검 필요 / {row.get('defect_type') or 'unknown'}",
                "dueAt": "즉시",
                "targetType": "event",
                "targetId": row.get("request_id"),
            }
            for row in snapshot.low_conf_rows[:6]
        ]
        attention = next((item for item in bundle["kpis"].items if item.key == "worker_attention_count"), None)
        if attention:
            unique_requests = {str(row.get("request_id")) for row in snapshot.low_conf_rows if row.get("request_id")}
            attention.value = len(unique_requests)
            attention.sourceType = "actual"
            attention.targetType = "event"
            attention.targetId = next(iter(unique_requests)) if unique_requests else None
            attention.detailId = "worker.event.detail"
            attention.clickable = bool(unique_requests)
            live_kpi_keys.add("worker_attention_count")
        live_dataset_keys.add("pendingActions")

    if snapshot.top_defects:
        hint = next((item for item in bundle["assistive"].items if item.key == "worker_ml_hint"), None)
        top = snapshot.top_defects[0]
        if hint:
            hint.value = f"{top['class_name']} 발생 {int(top['count'])}건"
            hint.reasonSummary = f"vision_result 기준 최신 집계 / 평균 confidence {top['avg_confidence']}"
            hint.sourceType = "actual"
            hint.status = "warning"
            hint.severity = "warning"

    return live_dataset_keys, live_kpi_keys


def _build_qa_live(bundle: dict[str, Any], snapshot: DashboardLiveSnapshot) -> tuple[set[str], set[str]]:
    datasets = bundle["datasets"]
    live_dataset_keys: set[str] = set()
    live_kpi_keys: set[str] = set()

    rate = _summary_rate(snapshot.summary)
    recheck_count = len({str(row.get("request_id")) for row in snapshot.low_conf_rows if row.get("request_id")})
    total = int(snapshot.summary.get("total_rows") or 0)
    ok = int(snapshot.summary.get("ok_rows") or 0)
    ng = int(snapshot.summary.get("ng_rows") or 0)

    for item in bundle["kpis"].items:
        if item.key == "qa_defect_rate" and rate is not None:
            item.value = rate
            item.sourceType = "actual"
            live_kpi_keys.add(item.key)
        elif item.key == "qa_recheck":
            item.value = recheck_count
            item.sourceType = "actual"
            item.targetType = "lot"
            item.targetId = snapshot.request_rollups[0]["request_id"] if snapshot.request_rollups else None
            item.detailId = "qa.reinspection.queue"
            item.clickable = bool(snapshot.request_rollups)
            live_kpi_keys.add(item.key)
        elif item.key == "qa_summary":
            item.value = {"totalInspected": total, "okCount": ok, "ngCount": ng}
            item.sourceType = "actual"
            live_kpi_keys.add(item.key)

    if snapshot.defect_trend:
        datasets["defectTrend"] = _build_defect_trend(snapshot)
        live_dataset_keys.add("defectTrend")
    if snapshot.top_defects:
        datasets["topDefects"] = _build_top_defects(snapshot, limit=5)
        live_dataset_keys.add("topDefects")
    if snapshot.recent_ng_rows:
        datasets["ngRows"] = _build_recent_ng_rows(snapshot)
        live_dataset_keys.add("ngRows")
    if snapshot.request_rollups:
        datasets["recheckQueue"] = _build_recheck_queue(snapshot)
        live_dataset_keys.add("recheckQueue")
    if snapshot.low_conf_rows:
        datasets["summaryLine"] = f"재검 우선: 신뢰도 90% 미만 {len(snapshot.low_conf_rows)}건"
        live_dataset_keys.add("summaryLine")

    for item in bundle["assistive"].items:
        if item.key == "qa_alert_status" and rate is not None:
            status = "critical" if rate >= 4 else "warning" if rate >= 2 else "normal"
            item.value = status
            item.status = status
            item.severity = "critical" if rate >= 4 else "warning" if rate >= 2 else "info"
            item.sourceType = "actual"
        elif item.key == "qa_pattern_hint" and snapshot.top_defects:
            top = snapshot.top_defects[0]
            item.value = f"{top['class_name']} 최다 발생"
            item.reasonSummary = f"최신 집계 기준 {int(top['count'])}건 / 평균 confidence {top['avg_confidence']}"
            item.sourceType = "actual"
            item.detailId = "qa.defect.detail"
            item.targetType = "defect"
            item.targetId = top["defect_type"]
            item.clickable = True

    return live_dataset_keys, live_kpi_keys


def _build_manager_live(bundle: dict[str, Any], snapshot: DashboardLiveSnapshot) -> tuple[set[str], set[str]]:
    datasets = bundle["datasets"]
    live_dataset_keys: set[str] = set()
    live_kpi_keys: set[str] = set()
    if snapshot.defect_trend:
        datasets["hourly"] = _build_hourly_proxy(snapshot)
        live_dataset_keys.add("hourly")
    if snapshot.top_defects:
        top = snapshot.top_defects[0]
        datasets["recommendation"] = f"{top['class_name']} 우선 점검 / 최신 발생 {int(top['count'])}건"
        live_dataset_keys.add("recommendation")
    summary = snapshot.summary
    total_rows = int(summary.get("total_rows") or 0)
    ok_rows = int(summary.get("ok_rows") or 0)
    yield_rate = round((ok_rows / total_rows) * 100, 2) if total_rows else None
    for item in bundle["kpis"].items:
        if item.key == "mgr_expected_output":
            item.value = int(summary.get("request_count") or 0)
            item.unit = "boards"
            item.sourceType = "actual"
            live_kpi_keys.add(item.key)
        elif item.key == "mgr_oee" and yield_rate is not None:
            item.value = yield_rate
            item.sourceType = "actual"
            live_kpi_keys.add(item.key)
    return live_dataset_keys, live_kpi_keys


def _build_promo_live(bundle: dict[str, Any], snapshot: DashboardLiveSnapshot) -> tuple[set[str], set[str]]:
    datasets = bundle["datasets"]
    live_dataset_keys: set[str] = set()
    live_kpi_keys: set[str] = set()

    hourly = _build_hourly_proxy(snapshot)
    if hourly:
        datasets["lineTrend"] = [{"time": row["time"], "produced": row["produced"]} for row in hourly]
        live_dataset_keys.add("lineTrend")
    if snapshot.top_defects:
        datasets["top3"] = _build_top_defects(snapshot, limit=3)
        datasets["topIssues"] = [
            {
                "rank": idx + 1,
                "title": f"{row['class_name']} 증가",
                "summary": f"최신 집계 {int(row['count'])}건 / 평균 confidence {row['avg_confidence']}",
            }
            for idx, row in enumerate(snapshot.top_defects[:3])
        ]
        top = snapshot.top_defects[0]
        datasets["rollingMessage"] = f"현재 주의 포인트: {top['class_name']} 발생 {int(top['count'])}건"
        live_dataset_keys.update({"top3", "topIssues", "rollingMessage"})

    total_boards = int(snapshot.summary.get("request_count") or 0)
    yield_rate = None
    total_rows = int(snapshot.summary.get("total_rows") or 0)
    ok_rows = int(snapshot.summary.get("ok_rows") or 0)
    if total_rows:
        yield_rate = round((ok_rows / total_rows) * 100, 2)

    for item in bundle["kpis"].items:
        if item.key == "promo_total":
            item.value = total_boards
            item.unit = "boards"
            item.sourceType = "actual"
            live_kpi_keys.add("promo_total")
        elif item.key == "promo_yield" and yield_rate is not None:
            item.value = yield_rate
            item.sourceType = "actual"
            live_kpi_keys.add("promo_yield")

    return live_dataset_keys, live_kpi_keys


def _build_live_bundle(screen: str) -> tuple[dict[str, Any], dict[str, Any]]:
    bundle = _copy_mock_bundle(screen)
    snapshot = get_dashboard_live_snapshot()
    if not snapshot.latest_date:
        meta = _base_meta(screen, data_mode="mock", effective_at=None, updated_at=None, is_partial=False, is_delayed=False)
        return bundle, meta

    live_dataset_keys: set[str] = set()
    live_kpi_keys: set[str] = set()
    if screen == "worker":
        live_dataset_keys, live_kpi_keys = _build_worker_live(bundle, snapshot)
    elif screen == "qa":
        live_dataset_keys, live_kpi_keys = _build_qa_live(bundle, snapshot)
    elif screen == "manager":
        live_dataset_keys, live_kpi_keys = _build_manager_live(bundle, snapshot)
    elif screen == "promo":
        live_dataset_keys, live_kpi_keys = _build_promo_live(bundle, snapshot)

    required = REQUIRED_LIVE_DATASETS[screen] | REQUIRED_LIVE_KPIS[screen]
    actual = live_dataset_keys | live_kpi_keys
    is_partial = bool(required - actual)
    effective_at = _iso_from_date(snapshot.latest_date)
    coverage = {
        "liveDatasetKeys": sorted(live_dataset_keys),
        "mockDatasetKeys": sorted(REQUIRED_LIVE_DATASETS[screen] - live_dataset_keys),
        "liveKpiKeys": sorted(live_kpi_keys),
        "mockKpiKeys": sorted(REQUIRED_LIVE_KPIS[screen] - live_kpi_keys),
        "note": "vision_result 기반 실데이터와 기존 mock 블록이 혼합된 하이브리드 응답입니다." if is_partial else "현재 화면의 필수 블록은 실데이터 기준으로 응답됩니다.",
        "liveSource": "vision_result",
    }
    meta = _base_meta(
        screen,
        data_mode="live",
        effective_at=effective_at,
        updated_at=effective_at,
        is_partial=is_partial,
        is_delayed=_is_delayed(snapshot.latest_date),
    )
    meta["coverage"] = coverage
    return bundle, meta


def get_dashboard_kpis(screen: str, **_filters: Any) -> DashboardKPIResponse:
    screen = _ensure_screen(screen)
    bundle, meta = _build_live_bundle(screen)
    return DashboardKPIResponse(**meta, kpis=bundle["kpis"], assistive=bundle["assistive"])


def get_dashboard_datasets(screen: str, **_filters: Any) -> DashboardDatasetsResponse:
    screen = _ensure_screen(screen)
    bundle, meta = _build_live_bundle(screen)
    return DashboardDatasetsResponse(**meta, datasets=bundle["datasets"])


def _find_mock_detail_content(screen: str, request: DashboardDetailRequest) -> dict[str, Any]:
    bundle = MOCK_BUNDLES[screen]
    datasets = bundle["datasets"]
    target_type = _canonical_target_type(request.targetType)
    target_id = request.targetId.strip().upper()

    def same(value: str | None) -> bool:
        return str(value or "").strip().upper() == target_id

    if target_type == "line":
        summary = [row for row in datasets.get("statusGrid", []) if same(row.get("lineId"))]
        logs = [row for row in datasets.get("activeAlarms", []) if same(row.get("lineId"))]
        related = [row for row in datasets.get("downtimePareto", []) if same(row.get("lineId"))]
    elif target_type == "equipment":
        summary = [row for row in datasets.get("statusGrid", []) if same(row.get("equipmentId"))]
        logs = [row for row in datasets.get("activeAlarms", []) if same(row.get("equipmentId"))]
        related = [row for row in datasets.get("downtimeHistory", []) if same(row.get("equipmentId"))]
    elif target_type == "lot":
        summary = [row for row in datasets.get("ngRows", []) if same(row.get("lotId"))]
        logs = [row for row in datasets.get("handoffLogs", []) if same(row.get("targetId"))]
        related = [row for row in datasets.get("recheckQueue", []) if same(row.get("lotId"))]
    elif target_type in {"alarm", "event"}:
        summary = [row for row in datasets.get("activeAlarms", []) if same(row.get("alarmId")) or same(row.get("targetId"))]
        logs = [row for row in datasets.get("handoffLogs", []) if same(row.get("targetId"))]
        related = [row for row in datasets.get("eventTimeline", []) if same(row.get("targetId"))]
    elif target_type == "inspection":
        summary = [row for row in datasets.get("recheckQueue", []) if same(row.get("inspectionId"))]
        logs = [row for row in datasets.get("handoffLogs", []) if same(row.get("targetId"))]
        related = [row for row in datasets.get("ngRows", []) if same(row.get("lotId")) or same(row.get("targetId"))]
    elif target_type == "defect":
        summary = [row for row in datasets.get("topDefects", []) if same(row.get("causeCode")) or same(row.get("class_name"))]
        logs = [row for row in datasets.get("ngRows", []) if same(row.get("defectClass")) or same(row.get("defectType"))]
        related = [row for row in datasets.get("recheckQueue", []) if same(row.get("defectClass"))]
    else:
        raise HTTPException(status_code=400, detail={"code": "unsupported", "message": f"Unsupported targetType: {request.targetType}"})

    if not summary and not logs and not related:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": f"No detail found for {request.targetType}:{request.targetId}"})
    return {"summary": summary, "logs": logs, "relatedItems": related, "actions": []}


def _find_live_detail_content(target_type: str, target_id: str) -> dict[str, Any] | None:
    if target_type == "defect":
        return get_defect_detail(target_id)
    if target_type == "lot":
        return get_lot_detail(target_id)
    if target_type == "alarm":
        return get_alarm_detail(target_id)
    if target_type in {"inspection", "event"}:
        return get_request_detail(target_id)
    return None


def get_dashboard_detail(screen: str, request: DashboardDetailRequest) -> DashboardDetailResponse:
    screen = _ensure_screen(screen)
    if screen == "promo":
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "Promo board does not support detail access"})

    detail_id = _validate_detail_id(screen, request.detailId)
    target_type = _canonical_target_type(request.targetType)
    live_detail = _find_live_detail_content(target_type, request.targetId)
    meta = _base_meta(
        screen,
        data_mode="live",
        effective_at=_now_iso(),
        updated_at=_now_iso(),
        is_partial=False,
        is_delayed=False,
    )
    detail_content = live_detail or _find_mock_detail_content(screen, request)
    if not detail_content.get("summary") and not detail_content.get("logs") and not detail_content.get("relatedItems"):
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": f"No detail found for {request.targetType}:{request.targetId}"})

    return DashboardDetailResponse(
        detailId=detail_id,
        targetType=target_type,
        targetId=request.targetId,
        subKey=request.subKey,
        screen=screen,
        screenId=SCREEN_ID_MAP[screen],
        timezone=TIMEZONE_NAME,
        dataMode=meta["dataMode"],
        effectiveAt=meta["effectiveAt"],
        updatedAt=meta["updatedAt"],
        isPartial=meta["isPartial"],
        isDelayed=meta["isDelayed"],
        staleLabel=meta["staleLabel"],
        coverage=meta.get("coverage", {}),
        **detail_content,
    )


def _web_dashboard_meta(screen: str, **filters: Any) -> dict[str, Any]:
    date_from = _coerce_filter_date(filters.get("date_from"))
    date_to = _coerce_filter_date(filters.get("date_to"))
    is_period_compare = bool(date_from and date_to and date_from != date_to and date_from <= date_to)
    requested_range = (
        {
            "from": date_from.isoformat(),
            "to": date_to.isoformat(),
            "days": (date_to - date_from).days + 1,
        }
        if is_period_compare
        else None
    )
    return {
        "screen": screen,
        "screenId": f"WEB-{screen.upper()}",
        "timezone": TIMEZONE_NAME,
        "effectiveAt": filters.get("effective_at") or _now_iso(),
        "updatedAt": filters.get("updated_at") or _now_iso(),
        "requestedDate": filters.get("requested_date"),
        "scenarioDate": filters.get("scenario_date"),
        "line": filters.get("line"),
        "viewMode": "period_compare" if is_period_compare else "realtime_day",
        "requestedDateRange": requested_range,
        "filters": {
            "factory": filters.get("factory"),
            "line": filters.get("line"),
            "shift": filters.get("shift"),
            "period": filters.get("period"),
            "tz": filters.get("tz") or TIMEZONE_NAME,
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
        },
    }


def _to_int(value: Any) -> int:
    return int(value or 0)


def _to_float(value: Any) -> float:
    return round(float(value or 0), 2)


def _status_by_floor(value: float, ok_floor: float, warn_floor: float) -> str:
    if value >= ok_floor:
        return "ok"
    if value >= warn_floor:
        return "warning"
    return "critical"


def _severity_color(severity: str) -> str:
    severity = str(severity or "info").lower()
    if severity == "critical":
        return "#DC2626"
    if severity == "warning":
        return "#D97706"
    if severity == "info":
        return "#2563EB"
    return "#059669"


def _equipment_status_token(status_code: str) -> str:
    status_code = str(status_code or "idle").lower()
    return {
        "run": "run",
        "idle": "idle",
        "down": "down",
        "maint": "maint",
    }.get(status_code, "idle")


def _line_temperature_payload(snap: WebDashboardSnapshot) -> dict[str, Any]:
    warning = 70
    critical = 78
    chosen = None
    for sensor in snap.focus_line_environment:
        sensor_type = str(sensor.get("sensor_type") or "").upper()
        if sensor_type.startswith("TEMP-") and sensor_type != "TEMP-LINE":
            chosen = sensor
            break
    if chosen is None:
        for sensor in snap.focus_line_environment:
            if str(sensor.get("metric_name") or "").lower() == "temperature":
                chosen = sensor
                break

    current = _to_float(chosen.get("metric_value")) if chosen else 0.0
    status = "critical" if current >= critical else "warning" if current >= warning else "run"
    return {
        "line": snap.focus_line_code or "-",
        "current": current,
        "unit": str(chosen.get("unit") or "°C") if chosen else "°C",
        "status": status,
        "warning": warning,
        "critical": critical,
        "updatedAt": str(chosen.get("recorded_at") or _now().strftime("%H:%M")) if chosen else _now().strftime("%H:%M"),
    }


def _overall_oee_components(snap: WebDashboardSnapshot, daily_plan_total: float | None = None) -> dict[str, float]:
    if snap.line_production:
        weighted_availability = 0.0
        total_weight = 0.0
        for row in snap.line_production:
            line_code = str(row.get("line_code") or "")
            weight = LINE_PLAN_SHARE.get(line_code, 0.25)
            weighted_availability += _to_float(row.get("availability_pct")) * weight
            total_weight += weight
        availability = round(weighted_availability / total_weight, 2) if total_weight > 0 else 0.0
    else:
        availability = 0.0

    plan_base = float(daily_plan_total) if daily_plan_total is not None else float(DAY_PLAN_TOTAL)
    plan_to_now = plan_base * max(float(snap.elapsed_ratio or 0), 0.01)
    performance = round((snap.total_produced / plan_to_now) * 100, 2) if plan_to_now > 0 else 0.0
    quality = round((snap.total_good / snap.total_produced) * 100, 2) if snap.total_produced > 0 else 0.0

    availability = max(0.0, min(100.0, availability))
    performance = max(0.0, min(100.0, performance))
    quality = max(0.0, min(100.0, quality))
    oee = round((availability / 100.0) * (performance / 100.0) * (quality / 100.0) * 100.0, 2)
    return {
        "availability": availability,
        "performance": performance,
        "quality": quality,
        "oee": oee,
    }


def _daily_plan_by_line(line_code: str | None) -> int:
    normalized = str(line_code or "").strip().upper()
    if not normalized:
        return DAY_PLAN_TOTAL
    share = LINE_PLAN_SHARE.get(normalized)
    if share is None:
        return DAY_PLAN_TOTAL
    return round(DAY_PLAN_TOTAL * float(share))


def _bundle_daily_plan(bundle: dict[str, Any], snap: WebDashboardSnapshot | None = None) -> tuple[int, str | None]:
    line_code = str(bundle.get("meta", {}).get("filters", {}).get("line") or "").strip().upper()
    if (not line_code) and snap is not None and len(snap.line_production or []) == 1:
        line_code = str((snap.line_production[0] or {}).get("line_code") or "").strip().upper()
    daily_plan = _daily_plan_by_line(line_code or None)
    return daily_plan, (line_code or None)


def _line_risk_summary(row: dict[str, Any]) -> str:
    latest_status = str(row.get("latest_status") or "").lower()
    risk = _to_float(row.get("risk_score"))
    ng = _to_int(row.get("ng"))
    produced = _to_int(row.get("produced"))
    defect_rate = round((ng / produced) * 100, 2) if produced > 0 else 0.0
    if latest_status == "down":
        return "다운타임과 알람 동시 증가"
    if defect_rate >= 4.0:
        return "품질 편차 지속"
    if risk >= 55:
        return "속도 저하와 운영 불안정"
    return "정상 운영"


def _build_daily_compare_rows(filters: dict[str, Any], start_date: date, end_date: date) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    requested_line = str(filters.get("line") or "").strip().upper()
    daily_plan = _daily_plan_by_line(requested_line or None)
    for day in _iter_dates(start_date, end_date):
        snap = get_web_dashboard_snapshot(
            filters.get("line"),
            target_date=day,
            factory=filters.get("factory"),
            shift=filters.get("shift"),
        )
        oee_parts = _overall_oee_components(snap, daily_plan_total=daily_plan)
        rows.append(
            {
                "date": day.isoformat(),
                "produced": int(snap.total_produced or 0),
                "checked": int(snap.total_checked or 0),
                "good": int(snap.total_good or 0),
                "ng": int(snap.total_ng or 0),
                "defect_rate": round(float(snap.defect_rate or 0), 2),
                "alarm_count": int(snap.active_alarm_count or 0),
                "oee": round(float(oee_parts.get("oee") or 0), 2),
            }
        )
    return rows


def _apply_period_compare_worker(bundle: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    if not rows:
        bundle["dailyCompare"] = []
        return
    days = len(rows)
    total_produced = sum(int(row.get("produced") or 0) for row in rows)
    total_ng = sum(int(row.get("ng") or 0) for row in rows)
    avg_oee = round(sum(float(row.get("oee") or 0) for row in rows) / max(days, 1), 2)

    line_code = str(bundle.get("meta", {}).get("filters", {}).get("line") or "").upper()
    line_share = float(LINE_PLAN_SHARE.get(line_code, 0.25))
    daily_target = round(DAY_PLAN_TOTAL * line_share)
    total_target = daily_target * days

    for item in bundle.get("kpis", []):
        if item.get("id") == "worker_hourly_output":
            item["label"] = "기간 일평균 생산량"
            item["value"] = round(total_produced / max(days, 1))
            item["target"] = daily_target
            item["meta"] = "actual/db"
            item["status"] = "critical" if item["value"] < daily_target * 0.65 else "warning" if item["value"] < daily_target * 0.85 else "ok"
        elif item.get("id") == "worker_line_output":
            item["label"] = "기간 총 생산량"
            item["value"] = total_produced
            item["target"] = total_target
            item["meta"] = "actual/db"
            item["status"] = "critical" if total_produced < total_target * 0.65 else "warning" if total_produced < total_target * 0.85 else "ok"
        elif item.get("id") == "worker_recent_10m_ng":
            item["label"] = "기간 총 NG"
            item["value"] = total_ng
            item["meta"] = "actual/db"
            item["status"] = "critical" if total_ng >= max(120, days * 8) else "warning" if total_ng >= max(30, days * 3) else "ok"
        elif item.get("id") == "worker_achievement":
            item["label"] = "기간 평균 OEE"
            item["value"] = avg_oee
            item["unit"] = "%"
            item["meta"] = "derived/db"
            item["status"] = "critical" if avg_oee < 70 else "warning" if avg_oee < 85 else "ok"

    bundle["ngTrend"] = [
        {"time": str(row.get("date"))[5:], "ng": int(row.get("ng") or 0)}
        for row in rows
    ]
    bundle["dailyCompare"] = rows
    bundle["hint"] = {"value": f"기간 비교 모드: {days}일 일별 데이터 비교", "confidence": 1.0}


def _apply_period_compare_qa(bundle: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    if not rows:
        bundle["dailyCompare"] = []
        return
    days = len(rows)
    total_produced = sum(int(row.get("produced") or 0) for row in rows)
    total_checked = sum(int(row.get("checked") or 0) for row in rows)
    total_ng = sum(int(row.get("ng") or 0) for row in rows)
    defect_rate = round((total_ng / max(total_checked, 1)) * 100, 2) if total_checked > 0 else 0.0

    line_code = str(bundle.get("meta", {}).get("filters", {}).get("line") or "").upper()
    line_share = float(LINE_PLAN_SHARE.get(line_code, 1.0 if not line_code else 0.25))
    total_target = round(DAY_PLAN_TOTAL * days * line_share)

    for item in bundle.get("kpis", []):
        if item.get("id") == "qa_defect_rate":
            item["label"] = "기간 평균 불량률"
            item["value"] = defect_rate
            item["meta"] = "derived/db"
            item["status"] = "critical" if defect_rate >= 3 else "warning" if defect_rate >= 1.5 else "ok"
        elif item.get("id") == "qa_recheck":
            item["label"] = "기간 알람 합계"
            item["value"] = sum(int(row.get("alarm_count") or 0) for row in rows)
            item["meta"] = "actual/db"
        elif item.get("id") == "qa_inspect":
            item["label"] = "기간 검사량"
            item["value"] = total_checked
            item["unit"] = f"/{total_target}"
            item["target"] = total_target
            item["meta"] = "actual/db"
            item["status"] = "critical" if total_checked < total_target * 0.65 else "warning" if total_checked < total_target * 0.85 else "ok"
        elif item.get("id") == "qa_total_output":
            item["label"] = "기간 총 생산량"
            item["value"] = total_produced
            item["target"] = total_target
            item["meta"] = "actual/db"
            item["status"] = "critical" if total_produced < total_target * 0.65 else "warning" if total_produced < total_target * 0.85 else "ok"

    bundle["defectTrend"] = [
        {"time": str(row.get("date"))[5:], "actual": float(row.get("defect_rate") or 0)}
        for row in rows
    ]
    bundle["dailyCompare"] = rows
    bundle["hint"] = {"value": f"기간 비교 모드: {days}일 품질 지표 비교", "severity": "warn" if defect_rate >= 1.5 else "info"}


def _apply_period_compare_manager(bundle: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    if not rows:
        bundle["dailyCompare"] = []
        return
    days = len(rows)
    total_produced = sum(int(row.get("produced") or 0) for row in rows)
    total_ng = sum(int(row.get("ng") or 0) for row in rows)
    avg_oee_raw = sum(float(row.get("oee") or 0) for row in rows) / max(days, 1)
    avg_oee = round(max(0.0, min(100.0, avg_oee_raw)), 2)
    daily_plan, _ = _bundle_daily_plan(bundle)
    total_plan = daily_plan * days
    achievement = round((total_produced / max(total_plan, 1)) * 100, 2) if total_plan > 0 else 0.0
    daily_avg_produced = round(total_produced / max(days, 1))

    for item in bundle.get("kpis", []):
        if item.get("id") == "mgr_oee":
            item["label"] = "기간 평균 OEE"
            item["value"] = avg_oee
            item["target"] = 85
            item["meta"] = "derived/db"
            item["status"] = "critical" if avg_oee < 70 else "warning" if avg_oee < 85 else "ok"
        elif item.get("id") == "mgr_achievement":
            item["label"] = "기간 목표 달성률"
            item["value"] = achievement
            item["target"] = 100
            item["meta"] = "derived/db"
            item["status"] = "critical" if achievement < 65 else "warning" if achievement < 80 else "ok"
        elif item.get("id") == "mgr_today_output":
            item["label"] = "기간 총 생산량"
            item["value"] = total_produced
            item["target"] = total_plan
            item["meta"] = "actual/db"
            item["status"] = "critical" if total_produced < total_plan * 0.65 else "warning" if total_produced < total_plan * 0.85 else "ok"
        elif item.get("id") == "mgr_expected_output":
            item["label"] = "기간 일평균 생산"
            item["value"] = daily_avg_produced
            item["target"] = daily_plan
            item["meta"] = "derived/db"
            item["status"] = "critical" if daily_avg_produced < daily_plan * 0.65 else "warning" if daily_avg_produced < daily_plan * 0.85 else "ok"

    bundle["managerProductionTrend"] = []
    bundle["managerDefectTrend"] = []
    for row in rows:
        daily_actual = int(row.get("produced") or 0)
        bundle["managerProductionTrend"].append(
            {"time": str(row.get("date"))[5:], "actual": daily_actual, "plan": daily_plan}
        )
        bundle["managerDefectTrend"].append(
            {"time": str(row.get("date"))[5:], "rate": float(row.get("defect_rate") or 0)}
        )

    bundle["dailyCompare"] = rows
    bundle["riskOverall"] = {
        "severity": "critical" if total_ng >= max(200, days * 12) else "warning" if total_ng >= max(80, days * 5) else "ok",
        "reason": f"기간 합계 NG {total_ng}건 기준",
    }


def _apply_period_compare_promo(bundle: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    if not rows:
        bundle["dailyCompare"] = []
        return
    days = len(rows)
    total_produced = sum(int(row.get("produced") or 0) for row in rows)
    total_good = sum(int(row.get("good") or 0) for row in rows)
    total_ng = sum(int(row.get("ng") or 0) for row in rows)
    avg_oee_raw = sum(float(row.get("oee") or 0) for row in rows) / max(days, 1)
    avg_oee = round(max(0.0, min(100.0, avg_oee_raw)), 2)
    daily_target, _ = _bundle_daily_plan(bundle)
    total_target = daily_target * days
    daily_avg_produced = round(total_produced / max(days, 1))
    achievement = round((total_produced / max(total_target, 1)) * 100, 2)
    defect_rate = round((total_ng / max(total_produced, 1)) * 100, 2) if total_produced > 0 else 0.0
    yield_rate = round((total_good / max(total_produced, 1)) * 100, 2) if total_produced > 0 else 0.0

    for item in bundle.get("kpis", []):
        if item.get("id") == "promo_today_output":
            item["label"] = "기간 총 생산량"
            item["value"] = total_produced
            item["target"] = total_target
            item["meta"] = "actual/db"
            item["status"] = "critical" if total_produced < total_target * 0.65 else "warning" if total_produced < total_target * 0.85 else "ok"
        elif item.get("id") == "promo_month_output":
            item["label"] = "기간 일평균 생산"
            item["value"] = daily_avg_produced
            item["target"] = daily_target
            item["meta"] = "derived/db"
            item["status"] = "critical" if daily_avg_produced < daily_target * 0.65 else "warning" if daily_avg_produced < daily_target * 0.85 else "ok"
        elif item.get("id") == "promo_oee":
            item["label"] = "기간 평균 OEE"
            item["value"] = avg_oee
            item["target"] = 85
            item["meta"] = "derived/db"
            item["status"] = "critical" if avg_oee < 70 else "warning" if avg_oee < 85 else "ok"
        elif item.get("id") == "promo_defect_rate":
            item["label"] = "기간 평균 불량률"
            item["value"] = defect_rate
            item["meta"] = "derived/db"
            item["status"] = "critical" if defect_rate >= 4 else "warning" if defect_rate >= 2 else "ok"
        elif item.get("id") == "promo_delivery_rate":
            item["label"] = "기간 평균 양품률"
            item["value"] = yield_rate
            item["target"] = 98
            item["meta"] = "derived/db"
            item["status"] = "critical" if yield_rate < 94 else "warning" if yield_rate < 98 else "ok"

    bundle["promoWeekProduction"] = [
        {
            "day": str(row.get("date"))[5:],
            "actual": int(row.get("produced") or 0),
            "target": daily_target,
        }
        for row in rows
    ]
    bundle["promoMonthlyCompare"] = [
        {"label": "기간 총 생산", "value": f"{total_produced:,}", "diff": f"{days}일 누적 기준", "tone": "up" if achievement >= 100 else "down"},
        {"label": "기간 평균 OEE", "value": f"{avg_oee}%", "diff": "고정 목표 85%", "tone": "up" if avg_oee >= 85 else "down"},
        {"label": "기간 평균 불량률", "value": f"{defect_rate}%", "diff": "고정 임계 2%", "tone": "down" if defect_rate > 2 else "up"},
    ]
    bundle["promoTicker"] = [
        f"선택 기간: {rows[0]['date']} ~ {rows[-1]['date']}",
        f"기간 총 생산량 {total_produced:,}",
        f"기간 평균 OEE {avg_oee}%",
        f"기간 평균 양품률 {yield_rate}%",
    ]
    bundle["dailyCompare"] = rows


def _set_web_kpi_detail(
    bundle: dict[str, Any],
    kpi_id: str,
    *,
    detail_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    detail_title: str | None = None,
) -> None:
    for item in bundle.get("kpis", []):
        if item.get("id") != kpi_id:
            continue
        if detail_id and target_type and target_id:
            item["detailId"] = detail_id
            item["targetType"] = target_type
            item["targetId"] = target_id
            item["clickable"] = True
            if detail_title:
                item["detailTitle"] = detail_title
        else:
            item.pop("detailId", None)
            item.pop("targetType", None)
            item.pop("targetId", None)
            item.pop("detailTitle", None)
            item["clickable"] = False
        break


def _web_worker_dashboard_bundle(**filters: Any) -> dict[str, Any]:
    return {
        "meta": _web_dashboard_meta("worker", **filters),
        "kpis": [
            {"id": "worker_hourly_output", "label": "시간당 생산량", "value": 421, "unit": "pcs", "target": 600, "status": "warning", "meta": "actual/mock"},
            {"id": "worker_line_output", "label": "현재 라인 생산량", "value": 1280, "unit": "pcs", "status": "ok", "meta": "actual/mock"},
            {
                "id": "worker_recent_10m_ng",
                "label": "최근 10분 NG",
                "value": 12,
                "unit": "건",
                "status": "warning",
                "meta": "actual/mock",
                "detailId": "worker.action.detail",
                "targetType": "lot",
                "targetId": "LOT-88421",
                "clickable": True,
                "detailTitle": "NG 상세",
            },
            {"id": "worker_achievement", "label": "가동률", "value": 93.2, "unit": "%", "status": "ok", "meta": "actual/mock"},
        ],
        "lineTemperature": {
            "line": "LINE-A",
            "current": 68.4,
            "unit": "°C",
            "status": "run",
            "warning": 70,
            "critical": 78,
            "updatedAt": "15:00",
        },
        "hint": {"value": "AOI-01 — 향후 10분 내 NG 증가 위험 감지", "confidence": 0.71},
        "statusGrid": [
            {"id": "AOI-01", "type": "광학검사", "status": "run", "opr": "91%", "ng": "8건", "time": "15:00"},
            {"id": "DRV-01", "type": "드라이버", "status": "run", "opr": "97%", "ng": "2건", "time": "15:00"},
            {"id": "PRN-02", "type": "프린터", "status": "run", "opr": "99%", "ng": "1건", "time": "14:58"},
            {"id": "MNT-04", "type": "마운터", "status": "down", "opr": "-", "ng": "34건", "time": "14:55"},
        ],
        "actionQueue": [
            {"priority": 1, "target": "MNT-04 정지 대응", "reason": "spur 다수 감지 → 설비 중지", "severity": "critical", "time": "14:55"},
            {"priority": 2, "target": "NG 급증 확인", "reason": "최근 10분 12건 — 주의 임박", "severity": "warning", "time": "14:58"},
            {"priority": 3, "target": "AOI-01 점검 예약", "reason": "처리속도 저하 감지", "severity": "info", "time": "15:00"},
            {"priority": 4, "target": "라인 온도 점검", "reason": "LINE-A 현재 온도 68.4°C — 기준 근접 여부 확인", "severity": "info", "time": "15:00"},
        ],
        "globalNotices": [
            {"color": "#DC2626", "meta": "15:02 · LINE-C · 알람", "text": "MNT-04 정지 — 전사 대응 공지"},
            {"color": "#D97706", "meta": "14:49 · LINE-B · 점검", "text": "AOI-03 광학검사 재교정 예정"},
            {"color": "#2563EB", "meta": "14:30 · LINE-D · 운영", "text": "야간조 인수인계 체크리스트 배포"},
        ],
        "ngTrend": [
            {"time": "14:52", "ng": 4},
            {"time": "14:53", "ng": 5},
            {"time": "14:54", "ng": 6},
            {"time": "14:55", "ng": 8},
            {"time": "14:56", "ng": 9},
            {"time": "14:57", "ng": 10},
            {"time": "14:58", "ng": 11},
            {"time": "14:59", "ng": 12},
            {"time": "15:00", "ng": 12},
        ],
        "ngTypes": [
            {"name": "short", "count": 34, "color": "#DC2626"},
            {"name": "open", "count": 22, "color": "#D97706"},
            {"name": "spur", "count": 16, "color": "#2563EB"},
            {"name": "mousebite", "count": 10, "color": "#059669"},
            {"name": "spurious_copper", "count": 8, "color": "#7C3AED"},
            {"name": "pin_hole", "count": 6, "color": "#6B7280"},
        ],
        "events": [
            {"color": "#DC2626", "meta": "15:00 · 알람 · MNT-04", "text": "마운터 정지 — spur 다수 감지"},
            {"color": "#D97706", "meta": "14:58 · 조치 · AOI-01", "text": "광학검사 속도 저하 — 자재 투입 대기 확인"},
            {"color": "#2563EB", "meta": "14:56 · QA · LINE A", "text": "품질팀 재검 요청 — LOT-88421 (open 판정)"},
            {"color": "#059669", "meta": "14:30 · 정보 · DRV-01", "text": "드라이버 정기점검 완료 — 정상 가동 확인"},
        ],
    }


def _apply_web_worker_live(bundle: dict[str, Any], snap: WebDashboardSnapshot) -> None:
    # DB 기반 모드에서는 mock 잔여값이 남지 않도록 주요 블록을 먼저 초기화한다.
    bundle["ngTypes"] = []
    bundle["events"] = []
    bundle["ngTrend"] = []
    bundle["actionQueue"] = []
    bundle["globalNotices"] = []
    bundle["statusGrid"] = []
    bundle["lineTemperature"] = {
        "line": "-",
        "current": 0,
        "unit": "°C",
        "status": "idle",
        "warning": 70,
        "critical": 78,
        "updatedAt": _now().strftime("%H:%M"),
    }
    bundle["hint"] = {"value": "DB 실시간 데이터 기준", "confidence": 1.0}

    for item in bundle.get("kpis", []):
        if item.get("id") == "worker_hourly_output":
            item["value"] = snap.focus_hourly_output
            item["status"] = _status_by_floor(snap.focus_hourly_output, 510, 420)
            item["meta"] = "actual/db"
        elif item.get("id") == "worker_line_output":
            item["value"] = snap.focus_line_output
            item["status"] = "ok" if snap.focus_line_output > 0 else "warning"
            item["meta"] = "actual/db"
        elif item.get("id") == "worker_recent_10m_ng":
            item["value"] = snap.recent_10m_ng
            item["status"] = "critical" if snap.recent_10m_ng >= 10 else "warning" if snap.recent_10m_ng >= 6 else "ok"
            item["meta"] = "actual/db"
        elif item.get("id") == "worker_achievement":
            item["value"] = snap.focus_line_availability
            item["status"] = _status_by_floor(snap.focus_line_availability, 95, 90)
            item["meta"] = "derived/db"

    bundle["lineTemperature"] = _line_temperature_payload(snap)

    bundle["ngTypes"] = [
        {
            "name": row["code"],
            "count": int(row["count"]),
            "color": row["color"],
        }
        for row in _build_fixed_defect_slots(snap.top_defects, limit=6)
    ]

    if snap.focus_ng_trend:
        bundle["ngTrend"] = [
            {"time": row.get("bucket"), "ng": _to_int(row.get("ng_qty"))}
            for row in snap.focus_ng_trend[-12:]
        ]

    if snap.focus_equipment_status:
        bundle["statusGrid"] = [
            {
                "id": row.get("equip_code") or "-",
                "type": row.get("equip_type") or "-",
                "status": _equipment_status_token(str(row.get("status_code") or "")),
                "opr": f"{_to_float(row.get('availability_pct'))}%",
                "ng": f"{_to_int(row.get('ng_qty'))}건",
                "time": str(row.get("updated_at") or ""),
            }
            for row in snap.focus_equipment_status
        ]

    focus_alarms = [row for row in snap.active_alarms if row.get("line_code") == snap.focus_line_code]
    if snap.recheck_rows:
        _set_web_kpi_detail(
            bundle,
            "worker_recent_10m_ng",
            detail_id="worker.action.detail",
            target_type="lot",
            target_id=str(snap.recheck_rows[0].get("lot_id") or ""),
            detail_title="NG 상세",
        )
    elif focus_alarms:
        _set_web_kpi_detail(
            bundle,
            "worker_recent_10m_ng",
            detail_id="common.alarm.detail",
            target_type="alarm",
            target_id=str(focus_alarms[0].get("alarm_code") or ""),
            detail_title="NG 관련 알람 상세",
        )
    else:
        _set_web_kpi_detail(bundle, "worker_recent_10m_ng")

    action_queue: list[dict[str, Any]] = []
    for row in focus_alarms[:3]:
        action_queue.append(
            {
                "priority": len(action_queue) + 1,
                "target": f"{row.get('equip_code') or row.get('alarm_code')}",
                "reason": str(row.get("message") or ""),
                "severity": str(row.get("severity") or "info").lower(),
                "time": str(row.get("occurred_at") or ""),
            }
        )
    for row in snap.focus_equipment_status:
        if str(row.get("status_code") or "").lower() == "down":
            action_queue.append(
                {
                    "priority": len(action_queue) + 1,
                    "target": str(row.get("equip_code") or "설비"),
                    "reason": str(row.get("reason_text") or "설비 정지 대응 필요"),
                    "severity": "critical",
                    "time": str(row.get("updated_at") or ""),
                }
            )
    if snap.recent_10m_ng >= 6:
        last_bucket = snap.focus_ng_trend[-1].get("bucket") if snap.focus_ng_trend else _now().strftime("%H:%M")
        action_queue.append(
            {
                "priority": len(action_queue) + 1,
                "target": f"{snap.focus_line_code} NG 추세",
                "reason": f"최근 10분 NG {snap.recent_10m_ng}건",
                "severity": "critical" if snap.recent_10m_ng >= 10 else "warning",
                "time": str(last_bucket),
            }
        )
    temp_payload = bundle["lineTemperature"]
    if temp_payload.get("current", 0) >= 68:
        action_queue.append(
            {
                "priority": len(action_queue) + 1,
                "target": f"{snap.focus_line_code} 온도 점검",
                "reason": f"설비 온도 {temp_payload.get('current')}°C",
                "severity": "warning" if temp_payload.get("current", 0) < 70 else "critical",
                "time": str(temp_payload.get("updatedAt") or ""),
            }
        )
    def _queue_time_to_ts(raw: Any) -> float:
        text = str(raw or "").strip()
        if not text:
            return 0.0
        try:
            return datetime.fromisoformat(text).timestamp()
        except ValueError:
            pass
        try:
            hh, mm = text.split(":", 1)
            local_dt = datetime.combine(_now().date(), time(int(hh), int(mm)), tzinfo=KST)
            return local_dt.timestamp()
        except (ValueError, TypeError):
            return 0.0

    severity_rank = {"critical": 3, "warning": 2, "info": 1, "ok": 0}
    sorted_queue = sorted(
        action_queue,
        key=lambda item: (
            _queue_time_to_ts(item.get("time")),
            severity_rank.get(str(item.get("severity") or "info").lower(), 0),
        ),
        reverse=True,
    )
    for idx, item in enumerate(sorted_queue, start=1):
        item["priority"] = idx

    # 백엔드는 전체 actionQueue를 전달하고, 프론트에서 최신 4건 미리보기 + 전체보기를 처리한다.
    bundle["actionQueue"] = sorted_queue

    if snap.focus_events:
        deduped_events = []
        seen_events: set[tuple[str, str]] = set()
        for row in snap.focus_events:
            meta = f"{row.get('event_time')} · {row.get('source_type')} · {row.get('equip_code')}"
            text = str(row.get("message") or row.get("title") or "")
            event_key = (meta, text)
            if event_key in seen_events:
                continue
            seen_events.add(event_key)
            deduped_events.append(
                {
                    "color": _severity_color(str(row.get("severity") or "info")),
                    "meta": meta,
                    "text": text,
                }
            )
        bundle["events"] = deduped_events[:4]

    if getattr(snap, "global_events", None):
        global_notices = []
        seen_notices: set[tuple[str, str]] = set()
        focus_line_upper = str(snap.focus_line_code or "").upper()
        for row in snap.global_events:
            line_code = str(row.get("line_code") or "").upper()
            if line_code and line_code == focus_line_upper:
                continue
            source_type = str(row.get("source_type") or "event")
            meta = f"{row.get('event_time')} · {line_code or '-'} · {source_type}"
            text = str(row.get("message") or row.get("title") or "")
            notice_key = (meta, text)
            if notice_key in seen_notices:
                continue
            seen_notices.add(notice_key)
            global_notices.append(
                {
                    "color": _severity_color(str(row.get("severity") or "info")),
                    "meta": meta,
                    "text": text,
                }
            )
        bundle["globalNotices"] = global_notices[:12]

    if focus_alarms:
        top_alarm = focus_alarms[0]
        bundle["hint"] = {
            "value": f"{top_alarm.get('equip_code')} {top_alarm.get('message')}",
            "confidence": 0.93 if str(top_alarm.get("severity") or "").lower() == "critical" else 0.82,
        }
    elif snap.recent_10m_ng >= 10:
        bundle["hint"] = {
            "value": f"{snap.focus_line_code} 최근 10분 NG 급증 감지",
            "confidence": 0.88,
        }
    elif bundle["lineTemperature"].get("current", 0) >= 68:
        bundle["hint"] = {
            "value": f"{snap.focus_line_code} 장비 온도가 임계치에 근접했습니다",
            "confidence": 0.77,
        }


def _web_qa_dashboard_bundle(**filters: Any) -> dict[str, Any]:
    return {
        "meta": _web_dashboard_meta("qa", **filters),
        "kpis": [
            {
                "id": "qa_defect_rate",
                "label": "불량률",
                "value": 4.2,
                "unit": "%",
                "status": "critical",
                "meta": "derived/mock",
                "detailId": "qa.defect.detail",
                "targetType": "defect",
                "targetId": "short",
                "clickable": True,
                "detailTitle": "불량 상세",
            },
            {
                "id": "qa_recheck",
                "label": "재검 대기",
                "value": 24,
                "unit": "건",
                "status": "warning",
                "meta": "derived/mock",
                "detailId": "qa.reinspection.queue",
                "targetType": "lot",
                "targetId": "LOT-88421",
                "clickable": True,
                "detailTitle": "재검 상세",
            },
            {"id": "qa_inspect", "label": "검사 현황", "value": 342, "unit": "/380", "target": 380, "status": "ok", "meta": "actual/mock"},
            {"id": "qa_total_output", "label": "현재 총 생산량", "value": 8420, "unit": "pcs", "status": "ok", "meta": "actual/mock"},
        ],
        "hint": {"value": "SHORT + OPEN 복합 불량 — 솔더 인쇄 공정 긴급 점검 권장", "severity": "warn"},
        "topDefects": [
            {"class_name": "short", "causeCode": "short", "count": 34, "color": "#DC2626"},
            {"class_name": "open", "causeCode": "open", "count": 22, "color": "#D97706"},
            {"class_name": "spur", "causeCode": "spur", "count": 16, "color": "#2563EB"},
            {"class_name": "mousebite", "causeCode": "mousebite", "count": 10, "color": "#059669"},
            {"class_name": "spurious_copper", "causeCode": "spurious_copper", "count": 8, "color": "#7C3AED"},
            {"class_name": "pin_hole", "causeCode": "pin_hole", "count": 6, "color": "#6B7280"},
        ],
        "recheckQueue": [
            {"lotId": "LOT-88421", "defectClass": "SHORT", "priority": "HIGH", "severity": "critical", "queuedAt": "09:18", "count": 14, "cause": "솔더 인쇄 압력 편차"},
            {"lotId": "LOT-88395", "defectClass": "OPEN", "priority": "MEDIUM", "severity": "warning", "queuedAt": "08:55", "count": 8, "cause": "리플로우 온도 이상"},
            {"lotId": "LOT-88312", "defectClass": "SPUR", "priority": "LOW", "severity": "info", "queuedAt": "08:30", "count": 5, "cause": "PCB 소재 이물질"},
        ],
        "defectTrend": [
            {"time": "09:00", "actual": 3.1},
            {"time": "09:20", "actual": 3.4},
            {"time": "09:40", "actual": 3.2},
            {"time": "10:00", "actual": 3.7},
            {"time": "10:20", "actual": 3.9},
            {"time": "10:40", "actual": 4.0},
            {"time": "11:00", "actual": 4.1},
            {"time": "11:20", "actual": 4.2},
        ],
        "issues": [
            {"id": "ISS-2405-001", "title": "SHORT 집중 발생", "cause": "솔더 인쇄 압력 편차", "equip": "SMT-01", "severity": "critical", "action": "솔더 인쇄기 설정 점검", "owner": "QA팀 김○○", "time": "09:15"},
            {"id": "ISS-2405-002", "title": "OPEN 불량 증가", "cause": "리플로우 온도 이상", "equip": "REFLOW-01", "severity": "warning", "action": "온도 프로파일 재설정", "owner": "설비팀 이○○", "time": "08:50"},
            {"id": "ISS-2405-003", "title": "PIN_HOLE 간헐 발생", "cause": "PCB 소재 이물질", "equip": "AOI-01", "severity": "info", "action": "입고 검사 강화 요청", "owner": "품질팀 박○○", "time": "08:30"},
        ],
        "events": [
            {"color": "#DC2626", "meta": "11:20 · 알람", "text": "불량률 4.2% — 임계 초과"},
            {"color": "#D97706", "meta": "10:55 · QA", "text": "QLT-144 OPEN 반복 패턴 감지"},
            {"color": "#2563EB", "meta": "10:40 · ML", "text": "SHORT 급증 예측 — DT-201"},
            {"color": "#059669", "meta": "09:00 · 정보", "text": "오전 검사 완료 — 양품율 95.8%"},
        ],
    }


def _apply_web_qa_live(bundle: dict[str, Any], snap: WebDashboardSnapshot) -> None:
    bundle["topDefects"] = []
    bundle["recheckQueue"] = []
    bundle["defectTrend"] = []
    bundle["issues"] = []
    bundle["events"] = []
    bundle["hint"] = {"value": "DB 실시간 품질 집계 기준", "severity": "info"}

    inspect_target = max(snap.total_checked, snap.total_produced)
    qa_defect_rate = round((snap.total_ng / snap.total_checked) * 100, 2) if snap.total_checked > 0 else snap.defect_rate
    qa_recheck_total = sum(_to_int(row.get("count_qty")) for row in snap.recheck_rows)
    for item in bundle.get("kpis", []):
        if item.get("id") == "qa_defect_rate":
            item["value"] = qa_defect_rate
            item["status"] = "critical" if qa_defect_rate >= 3 else "warning" if qa_defect_rate >= 1.5 else "ok"
            item["meta"] = "derived/db"
        elif item.get("id") == "qa_recheck":
            item["value"] = qa_recheck_total
            item["status"] = "critical" if qa_recheck_total >= 20 else "warning" if qa_recheck_total >= 5 else "ok"
            item["meta"] = "actual/db"
        elif item.get("id") == "qa_total_output":
            item["value"] = snap.total_produced
            item["meta"] = "actual/db"
        elif item.get("id") == "qa_inspect":
            item["value"] = snap.total_checked
            item["unit"] = f"/{inspect_target}" if inspect_target > 0 else "/0"
            item["target"] = inspect_target
            item["status"] = "ok" if snap.total_checked >= int(inspect_target * 0.9) else "warning"
            item["meta"] = "actual/db"

    defect_slots = _build_fixed_defect_slots(snap.top_defects, limit=6)
    bundle["topDefects"] = [
        {
            "class_name": str(row["name"]).upper(),
            "causeCode": row["code"],
            "count": int(row["count"]),
            "color": row["color"],
        }
        for row in defect_slots
    ]
    top_slot = max(defect_slots, key=lambda item: int(item.get("count") or 0), default=None)
    if top_slot and int(top_slot.get("count") or 0) > 0:
        bundle["hint"] = {
            "value": f"{top_slot.get('code') or 'unknown'} 집중 발생",
            "severity": "warning" if qa_defect_rate >= 1.5 else "info",
        }
        _set_web_kpi_detail(
            bundle,
            "qa_defect_rate",
            detail_id="qa.defect.detail",
            target_type="defect",
            target_id=str(top_slot.get("code") or ""),
            detail_title="불량 상세",
        )
    else:
        _set_web_kpi_detail(bundle, "qa_defect_rate")

    if snap.recheck_rows:
        source_rows = list(snap.recheck_rows)
        selected_rows: list[dict[str, Any]] = []
        used_defects: set[str] = set()

        # 1차: defect_code가 겹치지 않게 우선 선택
        for row in source_rows:
            defect_key = str(row.get("defect_code") or "").strip().lower()
            if defect_key and defect_key in used_defects:
                continue
            selected_rows.append(row)
            if defect_key:
                used_defects.add(defect_key)
            if len(selected_rows) >= 10:
                break

        # 2차: 남은 슬롯은 원래 우선순위 순서대로 채움
        if len(selected_rows) < 10:
            selected_ids = {id(item) for item in selected_rows}
            for row in source_rows:
                if id(row) in selected_ids:
                    continue
                selected_rows.append(row)
                if len(selected_rows) >= 10:
                    break

        bundle["recheckQueue"] = [
            {
                "lotId": row.get("lot_id") or "",
                "defectClass": row.get("defect_code") or "",
                "priority": row.get("priority") or "",
                "severity": row.get("severity") or "info",
                "queuedAt": str(row.get("queued_at") or ""),
                "count": int(row.get("count_qty") or 0),
                "cause": row.get("cause_text") or "",
            }
            for row in selected_rows[:10]
        ]
        _set_web_kpi_detail(
            bundle,
            "qa_recheck",
            detail_id="qa.reinspection.queue",
            target_type="lot",
            target_id=str(selected_rows[0].get("lot_id") or ""),
            detail_title="재검 상세",
        )
    else:
        _set_web_kpi_detail(bundle, "qa_recheck")

    if snap.hourly_production:
        bundle["defectTrend"] = [
            {
                "time": row.get("bucket"),
                "actual": round((int(row.get("ng_qty") or 0) / int(row.get("produced") or 1)) * 100, 2) if int(row.get("produced") or 0) > 0 else 0,
            }
            for row in snap.hourly_production
        ]
    recheck_lot_set = {str(row.get("lotId") or "").strip() for row in bundle.get("recheckQueue", []) if str(row.get("lotId") or "").strip()}

    issue_candidates: list[dict[str, Any]] = []
    seen_issue_keys: set[str] = set()
    if snap.issue_rows:
        for row in snap.issue_rows:
            lot_id = str(row.get("lot_id") or "").strip()
            # 재검 우선순위 카드와 동일 LOT는 이슈 요약에서 우선 제외해 중복 노출을 줄인다.
            if lot_id and lot_id in recheck_lot_set:
                continue

            defect_mix = str(row.get("defect_mix") or "불량")
            primary_defect = str(row.get("primary_defect") or "").strip().upper()
            tokens = [token.strip().upper() for token in defect_mix.split("+") if token.strip()]
            defect_qty = _to_int(row.get("defect_qty"))
            defect_rate = _to_float(row.get("defect_rate"))

            # 절대 결함 수량 + 결함률 + 주 결함코드를 함께 고려해 심각도를 결정한다.
            if primary_defect in {"SHORT", "OPEN"} and (defect_qty >= 16 or defect_rate >= 9):
                severity = "critical"
            elif defect_qty >= 30 or defect_rate >= 12:
                severity = "critical"
            elif defect_qty >= 12 or defect_rate >= 5:
                severity = "warning"
            else:
                severity = "info"

            if primary_defect in {"SHORT", "OPEN"}:
                category = f"{primary_defect} 중심 납땜 결함"
                action = "리플로우·솔더 인쇄 조건 점검"
            elif primary_defect in {"SPURIOUS_COPPER", "SPUR"}:
                category = f"{primary_defect} 중심 동박/버 이슈"
                action = "에칭/세정 조건 재점검"
            elif primary_defect in {"SCRATCH", "MOUSE_BITE"}:
                category = f"{primary_defect} 중심 표면 가공 결함"
                action = "취급 공정·이송 롤러 점검"
            elif primary_defect:
                category = f"{primary_defect} 반복 결함"
                action = "공정 파라미터 점검"
            elif {"SHORT", "OPEN"}.issubset(set(tokens)):
                category = "납땜 복합 결함"
                action = "리플로우·솔더 인쇄 조건 동시 점검"
            elif "SPURIOUS_COPPER" in tokens or "SPUR" in tokens:
                category = "동박/버 제거 이슈"
                action = "에칭/세정 조건 재점검"
            elif "SCRATCH" in tokens or "MOUSE_BITE" in tokens:
                category = "표면 가공 결함"
                action = "취급 공정·이송 롤러 점검"
            else:
                lead = tokens[0] if tokens else "UNKNOWN"
                category = f"{lead} 반복 결함"
                action = "공정 파라미터 점검"

            title = f"{lot_id or 'LOT-NA'} {category}"
            cause_text = str(row.get("cause_text") or "").strip() or f"{(primary_defect or defect_mix)} 패턴 확인 필요"

            issue_key = f"{title}|{str(row.get('equip_code') or '-') }|{cause_text}"
            if issue_key in seen_issue_keys:
                continue
            seen_issue_keys.add(issue_key)

            issue_candidates.append(
                {
                    "id": f"ISS-L-{len(issue_candidates)+1:04d}",
                    "title": title,
                    "cause": cause_text,
                    "equip": str(row.get("equip_code") or "-"),
                    "severity": severity,
                    "action": action,
                    "owner": "QA 자동추천",
                    "time": str(row.get("latest_at") or ""),
                    "_primary": primary_defect or (tokens[0] if tokens else "UNKNOWN"),
                }
            )

    # lot 기반 이슈가 재검 목록과 완전히 겹치는 경우, 알람 기반 이슈를 보강해서 카드 의미를 살린다.
    if (not issue_candidates) and snap.active_alarms:
        for row in snap.active_alarms:
            sev = str(row.get("severity") or "warning")
            message = str(row.get("message") or "알람 발생")
            issue_key = f"ALARM|{str(row.get('line_code') or '-')}|{str(row.get('equip_code') or '-')}|{message}"
            if issue_key in seen_issue_keys:
                continue
            seen_issue_keys.add(issue_key)

            issue_candidates.append(
                {
                    "id": f"ISS-A-{len(issue_candidates)+1:04d}",
                    "title": f"{str(row.get('line_code') or '-')} 알람 이슈",
                    "cause": message,
                    "equip": str(row.get("equip_code") or "-"),
                    "severity": sev,
                    "action": "설비/공정 원인 확인 및 조치",
                    "owner": "QA 알람기반",
                    "time": str(row.get("occurred_at") or ""),
                    "_primary": "ALARM",
                }
            )
            if len(issue_candidates) >= 4:
                break

    # 같은 결함 유형만 반복되지 않도록 유형 다양성을 우선해 4건을 구성한다.
    selected_issues: list[dict[str, Any]] = []
    seen_primary: set[str] = set()
    for item in issue_candidates:
        primary = str(item.get("_primary") or "").strip()
        if primary and primary in seen_primary:
            continue
        selected_issues.append(item)
        if primary:
            seen_primary.add(primary)
        if len(selected_issues) >= 4:
            break

    if len(selected_issues) < 4:
        for item in issue_candidates:
            if item in selected_issues:
                continue
            selected_issues.append(item)
            if len(selected_issues) >= 4:
                break

    for item in selected_issues:
        item.pop("_primary", None)

    bundle["issues"] = selected_issues[:4]
    if bundle["issues"]:
        top_issue = bundle["issues"][0]
        bundle["hint"] = {
            "value": f"{top_issue['title']} - {top_issue['action']}",
            "severity": top_issue["severity"],
        }

    if snap.active_alarms or snap.recheck_rows:
        qa_events = []
        for row in snap.recheck_rows[:2]:
            qa_events.append(
                {
                    "color": _severity_color(str(row.get("severity") or "warning")),
                    "meta": f"{row.get('queued_at')} · 재검 · {row.get('lot_id')}",
                    "text": str(row.get("cause_text") or ""),
                }
            )
        for row in snap.active_alarms[:2]:
            qa_events.append(
                {
                    "color": _severity_color(str(row.get("severity") or "warning")),
                    "meta": f"{row.get('occurred_at')} · 알람 · {row.get('line_code')}",
                    "text": str(row.get("message") or "알람 발생"),
                }
            )
        bundle["events"] = qa_events[:4]


def _web_manager_dashboard_bundle(**filters: Any) -> dict[str, Any]:
    return {
        "meta": _web_dashboard_meta("manager", **filters),
        "kpis": [
            {
                "id": "mgr_oee",
                "label": "OEE",
                "value": 71.2,
                "unit": "%",
                "status": "warning",
                "meta": "derived/mock",
                "detailId": "common.alarm.detail",
                "targetType": "alarm",
                "targetId": "ALM-2401",
                "clickable": True,
                "detailTitle": "주요 운영 리스크 상세",
            },
            {"id": "mgr_achievement", "label": "목표 달성률", "value": 66, "unit": "%", "status": "critical", "meta": "derived/mock"},
            {"id": "mgr_today_output", "label": "현재 총 생산량", "value": 9200, "unit": "pcs", "status": "ok", "meta": "actual/mock"},
            {"id": "mgr_expected_output", "label": "예상 종료 생산", "value": 18600, "unit": "pcs", "status": "ok", "meta": "predicted/mock"},
        ],
        "managerLineOee": [
            {"line": "LINE A", "actual": 79, "target": 85},
            {"line": "LINE B", "actual": 91, "target": 85},
            {"line": "LINE C", "actual": 48, "target": 85},
            {"line": "LINE D", "actual": 63, "target": 85},
        ],
        "managerProductionTrend": [
            {"time": "08:00", "actual": 1200, "plan": 1300},
            {"time": "09:00", "actual": 2350, "plan": 2600},
            {"time": "10:00", "actual": 3400, "plan": 3900},
            {"time": "11:00", "actual": 4600, "plan": 5200},
            {"time": "12:00", "actual": 5500, "plan": 6500},
            {"time": "13:00", "actual": 6800, "plan": 7800},
            {"time": "14:00", "actual": 8100, "plan": 9100},
            {"time": "15:00", "actual": 9200, "plan": 10400},
        ],
        "managerDefectTrend": [
            {"time": "08:00", "rate": 1.8},
            {"time": "09:00", "rate": 2.1},
            {"time": "10:00", "rate": 2.4},
            {"time": "11:00", "rate": 3.1},
            {"time": "12:00", "rate": 3.8},
            {"time": "13:00", "rate": 4.2},
            {"time": "14:00", "rate": 3.9},
            {"time": "15:00", "rate": 4.1},
        ],
        "riskOverall": {"severity": "critical", "reason": "LINE C 다운타임 + NG 급증 복합 리스크"},
        "riskLines": [
            {"lineId": "LINE C", "summary": "다운타임과 알람 동시 증가", "riskScore": 87, "severity": "critical"},
            {"lineId": "LINE D", "summary": "품질 편차 지속", "riskScore": 68, "severity": "warning"},
            {"lineId": "LINE A", "summary": "AOI 속도 저하", "riskScore": 42, "severity": "warning"},
            {"lineId": "LINE B", "summary": "정상 운영", "riskScore": 18, "severity": "ok"},
        ],
        "pendingActions": [
            {"priority": 1, "title": "설비 정지 대응", "summary": "LINE C MNT-04 즉시 수리 요청", "count": 1},
            {"priority": 2, "title": "불량률 초과 대응", "summary": "LINE D 솔더 공정 점검", "count": 3},
            {"priority": 3, "title": "생산 목표 조정", "summary": "금일 예상 -1,400 pcs 부족", "count": 1},
        ],
        "activeAlarms": [
            {"alarmId": "ALM-2401", "line": "LINE C", "equip": "MNT-04", "cause": "DT-201", "severity": "critical", "ack": "unack", "time": "14:55"},
            {"alarmId": "ALM-2404", "line": "LINE D", "equip": "CMP-07", "cause": "MAT-144", "severity": "warning", "ack": "hold", "time": "14:40"},
            {"alarmId": "ALM-2405", "line": "LINE A", "equip": "AOI-01", "cause": "SPD-001", "severity": "warning", "ack": "unack", "time": "15:00"},
            {"alarmId": "ALM-2406", "line": "LINE B", "equip": "DRV-02", "cause": "VIB-003", "severity": "warning", "ack": "ack", "time": "13:30"},
        ],
        "events": [
            {"color": "#DC2626", "meta": "15:00 · CRITICAL", "text": "LINE C MNT-04 다운 — ALM-2401"},
            {"color": "#D97706", "meta": "14:55 · WARNING", "text": "LINE D 품질 편차 지속 — R68"},
            {"color": "#2563EB", "meta": "14:40 · 조치", "text": "LINE D CMP-07 HOLD 처리"},
            {"color": "#059669", "meta": "14:00 · 정보", "text": "A조 → B조 인계 완료"},
        ],
    }


def _apply_web_manager_live(bundle: dict[str, Any], snap: WebDashboardSnapshot) -> None:
    bundle["managerLineOee"] = []
    bundle["managerProductionTrend"] = []
    bundle["managerDefectTrend"] = []
    bundle["activeAlarms"] = []
    bundle["pendingActions"] = []
    bundle["events"] = []
    bundle["riskOverall"] = {"severity": "ok", "reason": "DB 기준 특이사항 없음"}
    bundle["riskLines"] = []
    _set_web_kpi_detail(bundle, "mgr_oee")

    daily_plan, _ = _bundle_daily_plan(bundle, snap)
    oee_parts = _overall_oee_components(snap, daily_plan_total=daily_plan)
    achievement = round((snap.total_produced / (daily_plan * max(snap.elapsed_ratio, 0.01))) * 100, 2)
    expected_output = round((snap.total_produced / max(snap.elapsed_minutes, 1)) * DAY_MINUTES)
    for item in bundle.get("kpis", []):
        if item.get("id") == "mgr_oee":
            item["value"] = oee_parts["oee"]
            item["status"] = "critical" if oee_parts["oee"] < 70 else "warning" if oee_parts["oee"] < 85 else "ok"
            item["meta"] = "derived/db"
        elif item.get("id") == "mgr_achievement":
            item["value"] = achievement
            item["status"] = "critical" if achievement < 65 else "warning" if achievement < 80 else "ok"
            item["meta"] = "derived/db"
        elif item.get("id") == "mgr_today_output":
            item["value"] = snap.total_produced
            item["meta"] = "actual/db"
        elif item.get("id") == "mgr_expected_output":
            item["value"] = expected_output
            item["meta"] = "predicted/db"

    if snap.line_production:
        bundle["managerLineOee"] = [
            {
                "line": row.get("line_code") or row.get("line_name") or "-",
                "actual": _to_float(row.get("oee")),
                "target": 85,
            }
            for row in snap.line_production[:4]
        ]
        sorted_risks = sorted(snap.line_production, key=lambda row: _to_float(row.get("risk_score")), reverse=True)
        bundle["riskLines"] = [
            {
                "lineId": row.get("line_code") or row.get("line_name") or "-",
                "summary": _line_risk_summary(row),
                "riskScore": _to_float(row.get("risk_score")),
                "severity": "critical" if _to_float(row.get("risk_score")) >= 75 else "warning" if _to_float(row.get("risk_score")) >= 40 else "ok",
            }
            for row in sorted_risks[:4]
        ]

    if snap.hourly_production:
        cumulative_actual = 0
        production_trend = []
        defect_trend = []
        for idx, row in enumerate(snap.hourly_production, start=1):
            produced = _to_int(row.get("produced"))
            cumulative_actual += produced
            cumulative_plan = round((daily_plan / 24) * idx)
            production_trend.append({"time": row.get("bucket"), "actual": cumulative_actual, "plan": cumulative_plan})
            defect_trend.append(
                {
                    "time": row.get("bucket"),
                    "rate": round((_to_int(row.get("ng_qty")) / max(produced, 1)) * 100, 1) if produced > 0 else 0,
                }
            )
        bundle["managerProductionTrend"] = production_trend
        bundle["managerDefectTrend"] = defect_trend

    if snap.active_alarms:
        first_alarm_code = str(snap.active_alarms[0].get("alarm_code") or "")
        _set_web_kpi_detail(
            bundle,
            "mgr_oee",
            detail_id="common.alarm.detail",
            target_type="alarm",
            target_id=first_alarm_code,
            detail_title="주요 운영 리스크 상세",
        )
        bundle["activeAlarms"] = [
            {
                "alarmId": row.get("alarm_code") or "",
                "line": row.get("line_code") or "-",
                "equip": row.get("equip_code") or "-",
                "cause": row.get("cause_code") or "-",
                "severity": str(row.get("severity") or "info").lower(),
                "ack": str(row.get("ack_status") or "unack").lower(),
                "time": str(row.get("occurred_at") or ""),
            }
            for row in snap.active_alarms[:10]
        ]
        bundle["pendingActions"] = [
            {
                "priority": idx + 1,
                "title": f"{row.get('alarm_code') or 'ALARM'} 대응",
                "summary": str(row.get("message") or ""),
                "count": 1,
            }
            for idx, row in enumerate(snap.active_alarms[:3])
        ]
        bundle["events"] = [
            {
                "color": "#DC2626" if str(row.get("severity") or "").lower() == "critical" else "#D97706",
                "meta": f"{row.get('occurred_at')} · {str(row.get('severity') or '').upper()}",
                "text": str(row.get("message") or ""),
            }
            for row in snap.active_alarms[:4]
        ]
        worst = snap.active_alarms[0]
        bundle["riskOverall"] = {
            "severity": str(worst.get("severity") or "warning").lower(),
            "reason": f"{worst.get('line_code')} {worst.get('message') or '활성 알람 존재'}",
        }


def _web_promo_dashboard_bundle(**filters: Any) -> dict[str, Any]:
    return {
        "meta": _web_dashboard_meta("promo", **filters),
        "kpis": [
            {"id": "promo_today_output", "label": "오늘 생산량", "value": 9200, "unit": "pcs", "status": "warning", "meta": "actual/mock", "target": 12800},
            {"id": "promo_month_output", "label": "이번 달 생산", "value": 187400, "unit": "pcs", "status": "warning", "meta": "actual/mock", "target": 240000},
            {"id": "promo_oee", "label": "전체 OEE", "value": 71.2, "unit": "%", "status": "warning", "meta": "derived/mock"},
            {"id": "promo_defect_rate", "label": "현재 불량률", "value": 4.2, "unit": "%", "status": "critical", "meta": "derived/mock"},
            {"id": "promo_delivery_rate", "label": "납기 달성률", "value": 96.4, "unit": "%", "status": "ok", "meta": "actual/mock"},
        ],
        "promoWeekProduction": [
            {"day": "월(3/13)", "actual": 11800, "target": 12800},
            {"day": "화(3/14)", "actual": 12400, "target": 12800},
            {"day": "수(3/15)", "actual": 11200, "target": 12800},
            {"day": "목(3/16)", "actual": 12800, "target": 12800},
            {"day": "금(3/17)", "actual": 12100, "target": 12800},
            {"day": "토(3/18)", "actual": 10400, "target": 12800},
            {"day": "일(3/19)", "actual": 9200, "target": 12800},
        ],
        "promoLines": [
            {"line": "LINE A", "status": "run", "badge": "RUN", "output": 2840, "defectRate": "3.1%", "oee": 79, "oeeStatus": "warning"},
            {"line": "LINE B", "status": "run", "badge": "RUN", "output": 3120, "defectRate": "1.8%", "oee": 91, "oeeStatus": "ok"},
            {"line": "LINE C", "status": "down", "badge": "DOWN", "output": 1980, "stopTime": "38분", "oee": 48, "oeeStatus": "critical"},
            {"line": "LINE D", "status": "warn", "badge": "주의", "output": 1260, "defectRate": "4.8%", "oee": 63, "oeeStatus": "warning"},
        ],
        "promoTopDefects": [
            {"name": "short", "count": 34, "color": "#FF3A3A"},
            {"name": "open", "count": 22, "color": "#FFB020"},
            {"name": "spur", "count": 16, "color": "#4A7CFF"},
            {"name": "mousebite", "count": 10, "color": "#00D48A"},
            {"name": "pin_hole", "count": 6, "color": "#9B6DFF"},
        ],
        "promoCurrentAlarms": [
            {"severity": "critical", "line": "LINE C", "message": "MNT-04 설비 정지 — 즉시 조치 필요", "time": "14:55"},
            {"severity": "warning", "line": "LINE D", "message": "불량률 4.8% 임계 초과", "time": "15:00"},
            {"severity": "warning", "line": "LINE A", "message": "AOI-01 처리속도 저하 감지", "time": "15:02"},
        ],
        "promoMonthlyCompare": [
            {"label": "월 생산량", "value": "187,400", "diff": "▲ +4.2% vs 2월", "tone": "up"},
            {"label": "평균 OEE", "value": "71.2%", "diff": "▼ -2.1%p vs 2월", "tone": "down"},
            {"label": "불량률", "value": "4.2%", "diff": "▼ +0.8%p vs 2월", "tone": "down"},
            {"label": "납기 달성", "value": "96.4%", "diff": "▲ +1.2%p vs 2월", "tone": "up"},
        ],
        "promoTicker": [
            "LINE C MNT-04 긴급 수리 중 — 설비팀 즉시 지원 바람",
            "이번 달 목표 달성률 78% — 잔여 근무일 12일",
            "3월 품질 목표: 불량률 3.5% 이하",
            "오늘 17:00 전체 조회 — 2공장 회의실",
            "안전 제일 — 보호구 착용 필수",
            "이번 주 우수 작업자: LINE B 김○○ 님",
        ],
    }


def _apply_web_promo_live(bundle: dict[str, Any], snap: WebDashboardSnapshot) -> None:
    bundle["promoTopDefects"] = []
    bundle["promoCurrentAlarms"] = []
    bundle["promoWeekProduction"] = []
    bundle["promoLines"] = []
    bundle["promoMonthlyCompare"] = []
    bundle["promoTicker"] = []

    daily_plan, _ = _bundle_daily_plan(bundle, snap)
    oee_parts = _overall_oee_components(snap, daily_plan_total=daily_plan)
    yield_rate = round((snap.total_good / snap.total_produced) * 100, 2) if snap.total_produced > 0 else 0
    achievement = round((snap.total_produced / (daily_plan * max(snap.elapsed_ratio, 0.01))) * 100, 2)
    for item in bundle.get("kpis", []):
        if item.get("id") == "promo_today_output":
            item["value"] = snap.total_produced
            item["target"] = daily_plan
            item["status"] = "warning" if snap.total_produced < daily_plan else "ok"
            item["meta"] = "actual/db"
        elif item.get("id") == "promo_month_output":
            month_target = snap.scenario_date.day * daily_plan
            item["value"] = snap.month_produced
            item["target"] = month_target
            item["status"] = "warning" if snap.month_produced < month_target else "ok"
            item["meta"] = "actual/db"
        elif item.get("id") == "promo_oee":
            item["value"] = oee_parts["oee"]
            item["status"] = "critical" if oee_parts["oee"] < 70 else "warning" if oee_parts["oee"] < 85 else "ok"
            item["meta"] = "derived/db"
        elif item.get("id") == "promo_defect_rate":
            item["value"] = snap.defect_rate
            item["status"] = "critical" if snap.defect_rate >= 4 else "warning" if snap.defect_rate >= 2 else "ok"
            item["meta"] = "derived/db"
        elif item.get("id") == "promo_delivery_rate":
            item["value"] = achievement
            item["status"] = "ok" if achievement >= 95 else "warning"
            item["meta"] = "derived/db"

    if snap.top_defects:
        bundle["promoTopDefects"] = [
            {"name": row.get("defect_code") or "unknown", "count": int(row.get("cnt") or 0), "color": DEFECT_COLORS.get(str(row.get("defect_code") or "").lower(), "#6B7280")}
            for row in snap.top_defects[:5]
        ]
    if snap.active_alarms:
        bundle["promoCurrentAlarms"] = [
            {
                "severity": str(row.get("severity") or "info").lower(),
                "line": row.get("line_code") or "-",
                "message": str(row.get("message") or "알람 발생"),
                "time": str(row.get("occurred_at") or ""),
            }
            for row in snap.active_alarms[:5]
        ]
    if snap.daily_production:
        bundle["promoWeekProduction"] = [
            {
                "day": f"{['월', '화', '수', '목', '금', '토', '일'][row.get('work_date').weekday()]}({row.get('work_date').month}/{row.get('work_date').day})",
                "actual": _to_int(row.get("produced")),
                "target": daily_plan,
            }
            for row in snap.daily_production[-7:]
        ]
    if snap.line_production:
        bundle["promoLines"] = [
            {
                "line": row.get("line_code") or row.get("line_name") or "-",
                "status": "down" if str(row.get("latest_status") or "").lower() == "down" else "warn" if _to_float(row.get("risk_score")) >= 40 else "run",
                "badge": "DOWN" if str(row.get("latest_status") or "").lower() == "down" else "주의" if _to_float(row.get("risk_score")) >= 40 else "RUN",
                "output": _to_int(row.get("produced")),
                "defectRate": f"{round((_to_int(row.get('ng')) / max(_to_int(row.get('produced')), 1)) * 100, 2) if _to_int(row.get('produced')) > 0 else 0}%",
                "oee": _to_float(row.get("oee")),
                "oeeStatus": "critical" if _to_float(row.get("oee")) < 70 else "warning" if _to_float(row.get("oee")) < 85 else "ok",
            }
            for row in snap.line_production[:4]
        ]
    bundle["promoMonthlyCompare"] = [
        {"label": "일 생산량", "value": f"{snap.total_produced:,}", "diff": "DB 집계 기준", "tone": "up"},
        {"label": "전체 OEE", "value": f"{oee_parts['oee']}%", "diff": "가동률·성능·양품률 반영", "tone": "up" if oee_parts["oee"] >= 85 else "down"},
        {"label": "일 불량수", "value": f"{snap.total_ng:,}", "diff": "DB 집계 기준", "tone": "down" if snap.total_ng > 0 else "up"},
    ]
    bundle["promoTicker"] = [
        f"실시간 생산량 {snap.total_produced:,}",
        f"실시간 OEE {oee_parts['oee']}%",
        f"활성 알람 {snap.active_alarm_count}건",
    ]


def get_web_worker_dashboard(**filters: Any) -> dict[str, Any]:
    filters = _enforce_worker_line_filter(dict(filters))
    period_range = _resolve_period_range(filters)
    requested_date, scenario_date = _resolve_dashboard_dates(filters)
    snap = get_web_dashboard_snapshot(
        filters.get("line"),
        target_date=scenario_date,
        factory=filters.get("factory"),
        shift=filters.get("shift"),
    )
    bundle = _web_worker_dashboard_bundle(**filters)
    _apply_web_worker_live(bundle, snap)
    if period_range:
        start_date, end_date = period_range
        rows = _build_daily_compare_rows(filters, start_date, end_date)
        _apply_period_compare_worker(bundle, rows)
    _apply_web_snapshot_meta(bundle, snap, requested_date, scenario_date, **filters)
    bundle["meta"]["dataMode"] = "period_compare" if period_range else "live"
    return bundle


def get_web_qa_dashboard(**filters: Any) -> dict[str, Any]:
    period_range = _resolve_period_range(filters)
    requested_date, scenario_date = _resolve_dashboard_dates(filters)
    snap = get_web_dashboard_snapshot(
        filters.get("line"),
        target_date=scenario_date,
        factory=filters.get("factory"),
        shift=filters.get("shift"),
    )
    bundle = _web_qa_dashboard_bundle(**filters)
    _apply_web_qa_live(bundle, snap)
    if period_range:
        start_date, end_date = period_range
        rows = _build_daily_compare_rows(filters, start_date, end_date)
        _apply_period_compare_qa(bundle, rows)
    _apply_web_snapshot_meta(bundle, snap, requested_date, scenario_date, **filters)
    bundle["meta"]["dataMode"] = "period_compare" if period_range else "live"
    return bundle


def get_web_manager_dashboard(**filters: Any) -> dict[str, Any]:
    period_range = _resolve_period_range(filters)
    requested_date, scenario_date = _resolve_dashboard_dates(filters)
    snap = get_web_dashboard_snapshot(
        filters.get("line"),
        target_date=scenario_date,
        factory=filters.get("factory"),
        shift=filters.get("shift"),
    )
    bundle = _web_manager_dashboard_bundle(**filters)
    _apply_web_manager_live(bundle, snap)
    if period_range:
        start_date, end_date = period_range
        rows = _build_daily_compare_rows(filters, start_date, end_date)
        _apply_period_compare_manager(bundle, rows)
    _apply_web_snapshot_meta(bundle, snap, requested_date, scenario_date, **filters)
    bundle["meta"]["dataMode"] = "period_compare" if period_range else "live"
    return bundle


def get_web_promo_dashboard(**filters: Any) -> dict[str, Any]:
    period_range = _resolve_period_range(filters)
    requested_date, scenario_date = _resolve_dashboard_dates(filters)
    snap = get_web_dashboard_snapshot(
        filters.get("line"),
        target_date=scenario_date,
        factory=filters.get("factory"),
        shift=filters.get("shift"),
    )
    bundle = _web_promo_dashboard_bundle(**filters)
    _apply_web_promo_live(bundle, snap)
    if period_range:
        start_date, end_date = period_range
        rows = _build_daily_compare_rows(filters, start_date, end_date)
        _apply_period_compare_promo(bundle, rows)
    _apply_web_snapshot_meta(bundle, snap, requested_date, scenario_date, **filters)
    bundle["meta"]["dataMode"] = "period_compare" if period_range else "live"
    return bundle
