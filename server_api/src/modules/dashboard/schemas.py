"""dashboard API 응답 스키마 모음.

상단 KPI 응답, 데이터셋 응답, 상세 모달 응답, web_dashboard 전용 응답을
한 파일에서 관리한다. 프론트는 이 구조를 기준으로 카드/차트/모달을 렌더링한다.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# KPI / 보조지표 한 행
class KpiItem(BaseModel):
    # 카드 하나를 구성하는 최소 단위.
    # clickable/detailId/targetType/targetId는 KPI 클릭 상세와 직접 연결된다.
    key: str
    label: str
    value: Any = None
    unit: str = ""
    sourceType: str = "actual"
    dataMode: str = "live"
    detailId: str | None = None
    targetType: str | None = None
    targetId: str | None = None
    clickable: bool = False
    displayMode: str | None = None


class AssistiveItem(BaseModel):
    # KPI 옆에 붙는 보조 판단/추천 항목.
    # reasonSummary, confidence, severity, status 같은 해석용 필드를 추가로 담을 수 있다.
    key: str
    label: str
    value: Any = None
    sourceType: str = "derived"
    dataMode: str = "live"
    detailId: str | None = None
    targetType: str | None = None
    targetId: str | None = None
    clickable: bool = False
    reasonSummary: str | None = None
    confidence: float | None = None
    severity: str | None = None
    status: str | None = None


# KPI 묶음 응답
class DashboardKpiGroup(BaseModel):
    # /dashboard/kpis 응답에서 실제 KPI 배열을 감싸는 래퍼
    items: list[KpiItem] = Field(default_factory=list)


class DashboardAssistiveGroup(BaseModel):
    # /dashboard/kpis 응답에서 보조 항목 배열을 감싸는 래퍼
    items: list[AssistiveItem] = Field(default_factory=list)


class DashboardKPIResponse(BaseModel):
    # 상단 KPI 전용 API 응답 포맷
    # router.py의 /dashboard/kpis 엔드포인트와 1:1로 대응한다.
    screen: str
    screenId: str
    timezone: str
    dataMode: str
    effectiveAt: str
    updatedAt: str
    isPartial: bool = False
    isDelayed: bool = False
    staleLabel: str = "정상"
    coverage: dict[str, Any] = Field(default_factory=dict)
    kpis: DashboardKpiGroup
    assistive: DashboardAssistiveGroup


class DashboardDatasetsResponse(BaseModel):
    # 차트/표/보조 카드용 datasets 응답 포맷
    # router.py의 /dashboard/datasets 응답이며, 화면별 차트 원천 데이터가 들어간다.
    screen: str
    screenId: str
    timezone: str
    dataMode: str
    effectiveAt: str
    updatedAt: str
    isPartial: bool = False
    isDelayed: bool = False
    staleLabel: str = "정상"
    coverage: dict[str, Any] = Field(default_factory=dict)
    datasets: dict[str, Any] = Field(default_factory=dict)


class DashboardDetailRequest(BaseModel):
    # 상세 모달 호출 시 프론트가 보내는 최소 파라미터
    # router.py는 Query로 받고, service.py는 이 모델로 묶어서 detail 규칙을 검증한다.
    detailId: str
    targetType: str
    targetId: str
    subKey: str = ""


class DashboardDetailResponse(BaseModel):
    # detail API 공통 응답
    # 기본 요약(summary), 로그(logs), 연관 항목(relatedItems), 액션(actions)을 공통 구조로 제공한다.
    detailId: str
    targetType: str
    targetId: str
    subKey: str = ""
    screen: str | None = None
    screenId: str | None = None
    timezone: str = "Asia/Seoul"
    dataMode: str = "live"
    effectiveAt: str
    updatedAt: str
    isPartial: bool = False
    isDelayed: bool = False
    staleLabel: str = "정상"
    coverage: dict[str, Any] = Field(default_factory=dict)
    summary: list[dict[str, Any]] = Field(default_factory=list)
    logs: list[dict[str, Any]] = Field(default_factory=list)
    relatedItems: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


# web_dashboard 공통 메타/필터
class WebDashboardFilters(BaseModel):
    # /dashboard/web/* 에서 받은 원본 필터를 meta.filters 안에 그대로 남긴다.
    factory: str | None = None
    line: str | None = None
    shift: str | None = None
    period: str | None = None
    tz: str | None = None
    date_from: str | None = None
    date_to: str | None = None

    model_config = ConfigDict(extra="allow")


class WebDashboardMeta(BaseModel):
    # web_dashboard 모든 탭이 공통으로 갖는 메타 정보.
    # requestedDate / scenarioDate / viewMode / line은 화면 문구와 탭 제목에 직접 반영된다.
    screen: str
    screenId: str
    timezone: str
    effectiveAt: str
    updatedAt: str
    requestedDate: str | None = None
    scenarioDate: str | None = None
    line: str | None = None
    viewMode: str | None = None
    requestedDateRange: dict[str, Any] | None = None
    filters: WebDashboardFilters = Field(default_factory=WebDashboardFilters)
    dataMode: str = "live"

    model_config = ConfigDict(extra="allow")


# web_dashboard 탭별 기본 응답 구조
class WebDashboardResponseBase(BaseModel):
    # worker / qa / manager / promo 모두 공통으로 meta, kpis, notice를 가진다.
    meta: WebDashboardMeta
    kpis: list[dict[str, Any]] = Field(default_factory=list)
    notice: dict[str, Any] | None = None

    model_config = ConfigDict(extra="allow")


class WorkerWebDashboardResponse(WebDashboardResponseBase):
    # 작업자 탭: 내 라인 기준 카드/차트/목록
    # lineTemperature, statusGrid, actionQueue, globalNotices가 worker 화면 핵심 데이터다.
    lineTemperature: dict[str, Any] | None = None
    hint: dict[str, Any] | None = None
    statusGrid: list[dict[str, Any]] = Field(default_factory=list)
    actionQueue: list[dict[str, Any]] = Field(default_factory=list)
    globalNotices: list[dict[str, Any]] = Field(default_factory=list)
    ngTrend: list[dict[str, Any]] = Field(default_factory=list)
    ngTypes: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)


class QaWebDashboardResponse(WebDashboardResponseBase):
    # 품질관리 탭: 불량/재검/이슈 중심
    # recheckQueue, defectTrend, issues는 QA 메인 카드와 상세 모달의 원천 데이터다.
    hint: dict[str, Any] | None = None
    topDefects: list[dict[str, Any]] = Field(default_factory=list)
    recheckQueue: list[dict[str, Any]] = Field(default_factory=list)
    defectTrend: list[dict[str, Any]] = Field(default_factory=list)
    issues: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)


class ManagerWebDashboardResponse(WebDashboardResponseBase):
    # 관리자 탭: OEE/리스크/알람/생산 추세 중심
    # managerLineOee / activeAlarms / riskLines / managerProductionTrend가 주요 시각화 데이터다.
    riskOverall: dict[str, Any] | None = None
    riskLines: list[dict[str, Any]] = Field(default_factory=list)
    pendingActions: list[dict[str, Any]] = Field(default_factory=list)
    activeAlarms: list[dict[str, Any]] = Field(default_factory=list)
    managerLineOee: list[dict[str, Any]] = Field(default_factory=list)
    managerProductionTrend: list[dict[str, Any]] = Field(default_factory=list)
    managerDefectTrend: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)


class PromoWebDashboardResponse(WebDashboardResponseBase):
    # 공용 송출 탭: 전광판/대형 화면용 요약 카드
    # promoWeekProduction / promoLines / promoTopDefects / promoCurrentAlarms / promoTicker를 포함한다.
    promoWeekProduction: list[dict[str, Any]] = Field(default_factory=list)
    promoLines: list[dict[str, Any]] = Field(default_factory=list)
    promoTopDefects: list[dict[str, Any]] = Field(default_factory=list)
    promoCurrentAlarms: list[dict[str, Any]] = Field(default_factory=list)
    promoMonthlyCompare: list[dict[str, Any]] = Field(default_factory=list)
    promoTicker: list[Any] = Field(default_factory=list)
