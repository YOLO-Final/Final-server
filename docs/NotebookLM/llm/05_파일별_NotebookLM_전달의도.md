# 파일별 NotebookLM 전달 의도

NotebookLM이 각 파일을 같은 비중으로 읽지 않도록, 파일별 역할과 주의점을 먼저 정리한다.

## /home/orugu/Docker/Final_project_rss/server_api/src/main.py
- 왜 중요한가: 전체 FastAPI 앱의 진입점이며 LLM 모듈이 독립 서비스가 아니라 전체 서비스 일부임을 보여 준다.
- PM 문서에서 쓰일 위치: 서비스 내 위치, 백엔드 진입 구조.
- NotebookLM이 이 파일에서 읽어야 할 것: `api_v1_router`가 앱에 포함되는 구조, `/api/v1` 경계.
- 주의할 점: DB 초기화 코드가 있어도 이를 LLM 모듈 직접 저장 근거로 해석하면 안 된다.

## /home/orugu/Docker/Final_project_rss/server_api/src/api/v1/router.py
- 왜 중요한가: LLM 라우터가 전체 서비스 API 모듈 중 하나로 등록된다는 점을 보여 준다.
- PM 문서에서 쓰일 위치: 전체 서비스 내 모듈 배치 설명.
- NotebookLM이 이 파일에서 읽어야 할 것: `llm_router`가 `auth`, `vision`, `report` 등과 병렬 관계라는 점.
- 주의할 점: 다른 모듈과의 직접 내부 연계를 추정하지 말 것.

## /home/orugu/Docker/Final_project_rss/server_api/src/modules/llm/router.py
- 왜 중요한가: `/llm` 아래 어떤 API가 있는지 가장 먼저 보여 주는 경계 파일이다.
- PM 문서에서 쓰일 위치: LLM API 범위 요약.
- NotebookLM이 이 파일에서 읽어야 할 것: `chat_router`, `media_router`, `result_router`, `recommended-questions`가 묶여 있다는 점.
- 주의할 점: 이 파일은 API 표면만 보여 준다. 운영 사용 여부까지는 판단하지 말 것.

## /home/orugu/Docker/Final_project_rss/server_api/src/modules/llm/llm_chat_api.py
- 왜 중요한가: 채팅, 메모리, 지식 상태, 재색인, 업로드, 웹 진단 API가 모여 있는 핵심 파일이다.
- PM 문서에서 쓰일 위치: 핵심 질문 처리 흐름, 메모리 경계, 지식 관리 범위.
- NotebookLM이 이 파일에서 읽어야 할 것: 질문 요청 시 `ensure_knowledge_current()` 후 agent 응답 스트리밍, 메모리 reset, knowledge 상태 확인, upload/reindex의 존재.
- 주의할 점: `/upload`, `/knowledge/*`, `/health/web`는 구현 존재와 운영 연계 여부를 분리해서 써야 한다.

## /home/orugu/Docker/Final_project_rss/server_api/src/modules/llm/services/knowledge_service.py
- 왜 중요한가: RAG 관련 저장/검색/인덱싱 동작을 가장 직접적으로 보여 준다.
- PM 문서에서 쓰일 위치: 문서 저장/검색 방식, OCR, FAISS fallback, 한계 설명.
- NotebookLM이 이 파일에서 읽어야 할 것: TXT/PDF/Image 파일 처리, 스캔 PDF 텍스트 추출 실패 시 placeholder, OpenAI Vision OCR 사용, chunking, 임베딩 가능 시 FAISS, 불가 시 fallback 상태.
- 주의할 점: `indexed_chunks`가 0이라고 문서가 전혀 없는 것은 아닐 수 있다. fallback_only 상태를 정확히 구분해야 한다.

