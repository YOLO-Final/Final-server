"""인증 토큰 생성/검증 유틸.

access/refresh JWT를 만들고, 보호된 API에서 현재 로그인 사용자를
복원할 때 공통으로 사용하는 모듈이다.
"""

import os
from datetime import datetime, timedelta
from jose import jwt,JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from src.lib.database import get_db
from src.lib.env_loader import load_project_dotenv

load_project_dotenv()

# 토큰 서명에 사용하는 핵심 설정값
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is not set.")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 20
REFRESH_TOKEN_EXPIRE_HOURS = 12

# access 토큰: 짧은 수명으로 API 호출에 사용한다.
def create_access_token(employee_no: str, token_version: int) -> str:
    payload = {
        "sub": employee_no,
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
        "ver": token_version,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

# refresh 토큰: access 토큰 재발급에 사용한다.
def create_refresh_token(employee_no: str, token_version: int) -> str:
    payload = {
        "sub": employee_no,
        "exp": datetime.utcnow() + timedelta(hours=REFRESH_TOKEN_EXPIRE_HOURS),
        "type": "refresh",
        "ver": token_version,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    # 서명/만료 검증까지 포함한 공통 JWT 디코드 유틸
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# 보호된 API에서 현재 로그인 사용자와 계정 상태를 함께 검증한다.
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    from src.modules.db.users.db.model import UserTable

    # 인증 실패 시 FastAPI 표준 Bearer 응답 형식을 유지한다.
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # JWT 서명/만료를 먼저 검증한다.
        payload = decode_token(token)
    except JWTError:
        raise credentials_exception

    # access 토큰인지 확인
    if payload.get("type") != "access":
        raise credentials_exception

    employee_no = payload.get("sub")
    token_ver = payload.get("ver")

    if not employee_no or token_ver is None:
        raise credentials_exception

    # 토큰 안의 사용자와 현재 DB 상태를 다시 대조한다.
    user_row = db.query(UserTable).filter(UserTable.employee_no == employee_no).one_or_none()

    if not user_row:
        raise credentials_exception

    # 계정이 비활성화되었거나 잠겨 있으면 보호된 API 접근을 막는다.
    if not user_row.id_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )

    if user_row.id_locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is locked. Please contact hr_admin.",
        )

    # 핵심: token_version이 다르면 예전에 발급된 토큰으로 보고 즉시 차단한다.
    # 비밀번호 변경/로그아웃/비활성화 같은 이벤트가 여기에 반영된다.
    if token_ver != user_row.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been invalidated. Please log in again.",
        )

    return user_row
