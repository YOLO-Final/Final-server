"""개발/테스트용 기본 계정 시드.

운영 환경에서는 실행하지 않고, 로컬 개발 환경에서 admin 계정을
빠르게 준비할 때만 사용한다.
"""

import os
import bcrypt
from sqlalchemy.orm import Session

from src.lib.env_loader import load_project_dotenv
from src.modules.db.users.db.model import UserTable

load_project_dotenv()

# 시드 비밀번호도 실제 로그인과 동일하게 bcrypt로 저장한다.
def _hash_password(plain_password: str) -> str:
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def seed_test_admin_user(db: Session) -> None:
    # 운영 환경에서는 실행하지 않음
    if os.getenv("APP_ENV") == "production":
        return

    # 이미 admin 계정이 있으면 중복 생성하지 않는다.
    existing_user = (
        db.query(UserTable)
        .filter(UserTable.employee_no == "admin")
        .first()
    )
    if existing_user:
        return

    db.add(
        UserTable(
            employee_no="admin",
            password_hash=_hash_password("admin123"),
            role="hr_admin",
            id_active=True,
            id_locked=False,
            login_fail_count=0,
            token_version=0,
        )
    )
    db.commit()
    
