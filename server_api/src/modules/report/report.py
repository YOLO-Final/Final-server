from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Mapping

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def build_report_pdf(report_data: Mapping[str, str | int | float]) -> bytes:
    """Create a simple one-page PDF report and return raw bytes.

    This function is intentionally small so it can be expanded later with
    DB-driven values, table layouts, and branding assets.
    """
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)

    width, height = A4
    y = height - 60

    pdf.setTitle("Inspection Report")
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(40, y, "Inspection Report")

    y -= 28
    pdf.setFont("Helvetica", 11)
    pdf.drawString(40, y, f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    y -= 30
    pdf.setFont("Helvetica", 12)

    for key, value in report_data.items():
        pdf.drawString(40, y, f"{key}: {value}")
        y -= 20
        if y < 50:
            pdf.showPage()
            y = height - 60
            pdf.setFont("Helvetica", 12)

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()
