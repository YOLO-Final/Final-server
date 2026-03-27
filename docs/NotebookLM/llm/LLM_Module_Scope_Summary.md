# LLM Module Scope Summary

이 문서는 `/home/orugu/Docker/Final_project_rss/server_api/src/modules/llm` 기준으로, PM용 보고서 작성을 위해 NotebookLM이 먼저 이해해야 할 LLM 모듈의 실제 범위와 현재 상태를 요약한 문서다. 본문은 실제 코드와 운영 UI 호출 근거를 기준으로 작성한다.

## 1. 모듈 역할
- 이 모듈은 서비스 내에서 `문서 기반 질의응답`, `세션 메모리 기반 대화 보조`, `조건부 최신성 보강`, `STT/TTS`, `추천 질문` 기능을 담당한다.
- 전체 서비스 진입 경로는 `src/main.py -> src/api/v1/router.py -> src/modules/llm/router.py`다.
- 핵심 질문 처리 API는 `llm_chat_api.py`이며, 지식 적재/검색은 `knowledge_service.py`, 응답 오케스트레이션은 `sample/agent.py`에 집중되어 있다.

## 2. 현재 운영 UI와 연결된 기능
- 현재 `nginx/html/js/dashboard.js`에서 직접 호출이 확인되는 LLM API는 `/api/v1/llm/chat`, `/api/v1/llm/stt`, `/api/v1/llm/tts`, `/api/v1/llm/recommended-questions`다.
- 따라서 운영 연계가 확인된 기능은 `채팅`, `음성 입력(STT)`, `음성 출력(TTS)`, `추천 질문`이다.
- `configuration.html`, `auto.html`, `manual.html`, `iot.html`, `model.html` 등 운영 화면 HTML은 공통으로 `dashboard.js`를 로드한다.

## 3. 구현은 있으나 운영 연계가 직접 확인되지 않은 기능
- `/api/v1/llm/image`
- `/api/v1/llm/result`
- `/api/v1/llm/upload`
- `/api/v1/llm/knowledge`
- `/api/v1/llm/knowledge/files`
- `/api/v1/llm/knowledge/reindex`
- `/api/v1/llm/health/web`

위 API들은 백엔드 구현은 확인되지만, 현재 운영 UI인 `dashboard.js`에서 직접 호출되는 근거는 확인하지 못했다. 따라서 PM용 문서에서는 `구현 존재, 운영 미확인` 또는 `관리/보조 기능` 정도로 표현하는 것이 적절하다.

## 4. 핵심 질문 처리 흐름
1. 프론트엔드가 `/api/v1/llm/chat`으로 질문을 전송한다.
2. `llm_chat_api.py`가 지식 상태를 최신화한다.
3. `agent_service.py`를 통해 singleton agent를 가져온다.
4. `sample/agent.py`가 세션 메모리, 로컬 문서 컨텍스트, 필요 시 웹 검색 컨텍스트를 조합한다.
5. 선택된 provider로 답변을 스트리밍 생성한다.
6. 최종 응답은 텍스트 스트림으로 반환되고, 필요 시 source 링크가 붙는다.
7. 사용자/응답 대화 내역은 agent 내부 세션 상태에 반영된다.

## 5. 문서 저장·검색 방식
- 지식 문서는 기본적으로 파일 기반이다.
- 기본 경로는 `./knowledge_base`이며, `LLM_KNOWLEDGE_PATH` 환경 변수로 대체 가능하다.
- TXT, PDF, 이미지 파일을 읽어 문서 컨텍스트를 만든다.
- PDF는 텍스트 레이어가 없으면 placeholder 안내 문구로 대체될 수 있다.
- 이미지는 OpenAI Vision 기반 OCR로 텍스트를 추출하려 시도한다.
- 임베딩과 관련 패키지가 준비된 경우 FAISS retriever를 사용한다.
- 조건이 충족되지 않으면 로컬 chunk/fallback 검색 구조로 축소 동작할 수 있다.

## 6. 세션 메모리 저장 경계
- 세션 상태는 agent 내부 메모리 구조에 유지된다.
- 코드상 확인되는 구조는 `chat_history`, `memory_summary`, `knowledge_memory`, `web_history`다.
- 별도 DB 영속 저장 코드는 현재 LLM 모듈 범위 안에서 직접 확인되지 않는다.
- 따라서 PM 문서에는 `프로세스 메모리 기반 세션 상태`로 쓰는 것이 안전하다.

## 7. 외부 의존성
- OpenAI: 핵심 대화, STT, TTS, 이미지 생성, 이미지 OCR에 사용된다.
- Serper/Tavily: 조건부 웹 검색 보강에 사용될 수 있다.
- Gemini/vLLM: provider 옵션 코드 경로는 있으나 실제 운영 활성화 여부는 별도 확인이 필요하다.
- FAISS / LangChain 관련 패키지: 설치 및 임베딩 가능 여부에 따라 검색 계층이 달라질 수 있다.

## 8. 현재 범위 요약
- 현재 코드 기준으로 LLM 모듈은 `질문 응답`, `문서 기반 컨텍스트 결합`, `세션 메모리`, `STT/TTS`, `추천 질문`, `조건부 웹 검색 보강`을 구현하고 있다.
- 현재 운영 UI 기준으로 직접 연계가 확인된 범위는 `chat`, `stt`, `tts`, `recommended-questions`다.
- 현재 코드 기준으로 PostgreSQL이나 Redis에 LLM 대화 상태를 직접 저장하는 구조는 확인되지 않았다.

## 9. 핵심 한계와 주의점
- `sample/agent.py`는 실제 핵심 로직이지만 경로명만 보고 데모 전용으로 오해하기 쉽다.
- 웹 검색은 조건부 보강 기능이며, `항상 최신 정보 보장`으로 쓰면 안 된다.
- 세션 메모리는 프로세스 메모리 기반으로 보이므로 서버 재시작 후 유지된다고 쓰면 안 된다.
- FAISS는 환경에 따라 미사용일 수 있다.
- 백엔드에 API가 존재해도 운영 화면 직접 사용 여부는 별도로 확인해야 한다.

## 10. PM 문서용 서술 기준
- `이 모듈은 서비스 내에서 문서 기반 AI 상담 기능을 담당한다.`
- `현재 운영 화면과 직접 연계가 확인된 기능은 채팅, STT, TTS, 추천 질문이다.`
- `문서 검색과 세션 메모리를 결합해 응답을 생성하며, 최신성이 필요한 질의에는 조건부 웹 검색 보강을 시도할 수 있다.`
- `일부 부가 API는 구현되어 있으나 현재 운영 UI 직접 연계 여부는 별도 확인이 필요하다.`
