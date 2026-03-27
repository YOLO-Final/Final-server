"""인증/로그인 관련 HTTP 엔드포인트 모음.

비밀번호 로그인, Face ID 로그인, 토큰 재발급, 사용자 관리,
라인 배정, 로그아웃까지 인증 흐름의 진입점을 한 곳에 모아둔다.
"""

from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session

from src.lib.database import get_db
from src.modules.auth.db.schema import (
    AuthUserProfileResponse,
    FaceLoginRequest,
    FaceLoginResponse,
    FaceRegisterRequest,
    FaceRegisterResponse,
    FaceRegistrationStatusResponse,
    LoginRequest,
    LoginResponse,
    RefreshTokenResponse,
    CreateUserRequest,
    CreateUserResponse,
    DeactivateUserResponse,
    UnlockUserResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,  
    DeleteFaceEmbeddingResponse,
    UpdateLineIdRequest,
    UpdateLineIdResponse,
    LogoutResponse,
    WebLoginProfileResponse,
)
from src.modules.auth.service import (
    face_login_with_matching,
    get_auth_user_profile,
    get_web_login_profile,
    list_face_registration_status,
    login_with_password,
    refresh_access_token,
    register_face_embedding,
    deactivate_user,
    unlock_user,
    create_user,
    change_password,
    delete_face_embedding,
    update_line_id, 
    logout_user,
)

from src.modules.auth.jwt import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


# 기본 로그인 / 토큰 재발급
@router.post("/login", response_model=LoginResponse)          # ← 추가
def login(request: LoginRequest, db: Session = Depends(get_db)):
    # 사원번호/비밀번호 기반 로그인.
    # 성공 시 access/refresh 토큰을 함께 반환한다.
    return login_with_password(db=db, employee_no=request.employee_no, password=request.password)


@router.post("/login/face", response_model=FaceLoginResponse) # ← 추가
def face_login(request: FaceLoginRequest, db: Session = Depends(get_db)):
    # Face ID 로그인.
    # employee_no가 있으면 1:1 비교, 없으면 등록된 얼굴 전체에서 1:N 비교를 수행한다.
    return face_login_with_matching(db=db, request=request)


# Face ID 등록/조회 관리
@router.get("/face/registrations", response_model=FaceRegistrationStatusResponse)
def face_registrations(
    keyword: str | None = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    # 얼굴 등록 여부 목록을 조회한다.
    # 관리자 화면에서 Face ID 등록 상태를 한 번에 볼 때 사용한다.
    return list_face_registration_status(db=db, keyword=keyword)


@router.post("/face/register", response_model=FaceRegisterResponse)
def face_register(
    request: FaceRegisterRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    # 특정 사원의 얼굴 임베딩을 신규 등록하거나 덮어쓴다.
    return register_face_embedding(db=db, request=request)


@router.delete("/face/{employee_no}", response_model=DeleteFaceEmbeddingResponse)
def delete_face(
    employee_no: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    # 특정 사원의 등록된 Face ID 정보를 제거한다.
    return delete_face_embedding(db=db, employee_no=employee_no, current_user=current_user)


# 로그인 후 프로필/권한 조회
@router.get("/users/{employee_no}", response_model=AuthUserProfileResponse)
def auth_user_profile(
    employee_no: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    # on-device/auth 관리 화면에서 쓰는 기본 프로필 조회.
    return get_auth_user_profile(db=db, employee_no=employee_no)


@router.get("/web-login-profile/{employee_no}", response_model=WebLoginProfileResponse)
def web_login_profile(
    employee_no: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    # web_login 성공 직후 web_dashboard 진입 권한을 판별할 때 쓰는 프로필 조회.
    return get_web_login_profile(db=db, employee_no=employee_no)


@router.post("/refresh", response_model=RefreshTokenResponse) # ← 추가
def refresh_token(
    refresh_token: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    # refresh 토큰으로 access 토큰만 재발급한다.
    return refresh_access_token(db=db, refresh_token=refresh_token)


# 관리자용 계정 제어
@router.patch("/users/{employee_no}/deactivate", response_model=DeactivateUserResponse)  # ← 추가
def deactivate(
    employee_no: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    # 계정을 비활성화하고 기존 토큰도 함께 무효화한다.
    return deactivate_user(db=db, employee_no=employee_no, current_user=current_user)


@router.patch("/users/{employee_no}/unlock", response_model=UnlockUserResponse)          # ← 추가
def unlock(
    employee_no: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    # 잠긴 계정의 로그인 실패 횟수/잠금 상태를 초기화한다.
    return unlock_user(db=db, employee_no=employee_no, current_user=current_user)


@router.post("/users", response_model=CreateUserResponse)
def create_new_user(
    request: CreateUserRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    # 관리자 전용 신규 계정 생성.
    # worker 계정은 필요 시 line_id도 함께 받는다.
    return create_user(db=db, request=request, current_user=current_user)


@router.patch("/users/{employee_no}/password", response_model=ChangePasswordResponse)
def update_password(
    employee_no: str,
    request: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    # 본인 비밀번호 변경.
    # 변경 즉시 기존 토큰을 무효화해서 재로그인을 강제한다.
    return change_password(db=db, employee_no=employee_no, request=request, current_user=current_user)


# worker 계정 라인 배정
@router.patch("/users/{employee_no}/line", response_model=UpdateLineIdResponse)
def update_line(
    employee_no: str,
    request: UpdateLineIdRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    # worker 계정에 라인을 배정하거나 변경한다.
    return update_line_id(db=db, employee_no=employee_no, request=request, current_user=current_user)


# 현재 세션 무효화
@router.post("/logout", response_model=LogoutResponse)
def logout(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    # 현재 로그인 세션을 강제로 종료한다.
    # 서버에서는 token_version을 올려 기존 토큰을 모두 무효화한다.
    return logout_user(db=db, current_user=current_user)
