"""인증 서비스 핵심 로직.

비밀번호 로그인, Face ID 로그인, 토큰 재발급, 사용자 생성/잠금/비활성화,
라인 배정, 로그아웃까지 인증 도메인의 실제 동작을 담당한다.
"""
 
import hashlib
import hmac
import bcrypt
import os
from jose import JWTError
import json
 
from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from datetime import datetime
 
from src.modules.auth.db.model import FaceEmbeddingTable, VectorTable
 
from src.modules.auth.db.schema import FaceLoginRequest, FaceRegisterRequest, CreateUserRequest, ChangePasswordRequest, UpdateLineIdRequest
 
from src.modules.db.users.db.model import UserTable
from src.modules.auth.vision.service import FaceEngineUnavailableError, extract_face_embedding
 
from src.modules.auth.jwt import create_access_token, create_refresh_token, decode_token
 
from src.modules.auth.logger import auth_logger

# 얼굴 인식 매칭 임계값은 환경 변수로 조정하되, 잘못된 값이 들어와도 안전한 범위로 보정한다.
def _read_face_match_threshold() -> float:
    raw = os.getenv("FACE_MATCH_THRESHOLD", "0.30").strip()
    try:
        value = float(raw)
    except ValueError:
        value = 0.30
    return max(0.0, min(1.0, value))


FACE_MATCH_THRESHOLD = _read_face_match_threshold()


def _get_user_by_employee_no(db: Session, employee_no: str) -> UserTable | None:
    return db.query(UserTable).filter(UserTable.employee_no == employee_no).one_or_none()


def _get_user_or_404(db: Session, employee_no: str) -> UserTable:
    user_row = _get_user_by_employee_no(db, employee_no)
    if not user_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 사원번호입니다.",
        )
    return user_row


def _ensure_user_is_active(user_row: UserTable) -> None:
    if not user_row.id_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다. 관리자에게 문의해주세요.",
        )

    if user_row.id_locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="잠긴 계정입니다. 관리자에게 문의해주세요.",
        )


def _ensure_hr_admin(current_user) -> None:
    if current_user.role != "hr_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 기능은 관리자만 사용할 수 있습니다.",
        )


def _build_token_response(employee_no: str, token_version: int | None) -> dict:
    current_token_version = token_version or 0
    return {
        "access_token": create_access_token(employee_no, current_token_version),
        "refresh_token": create_refresh_token(employee_no, current_token_version),
        "token_type": "bearer",
        "employee_no": employee_no,
    }


def _extract_face_embedding_or_raise(image_base64: str, *, failure_message: str) -> list[float]:
    try:
        return extract_face_embedding(image_base64)
    except FaceEngineUnavailableError as exc:
        auth_logger.error("Face recognition engine is unavailable.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="얼굴 인식 서비스에 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
        ) from exc
    except ValueError as exc:
        auth_logger.error(f"Face embedding ValueError: {exc}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=failure_message,
        ) from exc
    except Exception as exc:  # noqa: BLE001
        auth_logger.error(f"Face recognition request failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="얼굴 인식 요청에 실패했습니다. 다시 시도해주세요.",
        ) from exc

# 비밀번호 해시/검증 유틸
def _hash_password(plain_password: str) -> str:
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")
 
def _legacy_sha256(plain_password: str) -> str:
    return hashlib.sha256(plain_password.encode("utf-8")).hexdigest()

def _is_legacy_sha256_hash(password_hash: str) -> bool:
    return len(password_hash) == 64 and all(ch in "0123456789abcdef" for ch in password_hash.lower())

def _verify_password(plain_password: str, hashed_password: str) -> bool:
    if _is_legacy_sha256_hash(hashed_password):
        return hmac.compare_digest(_legacy_sha256(plain_password), hashed_password.lower())

    if hashed_password.startswith("$2"):
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8"),
            )
        except ValueError:
            return False

    return False
