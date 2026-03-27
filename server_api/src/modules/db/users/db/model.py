"""사용자 계정 ORM 모델.

인증, 로그인, worker 라인 배정에서 공통으로 참조하는 핵심 사용자 테이블이다.
"""

from datetime import datetime

from sqlalchemy import BIGINT, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.lib.database import Base


class UserTable(Base):
    __tablename__ = "user_table"

    # 로그인/권한 판별에 필요한 기본 사용자 정보
    employee_no: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="admin")
    # public.user_table.line_id 기존 컬럼 매핑.
    # ORM FK로 묶지 않고 nullable BIGINT로 유지해서
    # auth 모델이 다른 lines 테이블 경로에 엮이지 않도록 한다.
    line_id: Mapped[int | None] = mapped_column(BIGINT, nullable=True)

    # 계정 활성화/잠금/토큰 무효화 상태
    id_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    id_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    login_fail_count: Mapped[int] = mapped_column(BIGINT, nullable=False, default=0)
    token_version: Mapped[int] = mapped_column(BIGINT, nullable=False, default=0)

    # 감사용 시각 정보
    join_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