## /home/orugu/Docker/Final_project_rss/server_api/src/modules/llm/sample/agent.py
- 왜 중요한가: 실제 질문 처리, 세션 메모리, 웹 검색, 응답 생성, source 링크 부착을 담당하는 핵심 오케스트레이션이다.
- PM 문서에서 쓰일 위치: 처리 흐름, 세션 메모리, 외부 의존성, 웹 검색 보강, 리스크/한계.
- NotebookLM이 이 파일에서 읽어야 할 것: 프로세스 메모리 기반 session state, 지식 컨텍스트 + 웹 컨텍스트 결합, 최신성 판단, 조건부 웹 검색, 스트리밍 응답 생성.
- 주의할 점: 경로명이 `sample`이지만 `agent_service.py`를 통해 실제 서비스에서 사용된다. 반대로 `sample/main.py`, `sample/static`은 데모 성격일 수 있으므로 분리해서 해석해야 한다.

## /home/orugu/Docker/Final_project_rss/server_api/src/modules/llm/services/agent_service.py
- 왜 중요한가: `sample/agent.py`를 실제 런타임 singleton으로 연결하는 명시적 근거다.
- PM 문서에서 쓰일 위치: 구현 근거 부록, 오해 방지 설명.
- NotebookLM이 이 파일에서 읽어야 할 것: `get_agent()`가 `agent_instance`를 반환한다는 점.
- 주의할 점: 짧은 파일이라고 중요도가 낮은 것은 아니다.

## /home/orugu/Docker/Final_project_rss/server_api/src/modules/llm/services/openai_service.py
- 왜 중요한가: OpenAI 클라이언트 생성 조건과 `OPENAI_API_KEY` 의존성을 보여 준다.
- PM 문서에서 쓰일 위치: 외부 의존성, 운영 전제.
- NotebookLM이 이 파일에서 읽어야 할 것: openai 패키지와 API 키가 없으면 일부 기능이 동작하지 않을 수 있다는 점.
- 주의할 점: 이 파일만으로 전체 provider 구조를 단정하지 말 것. 실제 사용은 `agent.py`, `llm_media_api.py`, `llm_question.py`를 함께 봐야 한다.

## /home/orugu/Docker/Final_project_rss/server_api/src/modules/llm/llm_media_api.py
- 왜 중요한가: STT, TTS, Image API 범위와 에러 조건을 보여 준다.
- PM 문서에서 쓰일 위치: 부가 기능 범위, 멀티모달 연계, 외부 API 의존성.
- NotebookLM이 이 파일에서 읽어야 할 것: STT/TTS/Image가 OpenAI provider 중심이며 파일 형식/크기 제한과 fallback이 존재한다는 점.
- 주의할 점: `/image`가 존재해도 현재 운영 UI에서 사용 중이라는 근거는 별도 확인이 필요하다.

## /home/orugu/Docker/Final_project_rss/server_api/src/modules/llm/llm_question.py
- 왜 중요한가: 추천 질문 기능의 구현 범위를 보여 준다.
- PM 문서에서 쓰일 위치: 운영 편의 기능, UI 초기화 기능 설명.
- NotebookLM이 이 파일에서 읽어야 할 것: OpenAI 생성 실패 시 정적 기본 질문으로 fallback하는 구조.
- 주의할 점: 핵심 챗봇 기능보다 우선순위는 낮다.

## /home/orugu/Docker/Final_project_rss/server_api/src/modules/llm/llm_result_api.py
- 왜 중요한가: LLM 단일 프롬프트 처리 API가 별도로 존재한다는 사실을 보여 준다.
- PM 문서에서 쓰일 위치: 구현 보유 기능 목록, 부록.
- NotebookLM이 이 파일에서 읽어야 할 것: `prompt`, `temperature`, `max_output_tokens` 기반 단일 결과 생성 API 존재.
- 주의할 점: 현재 운영 UI 직접 호출 근거는 확인되지 않았다.

## /home/orugu/Docker/Final_project_rss/nginx/html/js/dashboard.js
- 왜 중요한가: 운영 UI가 실제로 어떤 LLM 기능을 사용 중인지 판단하는 핵심 파일이다.
- PM 문서에서 쓰일 위치: 운영 연계 범위, 실제 사용자 흐름, 화면 동작 설명.
- NotebookLM이 이 파일에서 읽어야 할 것: `/api/v1/llm/chat`, `/stt`, `/tts`, `/recommended-questions` 호출, 채팅 후 TTS 연계, 마이크 입력 후 STT 적용.
- 주의할 점: 이 파일에 없는 API는 `운영 UI 미확인`이지 `미구현`이 아니다.

