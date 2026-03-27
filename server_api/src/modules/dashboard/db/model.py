"""web_dashboard 전용 ORM 모델 모음.

이 파일은 wed_dashboard 스키마 기준의 운영 테이블 구조를 한곳에 모아둔다.
Factory -> Line -> Equipment -> Employee 같은 마스터 데이터와,
생산/검사/알람/재검/이벤트/환경 로그 같은 운영 데이터를 함께 정의한다.
"""

from datetime import date, datetime

from sqlalchemy import (
    BIGINT,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.lib.database import Base


# 공장 / 라인 / 설비 / 작업자 마스터
class FactoryTable(Base):
    __tablename__ = "factories"

    factory_id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    factory_code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    factory_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))


class LineTable(Base):
    __tablename__ = "lines"
    __table_args__ = (
        Index("idx_lines_factory_id", "factory_id"),
        Index("idx_lines_active", "is_active"),
    )

    line_id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    factory_id: Mapped[int] = mapped_column(ForeignKey("factories.factory_id"), nullable=False)
    line_code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    line_name: Mapped[str] = mapped_column(String(100), nullable=False)
    line_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))


class EquipmentTable(Base):
    __tablename__ = "equipments"
    __table_args__ = (
        Index("idx_equipments_line_id", "line_id"),
        Index("idx_equipments_type", "equip_type"),
        Index("idx_equipments_active", "is_active"),
    )

    equip_id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.line_id"), nullable=False)
    equip_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    equip_name: Mapped[str] = mapped_column(String(100), nullable=False)
    equip_type: Mapped[str] = mapped_column(String(50), nullable=False)
    vendor: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    install_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))


class EmployeeTable(Base):
    __tablename__ = "employees"
    __table_args__ = (
        Index("idx_employees_line_id", "line_id"),
        Index("idx_employees_role_code", "role_code"),
    )

    employee_id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    employee_no: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    employee_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role_code: Mapped[str] = mapped_column(String(30), nullable=False)
    line_id: Mapped[int | None] = mapped_column(ForeignKey("lines.line_id"), nullable=True)
    shift_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))


# 생산 / 설비 상태 / 검사 / 불량 결과
class ProductionRecordTable(Base):
    __tablename__ = "production_records"
    __table_args__ = (
        Index("idx_production_records_line_time", "line_id", "recorded_at"),
        Index("idx_production_records_factory_time", "factory_id", "recorded_at"),
        Index("idx_production_records_work_date", "work_date"),
        Index("idx_production_records_lot_id", "lot_id"),
    )

    production_id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    factory_id: Mapped[int] = mapped_column(ForeignKey("factories.factory_id"), nullable=False)
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.line_id"), nullable=False)
    equip_id: Mapped[int | None] = mapped_column(ForeignKey("equipments.equip_id"), nullable=True)
    lot_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    model_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    work_shift: Mapped[str] = mapped_column(String(30), nullable=False)
    produced_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    good_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    ng_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))


class EquipmentStatusHistoryTable(Base):
    __tablename__ = "equipment_status_history"
    __table_args__ = (
        CheckConstraint("status_code IN ('run', 'idle', 'down', 'maint')", name="ck_equipment_status_history_status_code"),
        Index("idx_equipment_status_history_equip_time", "equip_id", "started_at"),
        Index("idx_equipment_status_history_line_time", "line_id", "started_at"),
        Index("idx_equipment_status_history_status", "status_code"),
    )

    status_id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.line_id"), nullable=False)
    equip_id: Mapped[int] = mapped_column(ForeignKey("equipments.equip_id"), nullable=False)
    status_code: Mapped[str] = mapped_column(String(20), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reason_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))


class InspectionResultTable(Base):
    __tablename__ = "inspection_results"
    __table_args__ = (
        Index("idx_inspection_results_line_time", "line_id", "recorded_at"),
        Index("idx_inspection_results_lot_id", "lot_id"),
        Index("idx_inspection_results_type", "inspection_type"),
    )

    inspection_id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.line_id"), nullable=False)
    equip_id: Mapped[int | None] = mapped_column(ForeignKey("equipments.equip_id"), nullable=True)
    lot_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    model_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    inspection_type: Mapped[str] = mapped_column(String(50), nullable=False)
    total_checked_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    pass_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    fail_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))


