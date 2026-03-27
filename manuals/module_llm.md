# LLM 모듈 운영 가이드

## 1. 한 줄 설명

챗봇, 메모리, 지식파일 인덱싱, 음성(STT/TTS), 이미지 생성 기능을 제공합니다.

## 2. API 기본 경로

- `/api/v1/llm`

## 3. 주요 기능

- 스트리밍 채팅
- 세션 메모리 조회/초기화
- 지식파일 업로드/재인덱싱
- STT, TTS, 이미지 생성
- 추천 질문 제공

## 4. 주요 엔드포인트

- `POST /api/v1/llm/chat`
- `GET /api/v1/llm/memory`
- `POST /api/v1/llm/memory/reset`
- `GET /api/v1/llm/knowledge`
- `GET /api/v1/llm/knowledge/files`
- `POST /api/v1/llm/knowledge/reindex`
- `POST /api/v1/llm/upload`
- `POST /api/v1/llm/stt`
- `POST /api/v1/llm/tts`
- `POST /api/v1/llm/image`
- `POST /api/v1/llm/result`
- `GET /api/v1/llm/recommended-questions`

## 5. 관련 환경변수

- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `LLM_MODEL`, `OPENAI_MODEL`
- `EMBEDDING_MODEL`
- `OPENAI_STT_MODEL`, `OPENAI_TTS_MODEL`, `OPENAI_IMAGE_MODEL`, `OPENAI_VISION_MODEL`
- `LLM_KNOWLEDGE_PATH`

## 6. 운영 점검 포인트

1. OpenAI 키가 비어 있으면 STT/TTS/이미지 기능 실패 가능
2. 지식파일 업로드 후에는 재인덱싱 상태 확인
3. 채팅 지연 시 웹검색 옵션과 외부 API 상태 점검

## 7. 자주 발생하는 문제

- 증상: 챗봇은 되는데 음성/이미지 기능 실패
- 원인: 해당 API 키 누락 또는 모델 권한 문제
- 조치: `.env` 키 재확인 후 `server_api` 재시작
