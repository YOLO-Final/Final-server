# LLM Module (Code)

## 목적
채팅, 지식 베이스, STT/TTS/이미지 생성, 결과 요약 API를 제공합니다.

## 핵심 파일
- `server_api/src/modules/llm/router.py`
- `server_api/src/modules/llm/llm_chat_api.py`
- `server_api/src/modules/llm/llm_media_api.py`
- `server_api/src/modules/llm/llm_result_api.py`
- `server_api/src/modules/llm/agent.py`
- `server_api/src/modules/llm/services/openai_service.py`
- `server_api/src/modules/llm/services/knowledge_service.py`

## 라우트 prefix
- `/api/v1/llm`

## 주요 흐름
1. chat 요청 수신
2. agent에서 메모리/지식/웹검색 컨텍스트 조합
3. provider(openai/gemini/vllm)별 LLM 호출
4. 스트리밍 응답 반환

## 최적화 반영 포인트
- OpenAI client 캐시 재사용
- 웹/답변 캐시 eviction O(1)
- 정규식/도메인 리스트 상수화

## 중요 환경변수
- `OPENAI_API_KEY`, `GEMINI_API_KEY`
- `OPENAI_MODEL`, `LLM_MODEL`, `EMBEDDING_MODEL`
- `OPENAI_STT_MODEL`, `OPENAI_TTS_MODEL`, `OPENAI_IMAGE_MODEL`, `OPENAI_VISION_MODEL`
- `LLM_KNOWLEDGE_PATH`

## 수정 시 주의
- 프런트 스트리밍 파싱 포맷 깨지지 않게 유지
- provider fallback 로직 순서 변경 시 품질 영향 큼
- 웹검색/캐시 정책 변경은 응답 일관성 검증 필요