# 비밀번호 로그인
def login_with_password(db: Session, employee_no: str, password: str) -> dict:
    user_row = db.query(UserTable).filter(UserTable.employee_no == employee_no).one_or_none()
 
    if not user_row:
        auth_logger.error(f"로그인 실패: 사용자 없음 (employee_no={employee_no})")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 틀렸습니다.",
        )
 
    # 퇴사자 체크 — 비밀번호 검증 전에 먼저
    if not user_row.id_active:
        auth_logger.error(f"로그인 차단: 비활성화 계정 (employee_no={employee_no})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다. 관리자에게 문의해주세요.",
        )
 
    # 잠금 체크 — 비밀번호 검증 전에 먼저
    if user_row.id_locked:
        auth_logger.error(f"로그인 차단: 잠긴 계정 (employee_no={employee_no})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="잠긴 계정입니다. 관리자에게 문의해주세요.",
        )
 
    # 현재 저장된 해시가 bcrypt인지, 예전 SHA-256인지와 무관하게
    # 공통 검증 함수에서 처리한다.
    stored_password = str(user_row.password_hash or "")

    if not _verify_password(password, stored_password):
        # 실패 횟수 +1
        user_row.login_fail_count = (user_row.login_fail_count or 0) + 1
 
        # 5회 이상 실패 시 계정 잠금 + 토큰 즉시 무효화
        if user_row.login_fail_count >= 5:
            user_row.id_locked = True
            user_row.token_version = (user_row.token_version or 0) + 1
 
        db.commit()
        auth_logger.error(
            f"로그인 실패: 비밀번호 불일치 "
            f"(employee_no={employee_no}, fail_count={user_row.login_fail_count}, locked={user_row.id_locked})"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 틀렸습니다.",
        )

    # 예전 SHA-256 해시는 다음 성공 로그인 시 bcrypt로 자동 승격한다.
    if _is_legacy_sha256_hash(stored_password):
        user_row.password_hash = _hash_password(password)
 
    # 로그인 성공 시 실패 횟수와 마지막 로그인 시각을 정리한다.
    user_row.login_fail_count = 0
    user_row.last_login = datetime.utcnow()
    db.commit()
    auth_logger.info(f"{user_row.name}님 로그인 하셨습니다.")  # ← 로그인 성공
 
    return _build_token_response(employee_no, user_row.token_version)
# 얼굴 임베딩 비교
def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    dot = 0.0
    norm1 = 0.0
    norm2 = 0.0
 
    for a, b in zip(vec1, vec2):
        dot += a * b
        norm1 += a * a
        norm2 += b * b
 
    if norm1 <= 0.0 or norm2 <= 0.0:
        return -1.0
 
    return dot / ((norm1 ** 0.5) * (norm2 ** 0.5))
# Face ID 로그인
def face_login_with_matching(db: Session, request: FaceLoginRequest) -> dict:
    probe_embedding = _extract_face_embedding_or_raise(
        request.image_base64,
        failure_message="얼굴 이미지를 처리할 수 없습니다. 다시 촬영해주세요.",
    )
 
    target_employee_no = (request.employee_no or "").strip()
 
    if target_employee_no:
        # 사원번호가 있으면 해당 사용자 얼굴과만 1:1 비교한다.
        # employee_no 제공 시 → 1:1 비교
        target = (
            db.query(FaceEmbeddingTable)
            .filter(FaceEmbeddingTable.employee_no == target_employee_no)
            .one_or_none()
        )
 
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,  # ← 503 → 404
                detail="등록된 얼굴 정보가 없습니다. 먼저 얼굴을 등록해주세요.",
            )
 
        stored_embedding = json.loads(target.embedding_json)
        score = _cosine_similarity(probe_embedding, stored_embedding)
 
        if score < FACE_MATCH_THRESHOLD:
            auth_logger.error("얼굴 인식에 실패하였습니다.")  # ← 1:1 얼굴 불일치
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,  # ← 503 → 401
                detail="얼굴 인식에 실패했습니다. 다시 시도해주세요.",
            )
 
        matched_employee_no = target_employee_no
    else:
        # 사원번호가 없으면 등록된 얼굴 전체를 대상으로 1:N 비교한다.
        # employee_no 미제공 시 → 전체 DB 대상 1:N 비교
        candidates = db.query(FaceEmbeddingTable).all()
 
        if not candidates:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,  # ← 503 → 404
                detail="등록된 얼굴 정보가 없습니다. 먼저 얼굴을 등록해주세요.",
            )
 
        best_employee_no = None
        best_score = -1.0
 
        for candidate in candidates:
            stored_embedding = json.loads(candidate.embedding_json)
            score = _cosine_similarity(probe_embedding, stored_embedding)
            if score > best_score:
                best_score = score
                best_employee_no = candidate.employee_no
 
        if not best_employee_no or best_score < FACE_MATCH_THRESHOLD:
            auth_logger.error("얼굴 인식에 실패하였습니다.")  # ← 1:N 얼굴 불일치
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,  # ← 503 → 401
                detail="얼굴을 인식할 수 없습니다. 먼저 얼굴을 등록해주세요.",
            )
 
        matched_employee_no = best_employee_no
 
    user_row = _get_user_or_404(db, matched_employee_no)
    _ensure_user_is_active(user_row)
 
    user_row.last_login = datetime.utcnow()
    db.commit()
    auth_logger.info(f"{user_row.name}님 로그인 하셨습니다.")  # ← 얼굴 로그인 성공
 
    token_payload = _build_token_response(matched_employee_no, user_row.token_version)
    return {
        "verified": True,
        "message": "얼굴 인증에 성공했습니다.",
        **token_payload,
    }
