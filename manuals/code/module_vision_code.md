# VISION Module (Code)

## 목적
카메라/온프레미스 연동, 프레임 수집, 오버레이 집계 API를 제공합니다.

## 핵심 파일
- `server_api/src/modules/vision/router.py`
- `server_api/src/modules/vision/service.py`
- `server_api/src/modules/vision/db/*`

## 라우트 prefix
- `/api/v1/vision`

## 주요 흐름
1. 카메라 토큰 검증 (`_verify_camera_token`)
2. 장치 정보 등록 / 핸드셰이크 등록
3. 프레임 업로드 수신 후 서비스 계층 처리
4. 상태/집계/스트림 관련 API 응답

## 중요 환경변수
- `VISION_ALLOW_NO_TOKEN`
- `VISION_CAMERA_TOKEN`
- `VISION_API_TOKEN`
- `VISION_MAX_FRAME_BYTES`

## 수정 시 주의
- 토큰 정책 변경 시 온프렘 장비와 동시에 맞춰야 함
- 업로드 허용 포맷/용량 제한 변경 시 클라이언트도 동기화 필요
