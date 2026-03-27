# README for NotebookLM

이 폴더는 `/home/orugu/Docker/Final_project_rss` 프로젝트 중 LLM 모듈 관련 자료를 NotebookLM에 업로드하기 전에, 해석 기준과 읽는 순서를 먼저 정리해 두기 위한 폴더다. 목적은 PM 제출용 최종 보고서를 직접 대체하는 것이 아니라, NotebookLM이 `역할`, `연결 구조`, `현재 구현 범위`, `운영 연계`, `한계`를 과장 없이 정리하도록 입력 품질을 높이는 것이다.

## 이 자료 묶음의 목적
- LLM 모듈이 전체 서비스 안에서 무엇을 담당하는지 설명한다.
- 실제 운영 화면과 연결된 기능 범위를 구분한다.
- 코드에 존재하는 기능과 현재 운영 중인 기능을 분리한다.
- 개념 아키텍처와 현재 구현 아키텍처를 분리한다.
- PM이 전체 서비스 보고서에 재사용하기 좋은 보수적 설명 재료를 만든다.

## 이 자료 묶음이 다루는 범위
- 주 범위: `/server_api/src/modules/llm`
- 연결 범위: `src/main.py`, `src/api/v1/router.py`, `nginx/html/js/dashboard.js`, 운영 화면 HTML, LLM 관련 아키텍처 문서
- 비범위: LLM과 직접 연결되지 않는 타 모듈 내부 구현 상세, 전체 서비스 일반 정적 자산, 설치 로그

## 해석 원칙
1. 코드에 있는 기능이 모두 운영 중이라고 가정하지 않는다.
2. 운영 연계 여부는 프론트엔드 호출 근거가 있는 경우에만 `운영 연계됨`으로 쓴다.
3. 개념 아키텍처 그림과 현재 구현 코드는 분리해서 읽는다.
4. `sample` 경로는 전부 데모 전용이 아니다. `sample/agent.py`는 실제 핵심 오케스트레이션 근거다.
5. 세션 메모리는 DB 영속 저장으로 추정하지 않는다. 코드상 확인되는 범위에서는 프로세스 메모리 기반으로 본다.
6. 웹 검색은 `조건부 최신성 보강`으로 해석한다. `실시간 최신성 보장`으로 쓰지 않는다.
7. PostgreSQL, FAISS, 외부 검색 도구가 그림에 등장해도 LLM 모듈의 직접 사용 여부는 코드 기준으로 판단한다.

## 상태 라벨 정의
- `구현됨`: 백엔드 코드 또는 실제 로직이 존재한다.
- `운영 연계됨`: 프론트엔드 호출 또는 실제 서비스 흐름 근거가 확인된다.
- `조건부 사용 가능`: 환경 변수, API 키, 설치 패키지, 네트워크 조건이 충족될 때 사용 가능하다.
- `운영 미확인`: 구현은 있지만 현재 운영 화면에서 직접 호출되는 근거를 확인하지 못했다.
- `개념도에만 존재`: 발표용/설명용 자료에는 있으나 현재 코드로 직접 확인되지 않는다.

## 권장 읽기 순서
1. `01_NotebookLM_자료종류.md`
2. `08_NotebookLM_오해방지_가이드.md`
3. `LLM_Module_Scope_Summary.md`
4. `LLM_Module_API_Summary.md`
5. `05_파일별_NotebookLM_전달의도.md`
6. 핵심 코드 파일
7. 운영 UI 연계 근거 파일
8. 아키텍처 자료
9. 부록 파일

## 핵심 source of truth
- 라우팅/앱 경계: `server_api/src/main.py`, `server_api/src/api/v1/router.py`, `server_api/src/modules/llm/router.py`
- 핵심 질문 처리: `server_api/src/modules/llm/llm_chat_api.py`
- 지식 적재/검색: `server_api/src/modules/llm/services/knowledge_service.py`
- 오케스트레이션/메모리/웹 검색: `server_api/src/modules/llm/sample/agent.py`
- 런타임 연결 근거: `server_api/src/modules/llm/services/agent_service.py`
- 운영 연계 근거: `nginx/html/js/dashboard.js`

## NotebookLM이 특히 주의해야 할 지점
- `sample/agent.py`는 이름과 달리 실제 핵심 로직 근거다.
- `sample/main.py`, `sample/static/*`는 데모 자료 성격으로 분리해서 본다.
- `dashboard.js`에서 현재 직접 확인되는 LLM 호출은 `chat`, `stt`, `tts`, `recommended-questions`다.
- `upload`, `knowledge/*`, `image`, `result`는 구현 존재와 운영 연계를 분리해서 서술해야 한다.
- `knowledge_service.py` 기준 FAISS는 항상 사용되는 구조가 아니라 조건부다.

## 이 자료를 바탕으로 작성해야 하는 문서의 성격
- PM용 전체 서비스 보고서에 재사용 가능한 모듈 설명 자료
- 포트폴리오용 자기 PR 문서가 아님
- 과장보다 경계와 범위가 더 중요함

## 금지할 표현
- `실시간 최신성 보장`
- `대화 이력 DB 저장`
- `모든 멀티모달 기능이 운영 중`
- `FAISS 기반 RAG가 항상 동작`
- `그림에 있으므로 실제 직접 사용`