## /home/orugu/Docker/Final_project_rss/nginx/html/configuration.html
- 왜 중요한가: 운영 화면이 `dashboard.js`를 포함한다는 실제 페이지 근거다.
- PM 문서에서 쓰일 위치: 운영 화면 출처, 캡처 근거.
- NotebookLM이 이 파일에서 읽어야 할 것: 운영 페이지에서 공통 JS를 로드하는 구조.
- 주의할 점: 기능 로직보다 화면 셸 근거 파일이다.

## /home/orugu/Docker/Final_project_rss/nginx/html/auto.html
- 왜 중요한가: 추가 운영 화면이 동일 JS를 사용한다는 점을 보강한다.
- PM 문서에서 쓰일 위치: 운영 화면 범위 보강, 캡처 후보.
- NotebookLM이 이 파일에서 읽어야 할 것: 공통 JS 기반 운영 화면 구조.
- 주의할 점: 페이지가 존재한다고 특정 LLM 기능이 각 화면에서 모두 노출된다고 단정하지 말 것.

## /home/orugu/Docker/Final_project_rss/docs/architecture/llm_architecture_report.md
- 왜 중요한가: 코드 기반으로 정리된 기존 메모다.
- PM 문서에서 쓰일 위치: 구현 개요 요약, 구조 보조 설명.
- NotebookLM이 이 파일에서 읽어야 할 것: 실제 진입 경로, 운영 UI 호출자, DB 직접 미사용 경계.
- 주의할 점: 보조 문서일 뿐 최종 판단은 코드 기준으로 해야 한다.

## /home/orugu/Docker/Final_project_rss/docs/architecture/llm_architecture.d2
- 왜 중요한가: LLM 모듈 상세 구조를 도식화한 자료다.
- PM 문서에서 쓰일 위치: 현재 구현 구조 설명, 부록 도식.
- NotebookLM이 이 파일에서 읽어야 할 것: FE/BE/Service/External/Data 계층 구분.
- 주의할 점: 도식과 코드가 충돌하면 코드가 우선이다.

## /home/orugu/Docker/Final_project_rss/docs/architecture/llm_architecture_sequence.puml
- 왜 중요한가: 질문 처리 흐름을 단계적으로 표현한다.
- PM 문서에서 쓰일 위치: 시퀀스 설명, 처리 흐름 장.
- NotebookLM이 이 파일에서 읽어야 할 것: 질문 입력부터 StreamingResponse 반환까지의 단계.
- 주의할 점: 단순화된 흐름도이므로 세부 조건은 코드로 보완해야 한다.

## /home/orugu/Docker/Final_project_rss/docs/architecture/발표용_기술반영_아키텍처.d2
- 왜 중요한가: 서비스 전체 안에서 LLM 관련 계층을 쉽게 보여 주는 발표용 개념도다.
- PM 문서에서 쓰일 위치: 개념 아키텍처, 발표용 구조 그림.
- NotebookLM이 이 파일에서 읽어야 할 것: 사용자 화면, 서비스 영역, AI 핵심, 저장 영역의 관계.
- 주의할 점: PostgreSQL, 상태 저장소, 외부 도구가 그림에 있어도 LLM 모듈 직접 사용 여부는 코드 기준으로 따져야 한다.

## /home/orugu/Docker/Final_project_rss/docs/architecture/발표용_사용자흐름_정돈.d2
- 왜 중요한가: 사용자 질문 관점의 흐름을 빠르게 설명하기 좋다.
- PM 문서에서 쓰일 위치: 사용자 흐름, 서비스 이용 시나리오 설명.
- NotebookLM이 이 파일에서 읽어야 할 것: 화면, API, 기능별 서비스, AI 처리, 저장소 흐름.
- 주의할 점: 개념 흐름도이므로 현재 운영 연계 기능 범위는 `dashboard.js`와 교차 확인해야 한다.

## 미발견 파일
- 이번 작업에서 사용자 지정 후보 파일 중 미발견 파일은 없었다.