# Face ID 등록 현황 / 등록 / 프로필 조회
def list_face_registration_status(db: Session, keyword: str | None = None, limit: int = 100) -> dict:
    normalized_keyword = (keyword or "").strip()

    # 사용자 정보와 vector 등록 여부를 함께 묶어서 관리 화면 목록을 만든다.
    query = (
        db.query(UserTable, VectorTable)
        .outerjoin(VectorTable, VectorTable.employee_no == UserTable.employee_no)
        .order_by(UserTable.employee_no.asc())
    )
 
    if normalized_keyword:
        pattern = f"%{normalized_keyword}%"
        query = query.filter(
            or_(
                UserTable.employee_no.ilike(pattern),
                UserTable.name.ilike(pattern),
            )
        )
 
    rows = query.limit(limit).all()
 
    items: list[dict] = []
    registered_count = 0
 
    for user_row, vector_row in rows:
        vector_text = str(vector_row.face_embedding).strip() if vector_row and vector_row.face_embedding else ""
        is_registered = bool(vector_text)
        if is_registered:
            registered_count += 1
 
        items.append(
            {
                "employee_no": user_row.employee_no,
                "name": user_row.name,
                "registration_status": "등록" if is_registered else "미등록",
            }
        )
 
    total = len(items)
    return {
        "items": items,
        "total": total,
        "registered_count": registered_count,
        "unregistered_count": total - registered_count,
    }
 
 
def register_face_embedding(db: Session, request: FaceRegisterRequest) -> dict:
    employee_no = request.employee_no.strip()
    if not employee_no:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="사원번호를 입력해주세요.",
        )
 
    # 사용자 존재 여부 확인
    user_exists = db.query(UserTable).filter(UserTable.employee_no == employee_no).one_or_none()
 
    if not user_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 사원번호입니다.",
        )
 
    try:
        embedding = extract_face_embedding(request.image_base64)
    except FaceEngineUnavailableError as exc:
        auth_logger.error("Face recognition engine is unavailable.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="얼굴 인식 서비스에 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
        ) from exc
    except ValueError as exc:
        auth_logger.error(f"Face embedding ValueError: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="얼굴 이미지를 처리할 수 없습니다. 다시 촬영해주세요.",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        auth_logger.error(f"Face embedding extraction failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="얼굴 정보 저장에 실패했습니다. 다시 시도해주세요.",
        ) from exc
 
    # 동일 임베딩을 두 저장소에 각각 맞는 형태로 저장한다.
    # - vector_table: 등록 상태/간단 조회용
    # - face_embedding_table: 실제 얼굴 매칭용
    vector_literal = " ".join(f"{value:.8f}" for value in embedding)
 
    # vector_table upsert — 등록 상태 조회용
    vector_row = db.query(VectorTable).filter(VectorTable.employee_no == employee_no).one_or_none()
 
    if vector_row:
        vector_row.face_embedding = func.to_tsvector("simple", vector_literal)
    else:
        vector_row = VectorTable(
            employee_no=employee_no,
            face_embedding=func.to_tsvector("simple", vector_literal),
        )
        db.add(vector_row)
 
    # face_embedding_table upsert — 실제 얼굴 매칭용
    embedding_row = db.query(FaceEmbeddingTable).filter(FaceEmbeddingTable.employee_no == employee_no).one_or_none()
    embedding_json = json.dumps([float(value) for value in embedding])
 
    if embedding_row:
        embedding_row.embedding_json = embedding_json
    else:
        db.add(
            FaceEmbeddingTable(
                employee_no=employee_no,
                embedding_json=embedding_json,
            )
        )
 
    db.commit()
    auth_logger.info(f"Face ID를 등록했습니다. (employee_no={employee_no})")  # ← 얼굴 등록 성공
 
    return {
        "employee_no": employee_no,
        "registration_status": "등록",
        "message": "얼굴 정보가 성공적으로 등록되었습니다.",
    }


