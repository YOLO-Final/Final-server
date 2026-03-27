# VOICE_INTERACTION Module (Code)

## 목적
음성 인터랙션 기능의 상태/확장 포인트를 제공합니다.

## 핵심 파일
- `server_api/src/modules/voice_interaction/router.py`
- `server_api/src/modules/voice_interaction/service.py`
- `server_api/src/modules/voice_interaction/db/schema.py`

## 라우트 prefix
- `/api/v1/voice`

## 현재 구현
- `GET /status` placeholder

## 확장 가이드
- 실제 음성 인식/명령 API는 LLM media(STT/TTS)와 인터페이스 분리 권장
- 세션/대화 문맥 연동 시 auth 토큰 기반 사용자 식별 통일
