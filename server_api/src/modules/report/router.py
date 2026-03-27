from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.lib.database import get_db
from src.modules.report.db.schema import ResultSummaryResponse
from src.modules.report.service import generate_report_pdf, get_result_summary, report_status_placeholder

router = APIRouter(prefix="/report", tags=["report"])


@router.get("/status")
def report_status():
    return report_status_placeholder()


@router.get("/result-summary", response_model=ResultSummaryResponse)
def result_summary(
    target_date: date | None = Query(default=None, description="조회 기준 날짜 (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    return get_result_summary(db, target_date=target_date)


@router.get("/pdf")
def download_report_pdf(
    target_date: date | None = Query(default=None, description="조회 기준 날짜 (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    pdf_bytes = generate_report_pdf(db, target_date=target_date)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="inspection_report.pdf"'},
    )