# 로그인 이후 화면 진입에 필요한 최소 프로필 조회
def get_auth_user_profile(db: Session, employee_no: str) -> dict:
    user_row = _get_user_or_404(db, employee_no)
 
    return {
        "employee_no": user_row.employee_no,
        "name": user_row.name,
    }


# web_login 전용 프로필/권한 조회
def get_web_login_profile(db: Session, employee_no: str) -> dict:
    user_row = _get_user_or_404(db, employee_no)

    return {
        "employee_no": user_row.employee_no,
        "name": user_row.name,
        "role": user_row.role,
    }
 
 
# refresh 토큰 기반 access 토큰 재발급
def refresh_access_token(db: Session, refresh_token: str) -> dict:
    try:
        payload = decode_token(refresh_token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 만료되었습니다. 다시 로그인해주세요.",
        )
 
    # refresh 토큰인지 확인
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 인증 정보입니다. 다시 로그인해주세요.",
        )
 
    employee_no = payload.get("sub")
    token_ver = payload.get("ver")  # ← token_version 꺼내기
 
    if not employee_no or token_ver is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 인증 정보입니다. 다시 로그인해주세요.",
        )
 
    # refresh 토큰만 믿지 않고 DB에서 현재 계정 상태를 다시 확인한다.
    user_row = _get_user_by_employee_no(db, employee_no)

    if not user_row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="존재하지 않는 사원번호입니다.",
        )

    _ensure_user_is_active(user_row)
 
    # token_version 불일치 시 즉시 차단
    if token_ver != user_row.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 만료되었습니다. 다시 로그인해주세요.",
        )
 
    # 새 Access Token 발급
    return {
        "access_token": create_access_token(employee_no, user_row.token_version),
        "token_type": "bearer",
    }
 
 
# 관리자 전용 계정 제어
def deactivate_user(db: Session, employee_no: str, current_user) -> dict:
    # hr_admin 권한 체크
    _ensure_hr_admin(current_user)
 
    user_row = _get_user_or_404(db, employee_no)
 
    # 퇴사 처리 + 토큰 즉시 무효화
    user_row.id_active = False
    user_row.token_version = (user_row.token_version or 0) + 1
    db.commit()
 
    return {
        "employee_no": employee_no,
        "message": "계정이 비활성화되었습니다.",
    }
 
 
def unlock_user(db: Session, employee_no: str, current_user) -> dict:
    # hr_admin 권한 체크
    _ensure_hr_admin(current_user)
 
    user_row = _get_user_or_404(db, employee_no)
 
    # 잠금 해제 (token_version 변경 안 함 — 설계서 옵션 A)
    user_row.id_locked = False
    user_row.login_fail_count = 0
    db.commit()
 
    return {
        "employee_no": employee_no,
        "message": "계정 잠금이 해제되었습니다.",
    }
 
 
