# VISION 모듈 운영 가이드

## 1. 한 줄 설명

카메라 상태, 프레임 업로드, 오버레이 집계, 온프렘 연동 핸드셰이크를 담당합니다.

## 2. API 기본 경로

- `/api/v1/vision`

## 3. 주요 기능

- 카메라 목록/상태 조회
- 카메라 장치 정보 등록
- 카메라 프레임 수신
- 오버레이 일간 건수 집계
- 연동용 heartbeat/handshake

## 4. 주요 엔드포인트

- `GET /api/v1/vision/status`
- `GET /api/v1/vision/cameras`
- `GET /api/v1/vision/overlay-counts/today`
- `POST /api/v1/vision/cameras/{camera_id}/device`
- `POST /api/v1/vision/cameras/{camera_id}/frames`
- `POST /api/v1/vision/interop/handshake`
- `GET /api/v1/vision/interop/handshake/{camera_id}`
- `GET|POST /api/v1/vision/stream/heartbeat`
- `POST /api/v1/vision/inspect` (호환용)

## 5. 관련 환경변수

- `VISION_ALLOW_NO_TOKEN`
- `VISION_CAMERA_TOKEN`
- `VISION_API_TOKEN`
- `VISION_MAX_FRAME_BYTES`

## 6. 운영 점검 포인트

1. 401 오류면 카메라 토큰 값 불일치 여부 확인
2. 413 오류면 프레임 크기가 허용치 초과
3. 핸드셰이크 누락 시 장비 등록 흐름부터 재확인

## 7. 자주 발생하는 문제

- 증상: 카메라 화면이 안 들어옴
- 원인: 토큰 누락, 잘못된 콘텐츠 타입, 프레임 크기 초과
- 조치: 헤더 토큰/이미지 형식(jpg/png)/프레임 크기 점검
