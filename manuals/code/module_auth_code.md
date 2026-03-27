# AUTH Module (Code)

## 목적
인증/인가 핵심 모듈. 비밀번호 로그인, 얼굴 로그인, 토큰 갱신, 사용자 관리를 처리합니다.

## 핵심 파일
- `server_api/src/modules/auth/router.py`
- `server_api/src/modules/auth/service.py`
- `server_api/src/modules/auth/jwt.py`
- `server_api/src/modules/auth/db/model.py`
- `server_api/src/modules/auth/db/schema.py`

## 라우트 prefix
- `/api/v1/auth`

## 주요 흐름
1. 로그인 요청 수신 (`/login` 또는 `/login/face`)
2. 서비스 계층에서 사용자/비밀번호 또는 임베딩 매칭 검증
3. JWT 생성 (`access`, `refresh`)
4. 보호 API는 `get_current_user`로 토큰 검증

## 중요 환경변수
- `SECRET_KEY` (필수)
- `FACE_MATCH_THRESHOLD` (기본 0.30)

## 수정 시 주의
- `SECRET_KEY` 누락 시 런타임 예외 발생
- 토큰 payload 키(`sub`, `type`, `ver`) 호환성 유지 필수
- 계정 잠금/비활성 정책은 service + jwt 의존 로직 같이 확인