# 계정 생성 / 비밀번호 변경
def create_user(db: Session, request: CreateUserRequest, current_user) -> dict:
    # hr_admin 권한 체크
    _ensure_hr_admin(current_user)
 
    # 사원번호 중복 체크
    existing = db.query(UserTable).filter(UserTable.employee_no == request.employee_no).one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 등록된 사원번호입니다.",
        )
 
    # role 유효성 체크
    valid_roles = {"hr_admin", "manager", "quality_manager", "worker"}
    if request.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 역할입니다. 관리자에게 문의해주세요.",
        )
 
    # 초기 비밀번호는 생년월일(YYYYMMDD)을 bcrypt로 해시해서 저장한다.
    db.add(
        UserTable(
            employee_no=request.employee_no,
            name=request.name,
            password_hash=_hash_password(request.birth_date),
            role=request.role,
            line_id=request.line_id,
            id_active=True,
            id_locked=False,
            login_fail_count=0,
            token_version=0,
        )
    )
    db.commit()
 
    return {
        "employee_no": request.employee_no,
        "name": request.name,
        "role": request.role,
        "message": "사용자가 성공적으로 등록되었습니다.",
    }
 
 
def change_password(db: Session, employee_no: str, request: ChangePasswordRequest, current_user) -> dict:
    # 본인만 변경 가능
    if current_user.employee_no != employee_no:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 비밀번호만 변경할 수 있습니다.",
        )
 
    # 새 비밀번호 일치 확인
    if request.new_password != request.new_password_confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="새 비밀번호가 일치하지 않습니다.",
        )
 
    user_row = _get_user_or_404(db, employee_no)
 
    # 현재 비밀번호 검증
    if not _verify_password(request.current_password, str(user_row.password_hash or "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="현재 비밀번호가 틀렸습니다.",
        )
 
    # 새 비밀번호 저장 + token_version +1 (기존 토큰 즉시 무효화)
    user_row.password_hash = _hash_password(request.new_password)
    user_row.token_version = (user_row.token_version or 0) + 1
    db.commit()
 
    return {
        "employee_no": employee_no,
        "message": "비밀번호가 변경되었습니다. 다시 로그인해주세요.",
    }
 
 
# Face ID 삭제 / worker 라인 배정 / 로그아웃
def delete_face_embedding(db: Session, employee_no: str, current_user) -> dict:
    # hr_admin 권한 체크
    _ensure_hr_admin(current_user)
 
    # 사용자 존재 여부 확인
    _get_user_or_404(db, employee_no)
 
    # FaceEmbeddingTable 삭제
    embedding_row = db.query(FaceEmbeddingTable).filter(FaceEmbeddingTable.employee_no == employee_no).one_or_none()
    if embedding_row:
        db.delete(embedding_row)
 
    # VectorTable 삭제
    vector_row = db.query(VectorTable).filter(VectorTable.employee_no == employee_no).one_or_none()
    if vector_row:
        db.delete(vector_row)
 
    db.commit()
    auth_logger.error(f"Face ID를 삭제했습니다. (employee_no={employee_no})")  # ← 얼굴 삭제 (빨간색)
 
    return {
        "employee_no": employee_no,
        "message": "얼굴 정보가 삭제되었습니다.",
    }
 
 
def update_line_id(db: Session, employee_no: str, request: UpdateLineIdRequest, current_user) -> dict:
    # hr_admin 권한 체크
    _ensure_hr_admin(current_user)
 
    # 사용자 존재 여부 확인
    user_row = _get_user_or_404(db, employee_no)
 
    # worker만 line_id 배정 대상
    if user_row.role != "worker":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="라인 배정은 작업자(worker) 계정에만 가능합니다.",
        )
 
    # 실제 worker 대시보드 라인 강제 필터가 이 line_id를 기준으로 동작한다.
    user_row.line_id = request.line_id
    db.commit()
 
    return {
        "employee_no": employee_no,
        "line_id": request.line_id,
        "message": "라인 배정이 변경되었습니다.",
    }


def logout_user(db: Session, current_user) -> dict:
    # token_version을 올려 현재 access/refresh 토큰을 모두 무효화한다.
    current_user.token_version = (current_user.token_version or 0) + 1
    db.commit()
    auth_logger.info(f"{current_user.name}님 로그아웃 하셨습니다.")
    return {"message": "로그아웃되었습니다."}