class DefectResultTable(Base):
    __tablename__ = "defect_results"
    __table_args__ = (
        Index("idx_defect_results_line_time", "line_id", "recorded_at"),
        Index("idx_defect_results_defect_code", "defect_code"),
        Index("idx_defect_results_lot_id", "lot_id"),
        Index("idx_defect_results_severity", "severity"),
    )

    defect_id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.line_id"), nullable=False)
    equip_id: Mapped[int | None] = mapped_column(ForeignKey("equipments.equip_id"), nullable=True)
    lot_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    model_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    defect_code: Mapped[str] = mapped_column(String(60), nullable=False)
    defect_name: Mapped[str] = mapped_column(String(100), nullable=False)
    defect_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cause_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    cause_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))


# 알람 / ACK 이력 / 재검 큐 / 이벤트
class AlarmTable(Base):
    __tablename__ = "alarms"
    __table_args__ = (
        CheckConstraint("severity IN ('critical', 'warning', 'info', 'ok')", name="ck_alarms_severity"),
        CheckConstraint("status IN ('active', 'cleared', 'hold')", name="ck_alarms_status"),
        Index("idx_alarms_line_time", "line_id", "occurred_at"),
        Index("idx_alarms_equip_time", "equip_id", "occurred_at"),
        Index("idx_alarms_status", "status"),
        Index("idx_alarms_severity", "severity"),
    )

    alarm_id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.line_id"), nullable=False)
    equip_id: Mapped[int | None] = mapped_column(ForeignKey("equipments.equip_id"), nullable=True)
    alarm_code: Mapped[str] = mapped_column(String(60), nullable=False)
    alarm_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cause_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))


class AlarmAckHistoryTable(Base):
    __tablename__ = "alarm_ack_history"
    __table_args__ = (
        CheckConstraint("ack_status IN ('unack', 'hold', 'ack')", name="ck_alarm_ack_history_ack_status"),
        Index("idx_alarm_ack_history_alarm_id", "alarm_id_ref", "handled_at"),
        Index("idx_alarm_ack_history_status", "ack_status"),
    )

    ack_id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    alarm_id_ref: Mapped[int] = mapped_column(ForeignKey("alarms.alarm_id"), nullable=False)
    ack_status: Mapped[str] = mapped_column(String(20), nullable=False)
    handled_by: Mapped[int | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    handled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)


class RecheckQueueTable(Base):
    __tablename__ = "recheck_queue"
    __table_args__ = (
        CheckConstraint("priority IN ('LOW', 'MEDIUM', 'HIGH')", name="ck_recheck_queue_priority"),
        CheckConstraint("severity IN ('critical', 'warning', 'info')", name="ck_recheck_queue_severity"),
        CheckConstraint("status IN ('queued', 'in_progress', 'done', 'hold')", name="ck_recheck_queue_status"),
        Index("idx_recheck_queue_line_status", "line_id", "status", "queued_at"),
        Index("idx_recheck_queue_lot_id", "lot_id"),
        Index("idx_recheck_queue_priority", "priority"),
    )

    recheck_id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    lot_id: Mapped[str] = mapped_column(String(60), nullable=False)
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.line_id"), nullable=False)
    equip_id: Mapped[int | None] = mapped_column(ForeignKey("equipments.equip_id"), nullable=True)
    defect_code: Mapped[str] = mapped_column(String(60), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'queued'"))
    count_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    cause_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))


class EventLogTable(Base):
    __tablename__ = "event_logs"
    __table_args__ = (
        Index("idx_event_logs_time", "recorded_at"),
        Index("idx_event_logs_line_time", "line_id", "recorded_at"),
        Index("idx_event_logs_severity", "severity"),
    )

    event_id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    line_id: Mapped[int | None] = mapped_column(ForeignKey("lines.line_id"), nullable=True)
    equip_id: Mapped[int | None] = mapped_column(ForeignKey("equipments.equip_id"), nullable=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[str] = mapped_column(String(255), nullable=False)
    meta_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))


# 라인 환경 센서 로그
class LineEnvironmentTable(Base):
    __tablename__ = "line_environment"
    __table_args__ = (
        Index("idx_line_environment_line_time", "line_id", "recorded_at"),
        Index("idx_line_environment_metric", "metric_name", "recorded_at"),
    )

    env_id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.line_id"), nullable=False)
    sensor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(50), nullable=False)
    metric_value: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
