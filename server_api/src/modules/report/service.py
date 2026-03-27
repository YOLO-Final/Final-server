from __future__ import annotations

import re
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.modules.report.report import build_report_pdf


def report_status_placeholder() -> dict:
    return {
        "module": "report",
        "message": "Report skeleton is ready. Implement reporting and PDF generation here.",
    }


def _fetch_one(db: Session, stmt: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    row = db.execute(text(stmt), params or {}).mappings().first()
    return dict(row) if row else None


def _fetch_all(db: Session, stmt: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    rows = db.execute(text(stmt), params or {}).mappings().all()
    return [dict(row) for row in rows]


def _safe_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None


def _decode_defect_type_label(raw_value: Any) -> str:
    value = str(raw_value or "").strip()
    if not value:
        return "unknown"

    # Stored format example: 101010 -> 1번, 3번, 5번
    if re.fullmatch(r"[01]+", value):
        positions = [f"{idx + 1}번" for idx, bit in enumerate(value) if bit == "1"]
        if positions:
            return ", ".join(positions)
        return "none"

    return value


def _aggregate_defect_type_buckets(rows: list[dict[str, Any]], bucket_size: int = 6) -> list[dict[str, int | str]]:
    label_map = [
        "short",
        "open",
        "mouse_bite",
        "spur",
        "missing_hole",
        "spurious_copper",
    ]
    buckets = [0 for _ in range(bucket_size)]

    for row in rows:
        code = str(row.get("defect_type") or "").strip()
        row_count = _safe_int(row.get("count"))
        if row_count <= 0:
            continue
        if not re.fullmatch(r"[01]+", code):
            continue

        for idx in range(min(bucket_size, len(code))):
            if code[idx] == "1":
                buckets[idx] += row_count

    result: list[dict[str, int | str]] = []
    for idx in range(bucket_size):
        defect_label = label_map[idx] if idx < len(label_map) else f"type_{idx + 1}"
        result.append({"defect_type": defect_label, "count": buckets[idx]})
    return result
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_result_summary(db: Session, target_date: date | None = None) -> dict[str, Any]:
    latest = _fetch_one(
        db,
        """
        SELECT max(created_at::date) AS latest_date
        FROM vision_result
        """,
    )
    latest_date = latest.get("latest_date") if latest else None
    selected_date = target_date or latest_date

    summary_stmt = """
        SELECT
          count(*) AS total_rows,
                    count(*) FILTER (WHERE lower(coalesce(result_status::text, '')) = 'ok') AS ok_rows,
                    count(*) FILTER (WHERE lower(coalesce(result_status::text, '')) = 'ng') AS ng_rows
        FROM vision_result
    """
    summary_params: dict[str, Any] = {}

    ng_stmt = """
        SELECT
                    coalesce(vr.defect_type::text, '') AS defect_type,
          count(*) AS count
                FROM vision_result vr
                WHERE lower(coalesce(vr.result_status::text, '')) = 'ng'
    """
    ng_params: dict[str, Any] = {}

    if selected_date is not None:
        summary_stmt += " WHERE created_at::date = :target_date"
        ng_stmt += " AND created_at::date = :target_date"
        summary_params["target_date"] = selected_date
        ng_params["target_date"] = selected_date

    ng_stmt += " GROUP BY coalesce(vr.defect_type::text, '') ORDER BY count(*) DESC, defect_type ASC"

    summary_row = _fetch_one(db, summary_stmt, summary_params) or {}
    total = _safe_int(summary_row.get("total_rows"))
    ok = _safe_int(summary_row.get("ok_rows"))
    ng = _safe_int(summary_row.get("ng_rows"))
    yield_pct = round((ok / total) * 100, 2) if total > 0 else 0.0

    ng_rows = _fetch_all(db, ng_stmt, ng_params)
    ng_distribution = _aggregate_defect_type_buckets(ng_rows, bucket_size=6)

    model_row = _fetch_one(
        db,
        """
        SELECT
          pl.model_id AS model_id,
          pm.model_name AS model_name,
          pm.unit AS unit,
          pm.alert_threshold AS alert_threshold,
          pm.danger_threshold AS danger_threshold
        FROM production_logs pl
        LEFT JOIN product_models pm ON pm.model_id = pl.model_id
        ORDER BY pl.log_id DESC
        LIMIT 1
        """,
    )
    if model_row is None:
        model_row = _fetch_one(
            db,
            """
            SELECT
              pm.model_id AS model_id,
              pm.model_name AS model_name,
              pm.unit AS unit,
              pm.alert_threshold AS alert_threshold,
              pm.danger_threshold AS danger_threshold
            FROM product_models pm
            ORDER BY pm.model_id ASC
            LIMIT 1
            """,
        ) or {}

    ai_model_row = _fetch_one(
        db,
        """
        SELECT pred_type
        FROM ml_predictions
        WHERE pred_type IS NOT NULL
        ORDER BY pred_id DESC
        LIMIT 1
        """,
    ) or {}

    camera_connected_row = _fetch_one(
        db,
        """
        SELECT count(*) AS connected_count
        FROM equipment
        WHERE lower(coalesce(status, '')) IN ('connected', 'run', 'running', 'ok', 'idle')
        """,
    ) or {}
    connected_count = _safe_int(camera_connected_row.get("connected_count"))

    return {
        "summary": {
            "total": total,
            "ok": ok,
            "ng": ng,
            "yield_pct": yield_pct,
        },
        "ng_distribution": ng_distribution,
        "model": {
            "model_id": model_row.get("model_id"),
            "model_name": model_row.get("model_name"),
            "unit": model_row.get("unit"),
            "alert_threshold": _safe_float(model_row.get("alert_threshold")),
            "danger_threshold": _safe_float(model_row.get("danger_threshold")),
        },
        "system": {
            "camera_status": "Connected" if connected_count > 0 else "Disconnected",
            "camera_resolution": "N/A (not stored in DB)",
            "ai_model": str(ai_model_row.get("pred_type") or "N/A"),
            "data_date": str(selected_date) if selected_date is not None else None,
        },
    }


def generate_report_pdf(db: Session, target_date: date | None = None) -> bytes:
    payload = get_result_summary(db, target_date=target_date)
    summary = payload.get("summary", {})
    model = payload.get("model", {})
    system = payload.get("system", {})

    pdf_data = {
        "Total": _safe_int(summary.get("total")),
        "OK": _safe_int(summary.get("ok")),
        "NG": _safe_int(summary.get("ng")),
        "Yield": f"{float(summary.get('yield_pct', 0.0)):.2f}%",
        "Model ID": str(model.get("model_id") or "N/A"),
        "Model Name": str(model.get("model_name") or "N/A"),
        "Camera": str(system.get("camera_status") or "N/A"),
        "AI Model": str(system.get("ai_model") or "N/A"),
        "Data Date": str(system.get("data_date") or "N/A"),
    }
    return build_report_pdf(pdf_data)
