"""dashboard HTTP 라우터.

이 파일은 프론트가 호출하는 dashboard API의 진입점이다.
요청 파라미터를 FastAPI Query/Body로 받고, service 계층에 넘긴 뒤,
response_model로 응답 계약을 고정한다.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query

from src.modules.auth.jwt import get_current_user
from src.modules.dashboard.schemas import (
    DashboardDetailRequest,
    DashboardDetailResponse,
    DashboardDatasetsResponse,
    DashboardKPIResponse,
    ManagerWebDashboardResponse,
    PromoWebDashboardResponse,
    QaWebDashboardResponse,
    WorkerWebDashboardResponse,
)
from src.modules.dashboard.service import (
    dashboard_status_placeholder,
    get_dashboard_detail,
    get_dashboard_kpis,
    get_dashboard_datasets,
    get_web_manager_dashboard,
    get_web_promo_dashboard,
    get_web_qa_dashboard,
    get_web_worker_dashboard,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/status")
def dashboard_status(current_user = Depends(get_current_user)):
    # 운영 상태 확인용 가벼운 헬스 체크.
    # 어떤 screen이 지원되는지와 live 소스 유무를 빠르게 확인할 때 쓴다.
    return dashboard_status_placeholder()


@router.get("/kpis", response_model=DashboardKPIResponse)
def read_dashboard_kpis(
    screen: str = Query(..., pattern="^(worker|qa|manager|promo)$"),
    tz: str | None = Query(default=None),
    factory: str | None = Query(default=None),
    line: str | None = Query(default=None),
    shift: str | None = Query(default=None),
    period: str | None = Query(default=None),
    current_user = Depends(get_current_user),
) -> DashboardKPIResponse:
    # 상단 KPI 전용 응답.
    # 입력: screen + 공통 필터(line/factory/shift/period/tz)
    # 출력: DashboardKPIResponse(kpis, assistive)
    return get_dashboard_kpis(screen=screen, tz=tz, factory=factory, line=line, shift=shift, period=period)


@router.get("/datasets", response_model=DashboardDatasetsResponse)
def read_dashboard_datasets(
    screen: str = Query(..., pattern="^(worker|qa|manager|promo)$"),
    tz: str | None = Query(default=None),
    factory: str | None = Query(default=None),
    line: str | None = Query(default=None),
    shift: str | None = Query(default=None),
    period: str | None = Query(default=None),
    current_user = Depends(get_current_user),
) -> DashboardDatasetsResponse:
    # 차트/표/보조 카드용 datasets 응답.
    # KPI와 달리 datasets 딕셔너리 안에 화면별 원본 시각화 데이터를 담아 내려준다.
    return get_dashboard_datasets(screen=screen, tz=tz, factory=factory, line=line, shift=shift, period=period)


@router.get("/detail", response_model=DashboardDetailResponse)
def read_dashboard_detail(
    screen: str = Query(..., pattern="^(worker|qa|manager|promo)$"),
    detailId: str = Query(...),
    targetType: str = Query(...),
    targetId: str = Query(...),
    subKey: str = Query(default=""),
    current_user = Depends(get_current_user),
) -> DashboardDetailResponse:
    # 공통 상세 모달 API.
    # 프론트는 detailId / targetType / targetId 조합으로
    # lot, alarm, defect, event 같은 상세 데이터를 요청한다.
    return get_dashboard_detail(
        screen=screen,
        request=DashboardDetailRequest(
            detailId=detailId,
            targetType=targetType,
            targetId=targetId,
            subKey=subKey,
        ),
    )


@router.get("/web/worker", response_model=WorkerWebDashboardResponse)
def read_web_worker_dashboard(
    tz: str | None = Query(default=None),
    factory: str | None = Query(default=None),
    line: str | None = Query(default=None),
    shift: str | None = Query(default=None),
    period: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    current_user=Depends(get_current_user),
) -> WorkerWebDashboardResponse:
    # 작업자 web_dashboard 메인 bundle.
    # worker 계정이면 service 계층에서 line 필터를 현재 사용자 라인으로 강제한다.
    # 출력은 WorkerWebDashboardResponse(meta, kpis, statusGrid, actionQueue, events ...)
    return get_web_worker_dashboard(
        tz=tz,
        factory=factory,
        line=line,
        shift=shift,
        period=period,
        date_from=date_from,
        date_to=date_to,
        current_user=current_user,
    )


@router.get("/web/qa", response_model=QaWebDashboardResponse)
def read_web_qa_dashboard(
    tz: str | None = Query(default=None),
    factory: str | None = Query(default=None),
    line: str | None = Query(default=None),
    shift: str | None = Query(default=None),
    period: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    current_user=Depends(get_current_user),
) -> QaWebDashboardResponse:
    # 품질관리자 web_dashboard 메인 bundle.
    # 재검 큐, 불량 추세, 품질 이슈, 최근 이벤트를 한 번에 묶어 내려준다.
    return get_web_qa_dashboard(
        tz=tz,
        factory=factory,
        line=line,
        shift=shift,
        period=period,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/web/manager", response_model=ManagerWebDashboardResponse)
def read_web_manager_dashboard(
    tz: str | None = Query(default=None),
    factory: str | None = Query(default=None),
    line: str | None = Query(default=None),
    shift: str | None = Query(default=None),
    period: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    current_user=Depends(get_current_user),
) -> ManagerWebDashboardResponse:
    # 관리자 web_dashboard 메인 bundle.
    # OEE, 리스크, 생산 추세, 활성 알람, 라인 비교 데이터를 포함한다.
    return get_web_manager_dashboard(
        tz=tz,
        factory=factory,
        line=line,
        shift=shift,
        period=period,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/web/promo", response_model=PromoWebDashboardResponse)
def read_web_promo_dashboard(
    tz: str | None = Query(default=None),
    factory: str | None = Query(default=None),
    line: str | None = Query(default=None),
    shift: str | None = Query(default=None),
    period: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    current_user=Depends(get_current_user),
) -> PromoWebDashboardResponse:
    # 공용 송출용 web_dashboard 메인 bundle.
    # 대형 화면/전광판 노출에 맞춰 주간 생산량, 라인 현황, top defect, ticker를 반환한다.
    return get_web_promo_dashboard(
        tz=tz,
        factory=factory,
        line=line,
        shift=shift,
        period=period,
        date_from=date_from,
        date_to=date_to,
    )
