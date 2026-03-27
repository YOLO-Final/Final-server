# Final Project RSS LLM Architecture Report

이 문서는 `server_api/src/modules/llm`를 기준으로 실제 코드 연결만 추적해 정리한 발표용 아키텍처 메모입니다.

## 핵심 결론

- LLM 모듈의 실제 진입 경로는 `src/main.py -> src/api/v1/router.py -> src/modules/llm/router.py`입니다.
- 운영 UI의 실제 호출자는 `nginx/html/js/dashboard.js`이며, 주로 `/api/v1/llm/chat`, `/tts`, `/stt`, `/recommended-questions`를 사용합니다.
- 채팅 기능의 핵심 오케스트레이션은 `src/modules/llm/sample/agent.py`의 `CSAgent`가 담당합니다.
- 지식베이스는 `knowledge_service.py`가 파일 기반으로 관리하며, 필요 시 OpenAI Vision OCR과 선택적 FAISS retriever를 사용합니다.
- 현재 코드 기준으로 LLM 모듈은 PostgreSQL이나 Redis를 직접 사용하지 않습니다. 세션 상태와 캐시는 메모리 내부 구조입니다.

## 실제 책임 분리

- API entry: `router.py`, `llm_chat_api.py`, `llm_media_api.py`, `llm_question.py`, `llm_result_api.py`
- orchestration: `services/agent_service.py`, `sample/agent.py`
- provider access: `services/openai_service.py`, `sample/agent.py`
- knowledge pipeline: `services/knowledge_service.py`
- shared config: `src/lib/env_loader.py`, `src/lib/settings.py`
- frontend callers: `nginx/html/js/dashboard.js`

## 발표 포인트

- 이 구조의 핵심은 "UI 호출", "FastAPI API 경계", "LLM orchestration", "외부 provider", "지식 소스"를 분리해 보여주는 것입니다.
- 모든 함수를 그리기보다 `knowledge_service`와 `CSAgent`를 중심으로 데이터 흐름을 설명하는 편이 발표에 적합합니다.
- DB는 시스템 전체에는 존재하지만, LLM 모듈의 직접 persistence 경계 밖에 있다는 점을 명시해야 오해를 줄일 수 있습니다.
