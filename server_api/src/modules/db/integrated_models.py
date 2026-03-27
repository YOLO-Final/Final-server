from datetime import datetime,date
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Integer,
    String,
    Boolean,
    Date,
    DateTime,
    Float,
    Text,
    ForeignKey,
    Index,
    UniqueConstraint,
    CheckConstraint,
    Numeric,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.lib.database import Base

# NOTE:
# This module is no longer part of the current web_dashboard table-registration path.
# For web_dashboard runtime and init_db, use src.modules.dashboard.db.model instead.
# Keep this file only for separately managed integrated-model references.

# =========================================================
# 1) Core Master Tables
# =========================================================
class Factory(Base):
    __tablename__ = "factories"

    factory_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    factory_code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    factory_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ProductModel(Base):
    __tablename__ = "product_models"
    __table_args__ = (
        Index("idx_product_models_active", "is_active"),
    )

    model_code: Mapped[str] = mapped_column(String(60), primary_key=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    alert_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    danger_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Line(Base):
    __tablename__ = "lines"
    __table_args__ = (
        Index("idx_lines_factory_id", "factory_id"),
        Index("idx_lines_active", "is_active"),
    )

    line_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    factory_id: Mapped[int] = mapped_column(ForeignKey("factories.factory_id"), nullable=False)
    line_code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    line_name: Mapped[str] = mapped_column(String(100), nullable=False)
    line_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    current_model_code: Mapped[Optional[str]] = mapped_column(
        ForeignKey("product_models.model_code"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Equipment(Base):
    __tablename__ = "equipment"
    __table_args__ = (
        Index("idx_equipment_line_id", "line_id"),
        Index("idx_equipment_type", "equip_type"),
        Index("idx_equipment_active", "is_active"),
    )

    equip_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.line_id"), nullable=False)
    equip_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    equip_name: Mapped[str] = mapped_column(String(100), nullable=False)
    equip_type: Mapped[str] = mapped_column(String(50), nullable=False)
    vendor: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    install_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        Index("idx_employees_line_id", "line_id"),
        Index("idx_employees_role_code", "role_code"),
    )

    employee_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    employee_no: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    employee_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role_code: Mapped[str] = mapped_column(String(30), nullable=False)
    line_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lines.line_id"), nullable=True)
    shift_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


# =========================================================
# 2) Core Fact / History Tables
# =========================================================
class ProductionRecord(Base):
    __tablename__ = "production_records"
    __table_args__ = (
        Index("idx_production_records_line_time", "line_id", "recorded_at"),
        Index("idx_production_records_factory_time", "factory_id", "recorded_at"),
        Index("idx_production_records_work_date", "work_date"),
        Index("idx_production_records_lot_id", "lot_id"),
    )

    production_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    factory_id: Mapped[int] = mapped_column(ForeignKey("factories.factory_id"), nullable=False)
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.line_id"), nullable=False)
    equip_id: Mapped[Optional[int]] = mapped_column(ForeignKey("equipment.equip_id"), nullable=True)
    lot_id: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    model_code: Mapped[Optional[str]] = mapped_column(ForeignKey("product_models.model_code"), nullable=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    work_shift: Mapped[str] = mapped_column(String(30), nullable=False)
    produced_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    good_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    ng_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class EquipmentStatusHistory(Base):
    __tablename__ = "equipment_status_history"
    __table_args__ = (
        CheckConstraint(
            "status_code IN ('run', 'idle', 'down', 'maint')",
            name="ck_equipment_status_history_status_code",
        ),
        Index("idx_equipment_status_history_equip_time", "equip_id", "started_at"),
        Index("idx_equipment_status_history_line_time", "line_id", "started_at"),
        Index("idx_equipment_status_history_status", "status_code"),
    )

    status_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.line_id"), nullable=False)
    equip_id: Mapped[int] = mapped_column(ForeignKey("equipment.equip_id"), nullable=False)
    status_code: Mapped[str] = mapped_column(String(20), nullable=False)
    reason_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reason_text: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class InspectionResult(Base):
    __tablename__ = "inspection_results"
    __table_args__ = (
        Index("idx_inspection_results_line_time", "line_id", "recorded_at"),
        Index("idx_inspection_results_lot_id", "lot_id"),
        Index("idx_inspection_results_type", "inspection_type"),
    )

    inspection_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.line_id"), nullable=False)
    equip_id: Mapped[Optional[int]] = mapped_column(ForeignKey("equipment.equip_id"), nullable=True)
    lot_id: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    model_code: Mapped[Optional[str]] = mapped_column(ForeignKey("product_models.model_code"), nullable=True)
    inspection_type: Mapped[str] = mapped_column(String(50), nullable=False)
    total_checked_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    pass_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    fail_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DefectResult(Base):
    __tablename__ = "defect_results"
    __table_args__ = (
        Index("idx_defect_results_line_time", "line_id", "recorded_at"),
        Index("idx_defect_results_defect_code", "defect_code"),
        Index("idx_defect_results_lot_id", "lot_id"),
        Index("idx_defect_results_severity", "severity"),
    )

    defect_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.line_id"), nullable=False)
    equip_id: Mapped[Optional[int]] = mapped_column(ForeignKey("equipment.equip_id"), nullable=True)
    lot_id: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    model_code: Mapped[Optional[str]] = mapped_column(ForeignKey("product_models.model_code"), nullable=True)
    defect_code: Mapped[str] = mapped_column(String(60), nullable=False)
    defect_name: Mapped[str] = mapped_column(String(100), nullable=False)
    defect_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    severity: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    cause_code: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    cause_text: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    detected_by_employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.employee_id"),
        nullable=True,
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Alarm(Base):
    __tablename__ = "alarms"
    __table_args__ = (
        CheckConstraint("severity IN ('critical', 'warning', 'info', 'ok')", name="ck_alarms_severity"),
        CheckConstraint("status IN ('active', 'cleared', 'hold')", name="ck_alarms_status"),
        Index("idx_alarms_line_time", "line_id", "occurred_at"),
        Index("idx_alarms_equip_time", "equip_id", "occurred_at"),
        Index("idx_alarms_status", "status"),
        Index("idx_alarms_severity", "severity"),
    )

    alarm_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.line_id"), nullable=False)
    equip_id: Mapped[Optional[int]] = mapped_column(ForeignKey("equipment.equip_id"), nullable=True)
    alarm_code: Mapped[str] = mapped_column(String(60), nullable=False)
    alarm_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    cause_code: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cleared_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AlarmAckHistory(Base):
    __tablename__ = "alarm_ack_history"
    __table_args__ = (
        CheckConstraint("ack_status IN ('unack', 'hold', 'ack')", name="ck_alarm_ack_history_ack_status"),
        Index("idx_alarm_ack_history_alarm_id", "alarm_id_ref", "handled_at"),
        Index("idx_alarm_ack_history_status", "ack_status"),
    )

    ack_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    alarm_id_ref: Mapped[int] = mapped_column(ForeignKey("alarms.alarm_id"), nullable=False)
    ack_status: Mapped[str] = mapped_column(String(20), nullable=False)
    handled_by: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    handled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class RecheckQueue(Base):
    __tablename__ = "recheck_queue"
    __table_args__ = (
        CheckConstraint("priority IN ('LOW', 'MEDIUM', 'HIGH')", name="ck_recheck_queue_priority"),
        CheckConstraint("severity IN ('critical', 'warning', 'info')", name="ck_recheck_queue_severity"),
        CheckConstraint("status IN ('queued', 'in_progress', 'done', 'hold')", name="ck_recheck_queue_status"),
        Index("idx_recheck_queue_line_status", "line_id", "status", "queued_at"),
        Index("idx_recheck_queue_lot_id", "lot_id"),
        Index("idx_recheck_queue_priority", "priority"),
    )

    recheck_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    lot_id: Mapped[str] = mapped_column(String(60), nullable=False)
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.line_id"), nullable=False)
    equip_id: Mapped[Optional[int]] = mapped_column(ForeignKey("equipment.equip_id"), nullable=True)
    defect_code: Mapped[str] = mapped_column(String(60), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", server_default="queued")
    count_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    cause_text: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    owner_employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class EventLog(Base):
    __tablename__ = "event_logs"
    __table_args__ = (
        Index("idx_event_logs_time", "recorded_at"),
        Index("idx_event_logs_line_time", "line_id", "recorded_at"),
        Index("idx_event_logs_severity", "severity"),
    )

    event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    line_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lines.line_id"), nullable=True)
    equip_id: Mapped[Optional[int]] = mapped_column(ForeignKey("equipment.equip_id"), nullable=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[str] = mapped_column(String(255), nullable=False)
    meta_text: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class LineEnvironment(Base):
    __tablename__ = "line_environment"
    __table_args__ = (
        Index("idx_line_environment_line_time", "line_id", "recorded_at"),
        Index("idx_line_environment_metric", "metric_name", "recorded_at"),
    )

    env_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.line_id"), nullable=False)
    sensor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(50), nullable=False)
    metric_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


# =========================================================
# 3) Extension / Support Tables
# =========================================================
class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("idx_notifications_line_triggered_at", "line_id", "triggered_at"),
        Index("idx_notifications_target_role", "target_role"),
    )

    noti_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    line_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lines.line_id"), nullable=True)
    target_role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    message: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_dismissed: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        default=False,
        server_default="false",
    )


class MlPrediction(Base):
    __tablename__ = "ml_predictions"
    __table_args__ = (
        Index("idx_ml_predictions_line_predicted_at", "line_id", "predicted_at"),
        Index("idx_ml_predictions_pred_type", "pred_type"),
    )

    pred_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.line_id"), nullable=False)
    pred_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    predicted_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    predicted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class VisionResult(Base):
    __tablename__ = "vision_result"
    __table_args__ = (
        Index("idx_vision_result_request_id", "request_id"),
        Index("idx_vision_result_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    image_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    result_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    defect_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    created_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)


class FaceEmbeddingTable(Base):
    __tablename__ = "face_embedding_table"
    __table_args__ = (
        UniqueConstraint("employee_no", name="uq_face_embedding_table_employee_no"),
    )

    embedding_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    employee_no: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    embedding_json: Mapped[str] = mapped_column(Text, nullable=False)


class VectorTable(Base):
    __tablename__ = "vector_table"
    __table_args__ = (
        UniqueConstraint("employee_no", name="uq_vector_table_employee_no"),
    )

    vector_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    employee_no: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, unique=True)
    face_embedding: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
