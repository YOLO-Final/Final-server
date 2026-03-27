# VOICE_INTERACTION 모듈 운영 가이드

## 1. 한 줄 설명

음성 인터랙션 모듈의 상태 점검용 API를 제공합니다.

## 2. API 기본 경로

- `/api/v1/voice`

## 3. 주요 기능

- 음성 모듈 상태 확인

## 4. 주요 엔드포인트

- `GET /api/v1/voice/status`

## 5. 운영 점검 포인트

1. 상태 확인 후 실제 음성 기능은 LLM 모듈(STT/TTS)과 함께 점검
2. 장애 분리 시 voice status와 llm stt/tts를 구분 확인

## 6. 자주 발생하는 문제

- 증상: 음성 전체가 안된다고 보고됨
- 조치: 먼저 `/voice/status`와 `/llm/stt`를 분리 테스트
