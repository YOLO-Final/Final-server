"""인증 API 입출력 스키마 모음.

로그인, Face ID, 토큰 재발급, 사용자 생성/잠금 해제, 라인 배정,
로그아웃 응답까지 인증 라우터가 사용하는 요청/응답 모델을 정의한다.
"""

from pydantic import BaseModel, field_validator
from datetime import datetime


# 기본 로그인 / 토큰 응답
class LoginRequest(BaseModel):
    # 사원번호/비밀번호 로그인 요청 본문
    employee_no: str
    password: str


class LoginResponse(BaseModel):
    # 로그인 성공 시 web/on-device 공통으로 쓰는 기본 인증 응답
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    employee_no: str
    name: str | None = None
    role: str | None = None


class FaceLoginRequest(BaseModel):
    # employee_no는 선택 입력이다.
    # 값이 있으면 지정 사원 기준 비교, 없으면 전체 등록 얼굴 대상 비교를 수행한다.
    employee_no: str | None = None
    image_base64: str


class FaceLoginResponse(BaseModel):
    # 얼굴 인증 결과와, 성공 시 발급된 토큰/사용자 정보를 함께 담는다.
    verified: bool
    message: str
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str | None = None
    employee_no: str | None = None
    name: str | None = None
    role: str | None = None


class RefreshTokenResponse(BaseModel):
    # refresh 이후에는 access 토큰만 다시 내려준다.
    access_token: str
    token_type: str = "bearer"


# Face ID 등록 현황 / 등록
class FaceRegistrationStatusItem(BaseModel):
    # Face ID 등록 현황 목록의 한 행
    employee_no: str
    name: str | None = None
    registration_status: str


class FaceRegistrationStatusResponse(BaseModel):
    # 관리자 화면에서 등록/미등록 현황을 요약할 때 사용한다.
    items: list[FaceRegistrationStatusItem]
    total: int
    registered_count: int
    unregistered_count: int


class FaceRegisterRequest(BaseModel):
    # 얼굴 등록은 사원번호와 base64 이미지 한 장을 입력으로 받는다.
    employee_no: str
    image_base64: str


class FaceRegisterResponse(BaseModel):
    # 등록 완료 후 화면에 바로 표시할 최소 결과
    employee_no: str
    registration_status: str
    message: str


class AuthUserProfileResponse(BaseModel):
    # on-device/auth 관리 화면용 기본 프로필
    employee_no: str
    name: str | None = None


class WebLoginProfileResponse(BaseModel):
    # web_login 성공 후 web_dashboard 탭 권한을 정할 때 사용하는 응답
    employee_no: str
    name: str | None = None
    role: str


# 관리자 계정 관리
class CreateUserRequest(BaseModel):
    # 관리자 신규 계정 생성 요청.
    # worker는 line_id가 사실상 필요하지만, 실제 필수 여부는 서비스 레이어에서 검증한다.
    employee_no: str
    name: str
    role: str
    birth_date: str
    line_id: int | None = None  # ← 추가 (worker는 필수지만 서버에서 검증)

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, v: str) -> str:
        # 초기 비밀번호 생성 기준이므로 YYYYMMDD 형식을 강제한다.
        try:
            datetime.strptime(v, "%Y%m%d")
        except ValueError:
            raise ValueError("birth_date must be in YYYYMMDD format. (e.g. 19960417)")
        return v

class CreateUserResponse(BaseModel):
    # 계정 생성 완료 후 목록/알림에 바로 쓸 수 있는 응답
    employee_no: str
    name: str
    role: str
    message: str


class DeactivateUserResponse(BaseModel):
    # 계정 비활성화 응답
    employee_no: str
    message: str


class UnlockUserResponse(BaseModel):
    # 잠금 해제 응답
    employee_no: str
    message: str

class ChangePasswordRequest(BaseModel):
    # 비밀번호 변경 시 현재/새 비밀번호와 확인값을 함께 받는다.
    current_password: str
    new_password: str
    new_password_confirm: str

class ChangePasswordResponse(BaseModel):
    # 비밀번호 변경 완료 응답
    employee_no: str
    message: str

class DeleteFaceEmbeddingResponse(BaseModel):
    # Face ID 삭제 완료 응답
    employee_no: str
    message: str

class UpdateLineIdRequest(BaseModel):
    # worker 계정 라인 배정 요청
    line_id: int

class UpdateLineIdResponse(BaseModel):
    # worker 계정 라인 배정 완료 응답
    employee_no: str
    line_id: int
    message: str

class LogoutResponse(BaseModel):
    # 로그아웃 완료 메시지
    message: str
