from fastapi import HTTPException, status


def require_role_placeholder(role: str) -> None:
    # TODO: auth 모듈의 실제 JWT/RBAC 구현이 들어오면 교체합니다.
    if not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role is required",
        )
