from pydantic import BaseModel


class ReportRequest(BaseModel):
    report_type: str


class ResultSummaryCard(BaseModel):
    total: int
    ok: int
    ng: int
    yield_pct: float


class ResultDistributionItem(BaseModel):
    defect_type: str
    count: int


class ResultModelCard(BaseModel):
    model_id: str | None = None
    model_name: str | None = None
    unit: str | None = None
    alert_threshold: float | None = None
    danger_threshold: float | None = None


class ResultSystemCard(BaseModel):
    camera_status: str
    camera_resolution: str
    ai_model: str
    data_date: str | None = None


class ResultSummaryResponse(BaseModel):
    summary: ResultSummaryCard
    ng_distribution: list[ResultDistributionItem]
    model: ResultModelCard
    system: ResultSystemCard
