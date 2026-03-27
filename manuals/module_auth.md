# AUTH 모듈 운영 가이드

## 1. 한 줄 설명

사용자 로그인, 토큰 갱신, 얼굴 등록/로그인, 사용자 계정 관리 기능을 담당합니다.

## 2. API 기본 경로

- `/api/v1/auth`

## 3. 주요 기능

- 비밀번호 로그인
- 얼굴 로그인
- 액세스 토큰 재발급
- 얼굴 등록/삭제
- 사용자 계정 생성/잠금해제/비활성화
- 라인 정보 변경
- 로그아웃

## 4. 주요 엔드포인트

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/login/face`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/face/register`
- `GET /api/v1/auth/face/registrations`
- `DELETE /api/v1/auth/face/{employee_no}`
- `POST /api/v1/auth/users`
- `PATCH /api/v1/auth/users/{employee_no}/deactivate`
- `PATCH /api/v1/auth/users/{employee_no}/unlock`
- `PATCH /api/v1/auth/users/{employee_no}/password`
- `PATCH /api/v1/auth/users/{employee_no}/line`
- `POST /api/v1/auth/logout`

## 5. 필수 환경변수

- `SECRET_KEY` (필수)
- `FACE_MATCH_THRESHOLD` (선택, 기본 0.30)

## 6. 운영 점검 포인트

1. 로그인 실패 시 먼저 `SECRET_KEY` 누락 여부 확인
2. 얼굴 로그인 인식률 이슈 시 `FACE_MATCH_THRESHOLD` 조정 검토
3. 토큰 문제 발생 시 재로그인 후 동작 확인

## 7. 자주 발생하는 문제

- 증상: 로그인은 됐는데 API 호출이 401
- 원인: 만료/무효 토큰 또는 토큰 버전 불일치
- 조치: 로그아웃 후 재로그인, 계정 잠금 상태 확인
