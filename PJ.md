# LLM 모듈 고도화 설명서

이 문서는 `server_api/src/modules/llm`에 대해, 내가 고도화했던 부분들을 직접 설명할 수 있도록 정리한 문서입니다.
단순히 "무슨 API가 있다"가 아니라, 어떤 문제를 해결하려고 어떤 코드를 넣었는지 중심으로 설명합니다.

---

## 1. LLM 모듈의 전체 목적

이 모듈은 단순 채팅 API가 아니라 아래 기능을 한 번에 담당하는 운영형 LLM 백엔드입니다.

- 대화형 챗봇
- 세션별 메모리 관리
- 사내 지식 문서 검색
- 최신 정보가 필요한 경우 웹 검색 보강
- STT / TTS / 이미지 생성
- 추천 질문 생성

핵심 진입 구조는 아래와 같습니다.

```text
router.py
 ├─ llm_chat_api.py
 │   └─ agent.py
 ├─ llm_media_api.py
 ├─ llm_result_api.py
 └─ llm_question.py
```

설명할 때는 이렇게 말하면 됩니다.

> 이 모듈은 단순 OpenAI 호출 래퍼가 아니라, 채팅 흐름 제어, 지식 검색, 웹 검색, 음성/이미지 기능까지 통합한 운영형 AI 모듈입니다.

---

## 2. 내가 고도화한 핵심 포인트

이 LLM 모듈에서 설명 포인트가 되는 고도화는 크게 8개입니다.

1. 세션별 메모리 관리
2. 지식 문서 검색 고도화
3. OCR 및 폴백 구조 추가
4. 최신 정보 대응을 위한 웹 검색 자동화
5. 빠른 직접 응답 경로 추가
6. 스트리밍 응답 품질 개선
7. 운영 안정성을 위한 캐시/폴백/예외 처리
8. 미디어 API(STT/TTS/이미지) 운영형 보완

---

## 3. 세션별 메모리 관리 고도화

### 왜 넣었는가

기본 챗봇은 매 요청이 독립적이라 이전 대화를 기억하지 못합니다.
운영 환경에서는 사용자가 같은 세션에서 이어서 질문하기 때문에, 문맥 유지가 필요했습니다.

### 구현 위치

- `server_api/src/modules/llm/agent.py`

### 핵심 코드

```python
self._session_state[key] = {
    "chat_history": [],
    "memory_summary": "",
    "knowledge_memory": [],
    "web_history": [],
}
```

```python
if len(state["chat_history"]) > max_messages:
    overflow = state["chat_history"][:-max_messages]
    state["chat_history"] = state["chat_history"][-max_messages:]
    state["memory_summary"] = self._merge_memory_summary(...)
```

### 설명 포인트

- 세션마다 대화 상태를 분리해서 관리합니다.
- 대화가 길어지면 무한히 쌓지 않고, 오래된 대화는 `memory_summary`로 압축합니다.
- 그래서 문맥은 유지하면서도 프롬프트 길이 폭증을 막을 수 있습니다.

### 발표용 한 줄

> 대화 이력을 그냥 누적하지 않고, 최근 대화는 유지하고 오래된 대화는 요약 메모리로 압축하도록 고도화했습니다.

---

## 4. 지식 문서 검색 고도화

### 왜 넣었는가

현장/품질 문서를 챗봇이 참고하려면 단순 프롬프트 입력만으로는 한계가 있었습니다.
그래서 로컬 문서를 읽고 검색해서 답변에 반영하는 구조를 넣었습니다.

### 구현 위치

- `server_api/src/modules/llm/services/knowledge_service.py`
- `server_api/src/modules/llm/agent.py`

### 핵심 구조

문서를 읽고:

- `.txt` 직접 로드
- `.pdf` 텍스트 추출
- 이미지 OCR 수행

그다음:

- 청크 분할
- 가능하면 FAISS 벡터 인덱스 생성
- 불가능하면 로컬 청크 기반 검색 폴백

### 핵심 코드

```python
splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120)
chunked_docs = splitter.split_documents(all_docs)
```

```python
vector_db = FAISS.from_documents(chunked_docs, agent.embeddings)
agent.retriever = vector_db.as_retriever(search_kwargs={"k": 6})
```

```python
agent.set_local_knowledge_docs(local_chunks)
```

### 설명 포인트

- 검색 품질을 위해 문서를 청크로 나눴습니다.
- 벡터 검색이 가능하면 FAISS를 사용합니다.
- 의존성이 없거나 임베딩이 안 되더라도, 텍스트 조각 기반 검색으로 최소 기능은 유지됩니다.
- 즉, "잘 되면 고급 검색, 안 돼도 망가지지 않는 구조"입니다.

### 발표용 한 줄

> 문서를 그냥 읽게 한 것이 아니라, 청크 분할과 벡터 검색을 붙이고, 실패해도 폴백 검색으로 동작하도록 설계했습니다.

---

## 5. 하이브리드 검색 고도화

### 왜 넣었는가

벡터 검색만 쓰면 OCR 품질이 낮거나 용어가 살짝 달라졌을 때 검색 누락이 생길 수 있습니다.
그래서 dense 검색과 sparse 검색을 함께 섞는 구조를 넣었습니다.

### 구현 위치

- `server_api/src/modules/llm/agent.py`

### 핵심 코드

```python
dense_candidates = self._dense_retrieval_candidates(...)
sparse_candidates = self._sparse_retrieval_candidates(...)
```

```python
ranked = sorted(
    merged_candidates.values(),
    key=lambda item: (dense_weight * float(item.get("dense_score", 0.0)))
    + (sparse_weight * float(item.get("sparse_score", 0.0))),
    reverse=True,
)
```

### 설명 포인트

- dense retrieval: 임베딩 기반 의미 검색
- sparse retrieval: 토큰 겹침 기반 검색
- 둘을 합쳐서 점수화하기 때문에 실제 현장 문서처럼 품질이 고르지 않은 데이터에도 강합니다.

### 발표용 한 줄

> 검색 안정성을 높이기 위해 벡터 검색 하나만 쓰지 않고, 의미 검색과 키워드 검색을 합친 하이브리드 검색으로 고도화했습니다.

---

## 6. OCR 및 폴백 구조 고도화

### 왜 넣었는가

실제 문서는 PDF나 이미지가 많고, 특히 스캔 문서는 텍스트 추출이 잘 안 됩니다.
그래서 OCR을 여러 단계로 시도하도록 만들었습니다.

### 구현 위치

- `server_api/src/modules/llm/services/knowledge_service.py`

### OCR 우선순위

1. PDF 텍스트 직접 추출
2. OpenAI Vision OCR
3. 로컬 OCR(`pytesseract`)
4. sidecar 텍스트 파일(`.txt`, `_ocr.txt`)
5. 그래도 안 되면 placeholder 문서 생성

### 핵심 코드

```python
response = client.responses.create(
    model=model,
    input=[ ... input_text ..., ... input_image ... ],
)
```

```python
local_text = _local_image_ocr_text(path)
if local_text:
    ...
```

```python
sidecar_text, sidecar_name = _read_sidecar_ocr_text(path)
```

### 설명 포인트

- OpenAI Vision이 있으면 그걸 우선 사용합니다.
- API 키가 없거나 실패하면 로컬 OCR로 폴백합니다.
- 그것도 안 되면 사람이 붙여둔 텍스트 파일을 읽습니다.
- 최종적으로는 "문서가 완전히 검색에서 빠지지 않도록" placeholder까지 남깁니다.

### 발표용 한 줄

> 실제 운영 문서는 품질이 제각각이라 OCR을 단일 방식으로 처리하지 않고, OpenAI OCR, 로컬 OCR, sidecar 파일까지 계층적으로 폴백되도록 만들었습니다.

---

## 7. 최신 정보 대응용 웹 검색 고도화

### 왜 넣었는가

LLM은 학습 시점 이후 정보가 오래될 수 있습니다.
특히 "오늘", "최근", "최신", "현재" 같은 질문은 내부 문서만으로 답하면 틀릴 가능성이 높습니다.

### 구현 위치

- `server_api/src/modules/llm/agent.py`

### 핵심 아이디어

질문을 보고:

- 최신 정보가 필요한지 판단
- 필요하면 자동 웹 검색
- 웹 결과를 컨텍스트에 붙여서 답변 생성
- 출처 링크도 함께 제공

### 핵심 코드

```python
fresh_required = self._needs_fresh_data(text_query)
auto_web = False if disable_auto_web else self._should_use_web_search(text_query)
force_web = use_web_search or auto_web
```

```python
web = self._web_context(...)
sources = self._extract_sources(web) if web else []
```

### 설명 포인트

- 사용자가 웹 검색을 직접 켜지 않아도, 질문이 최신성 요구일 때는 자동으로 웹 검색이 붙습니다.
- 즉, 모델 hallucination을 줄이기 위해 최신성이 필요한 질문은 별도 처리한 것입니다.
- 답변 끝에 citation block을 붙여 출처도 확인할 수 있습니다.

### 발표용 한 줄

> 최신 정보가 필요한 질문은 모델 내부 지식만 믿지 않고, 자동으로 웹 컨텍스트를 붙이는 구조로 고도화했습니다.

---

## 8. 빠른 직접 응답 경로 고도화

### 왜 넣었는가

모든 질문을 무조건 전체 LLM 파이프라인으로 보내면 느리고 비효율적입니다.
일부 질문은 규칙 기반으로 더 정확하고 빠르게 답할 수 있습니다.

### 구현 위치

- `server_api/src/modules/llm/agent.py`

### 현재 들어간 직접 응답

- OCR 원문 그대로 요청
- 회사명/제조사 질문
- 보드 종류 질문

### 핵심 코드

```python
direct_ocr_answer = self._direct_ocr_text_answer(text_query)
if direct_ocr_answer:
    yield direct_ocr_answer
    return
```

```python
direct_company_answer = self._direct_company_answer(text_query)
if direct_company_answer:
    yield direct_company_answer
    return
```

### 설명 포인트

- OCR 원문을 그대로 달라는 요청은 LLM 요약을 거치지 않고 바로 반환합니다.
- 특정 필드 추출형 질문은 문서에서 정규식으로 바로 뽑아서 답합니다.
- 이 방식은 속도와 정확도를 동시에 개선합니다.

### 발표용 한 줄

> 자주 나오는 구조화된 질문은 전체 생성형 응답 대신 직접 추출 경로를 넣어서, 더 빠르고 더 정확하게 답하도록 만들었습니다.

---

## 9. 스트리밍 응답 품질 고도화

### 왜 넣었는가

스트리밍 응답이 너무 잘게 끊기면 사용자가 읽기 불편합니다.
그래서 청크를 그대로 뿌리지 않고 문장 경계에 맞춰 버퍼링하는 로직을 넣었습니다.

### 구현 위치

- `server_api/src/modules/llm/agent.py`

### 핵심 코드

```python
boundary = max(pending.rfind("\n"), pending.rfind(". "), pending.rfind("? "), pending.rfind("! "))
if boundary >= 0 or len(pending) >= 120:
    emit_now = pending if boundary < 0 else pending[: boundary + 1]
    yield emit_now
```

### 설명 포인트

- 모델에서 오는 조각을 그대로 내보내지 않고
- 문장 끝, 줄바꿈, 길이 기준으로 잘라서 전송합니다.
- 그래서 UI에서 읽기 좋은 스트리밍이 됩니다.

### 발표용 한 줄

> 스트리밍도 단순 SDK 출력이 아니라, 문장 경계 기준으로 버퍼링해서 사용성이 좋도록 손봤습니다.

---

## 10. 운영 안정성 고도화

### 왜 넣었는가

실운영에서는 의존성이 빠지거나 API 키가 없거나, OCR이 실패하거나, 임베딩이 없을 수 있습니다.
이때 전체 기능이 죽지 않게 하는 것이 중요합니다.

### 구현 위치

- `server_api/src/modules/llm/agent.py`
- `server_api/src/modules/llm/services/knowledge_service.py`
- `server_api/src/modules/llm/services/openai_service.py`

### 들어간 안정화 포인트

- OpenAI 클라이언트 캐시
- 웹 검색 캐시 / 응답 캐시
- 지식 인덱싱 상태 관리
- retriever가 없어도 fallback 검색 유지
- 모델 실패 시 friendly error
- 추천 질문 fallback
- OCR 실패 시 placeholder 유지

### 핵심 코드

```python
@lru_cache(maxsize=1)
def _get_cached_openai_client(api_key: str):
    return OpenAI(api_key=api_key)
```

```python
if not chunked_docs:
    _knowledge_state["last_error"] = "no_documents_after_parsing"
elif not all([FAISS, Document, RecursiveCharacterTextSplitter]):
    _knowledge_state["last_error"] = "vector_dependencies_unavailable"
```

### 설명 포인트

- "최고 성능"보다 "죽지 않는 구조"를 우선했습니다.
- 의존성이 없어도 최소 기능이 돌아가게 설계했습니다.
- 상태값을 따로 저장해서 장애 원인도 바로 볼 수 있게 했습니다.

### 발표용 한 줄

> 운영 환경에서 일부 기능이 실패해도 전체 챗봇이 멈추지 않도록, 폴백과 상태 추적을 많이 넣었습니다.

---

## 11. 보안성 보완

### 왜 넣었는가

오류 로그나 예외 메시지에 API 키, 토큰, 비밀번호가 그대로 노출되면 위험합니다.

### 구현 위치

- `server_api/src/modules/llm/services/security_utils.py`

### 핵심 코드

```python
def redact_text(text: object) -> str:
    ...
    redacted = pattern.sub(_repl, redacted)
    return redacted
```

### 설명 포인트

- 로그에 민감값이 찍히지 않도록 마스킹합니다.
- 운영 로그를 남겨도 키 유출 위험을 줄였습니다.

### 발표용 한 줄

> 운영 로그에서 API Key나 Token이 노출되지 않도록 민감정보 마스킹 유틸도 같이 넣었습니다.

---

## 12. 미디어 API 고도화

### 왜 넣었는가

음성 인식, 음성 합성, 이미지 생성은 데모 수준이 아니라 실제 API로 쓸 수 있어야 했습니다.
그래서 파일 검증과 모델 폴백, 형식 제한, 에러 처리를 강화했습니다.

### 구현 위치

- `server_api/src/modules/llm/llm_media_api.py`

### STT 고도화 포인트

- 업로드 파일을 임시 파일로 저장
- 최소/최대 파일 크기 검증
- OpenAI 옵션 실패 시 최소 인자 재시도

```python
if audio_size < min_audio_bytes:
    return {"text": "", "error": "The audio file is too short."}
if audio_size > max_audio_bytes:
    return {"text": "", "error": "The audio file is too large."}
```

### TTS 고도화 포인트

- 속도 범위 제한
- 출력 포맷 검증
- 오디오 스트리밍 응답

### 이미지 생성 고도화 포인트

- 기본 모델 `gpt-image-1`
- 실패 시 `dall-e-3` 폴백

### 발표용 한 줄

> 미디어 기능도 단순 SDK 호출이 아니라, 파일 검증, 재시도, 모델 폴백까지 넣어서 운영형 API로 다듬었습니다.

---

## 13. 추천 질문 기능 고도화

### 왜 넣었는가

사용자가 첫 화면에서 바로 질문을 시작하기 어렵기 때문에, 빠르게 눌러볼 추천 질문이 필요했습니다.

### 구현 위치

- `server_api/src/modules/llm/llm_question.py`

### 구현 방식

- OpenAI로 짧은 실무형 질문 생성
- 모델 실패 시 기본 질문 목록 반환

```python
try:
    items = _call_model_for_questions(...)
except ...:
    fallback = _default_questions(...)
```

### 설명 포인트

- UI 초기 진입 경험 개선 목적
- 모델 장애가 있어도 항상 같은 응답 스키마 유지

### 발표용 한 줄

> 추천 질문도 모델 의존만 하지 않고 fallback 질문 세트를 둬서, 초기 UX가 깨지지 않도록 했습니다.

---

## 14. 이 모듈을 설명할 때 추천 흐름

발표나 코드 리뷰 때는 아래 순서로 설명하면 자연스럽습니다.

1. 이 모듈은 단순 챗봇이 아니라 운영형 AI 백엔드다
2. 채팅 엔진은 `agent.py`가 중심이다
3. 세션 메모리와 요약 메모리를 넣어 대화 문맥을 유지했다
4. 문서 검색은 청크 분할 + FAISS + fallback 검색으로 고도화했다
5. OCR은 OpenAI, 로컬 OCR, sidecar 파일까지 폴백되게 만들었다
6. 최신 질문은 자동 웹 검색으로 보강했다
7. 자주 묻는 구조형 질문은 직접 응답 경로를 넣어 속도/정확도를 높였다
8. STT/TTS/이미지 생성도 운영형 예외 처리까지 넣었다
9. 전체적으로 "성능"보다 "실제 운영에서 안 죽는 구조"를 우선했다

---

## 15. 파일별 설명 요약

### `router.py`

- LLM 관련 모든 라우터를 `/llm` 아래로 묶는 최상위 엔트리

### `llm_chat_api.py`

- 채팅, 메모리, 지식 상태, 업로드, 재인덱싱 API 제공
- 실제 채팅은 `agent.py`에 위임

### `agent.py`

- 이 모듈의 핵심
- 메모리, 검색, 웹, 프롬프트, 스트리밍 응답을 총괄

### `services/knowledge_service.py`

- 로컬 문서 수집
- OCR
- 청크 분할
- FAISS 인덱싱
- 상태 관리

### `llm_media_api.py`

- STT / TTS / 이미지 생성 API

### `llm_result_api.py`

- 단발성 텍스트 생성 API

### `llm_question.py`

- 추천 질문 생성

### `services/openai_service.py`

- OpenAI 클라이언트 캐시 및 공용 초기화

### `services/security_utils.py`

- 민감정보 마스킹

---

## 16. 파일별 상세 코드 설명

이 섹션은 실제 코드 리뷰나 발표에서 파일을 하나씩 열어가며 설명할 수 있도록 더 자세히 정리한 부분입니다.

### 16-1. `router.py`

파일 역할:

- LLM 모듈의 최상위 라우터
- 채팅, 미디어, 결과 API를 한 prefix 아래로 묶음
- 추천 질문 API를 직접 노출

핵심 코드:

```python
router = APIRouter(prefix="/llm", tags=["llm"])
router.include_router(chat_router)
router.include_router(media_router)
router.include_router(result_router)
```

설명 포인트:

- 이 파일은 비즈니스 로직이 거의 없습니다.
- "라우팅 조립"이 주 역할입니다.
- 모듈을 채팅/미디어/결과로 분리해서 유지보수를 쉽게 만든 구조입니다.

리뷰할 때 볼 점:

- 라우터가 얇게 유지되고 있는지
- 기능이 하나의 파일에 과도하게 몰리지 않았는지
- API prefix와 태그 구성이 일관적인지

발표용 설명:

> `router.py`는 LLM 기능들을 `/llm` 아래로 묶는 진입점이고, 실제 복잡한 로직은 하위 파일로 분리해 구조를 단순하게 유지했습니다.

---

### 16-2. `llm_chat_api.py`

파일 역할:

- 채팅 API
- 세션 메모리 조회 및 초기화 API
- 지식베이스 상태 확인 API
- 지식 파일 업로드/재인덱싱 API
- 웹 검색 진단 API

핵심 엔드포인트:

- `POST /llm/chat`
- `GET /llm/memory`
- `POST /llm/memory/reset`
- `GET /llm/knowledge`
- `GET /llm/knowledge/files`
- `POST /llm/knowledge/reindex`
- `POST /llm/upload`
- `GET /llm/health/web`

중요 구현 포인트:

```python
@chat_router.on_event("startup")
async def startup() -> None:
    _start_background_knowledge_index()
```

```python
return StreamingResponse(stream_wrapper(), media_type="text/plain; charset=utf-8", headers=headers)
```

```python
if to_bool(reset_memory):
    agent.reset_memory(normalized_session)
```

이 파일이 하는 일:

1. HTTP 요청 파싱
2. 최소한의 입력 정리
3. 실제 로직은 `agent.py`와 `knowledge_service.py`에 위임
4. 응답은 스트리밍으로 연결

고도화 설명 포인트:

- 서버 시작 시 지식 인덱싱을 백그라운드로 돌리기 때문에, 서버 부팅을 과도하게 막지 않습니다.
- 요청 시점에도 `ensure_knowledge_current()`로 지식 변경 여부를 다시 확인합니다.
- 업로드 즉시 `update_knowledge()`를 호출해 재인덱싱합니다.

리뷰 포인트:

- Form 기반 입력이 프론트와 잘 맞는지
- startup indexing과 요청 시 recheck가 중복 비용을 너무 만들지 않는지
- 업로드 파일 확장자 검증이 충분한지

발표용 설명:

> `llm_chat_api.py`는 HTTP 계층이고, 채팅 자체를 구현한다기보다 요청을 정리해서 에이전트로 넘기고 지식 상태를 관리하는 입구 역할을 합니다.

---

### 16-3. `agent.py`

파일 역할:

- 이 모듈의 핵심 오케스트레이터
- 세션 상태 관리
- 지식 검색
- 웹 검색
- 직접 응답 처리
- 프롬프트 구성
- LLM 호출
- 스트리밍 응답
- 출처 처리

가장 중요한 공개 메서드:

- `get_ai_streaming_response()`
- `get_memory_snapshot()`
- `reset_memory()`
- `get_web_diagnostics()`

핵심 실행 흐름:

```python
def get_ai_streaming_response(...):
    direct_ocr_answer = self._direct_ocr_text_answer(text_query)
    direct_company_answer = self._direct_company_answer(text_query)
    direct_knowledge_answer = self._direct_knowledge_answer(text_query)
    ...
    memory = self._history_block(session_key)
    knowledge = self._knowledge_context(session_key, text_query)
    web, detected_emotion, fresh_required = self._prepare_context(...)
    prompt = self._build_prompt(...)
    ...
    for part in stream_iter:
        yield part
```

즉, 순서대로 보면:

1. 직접 응답 가능 여부 확인
2. 메모리 컨텍스트 수집
3. 지식베이스 검색
4. 웹 검색 필요 여부 판단
5. 프롬프트 생성
6. 모델 스트리밍 호출
7. 출처 블록 부착
8. 응답 메모리 저장

주요 내부 책임:

#### 세션 상태 관리

- `_session_key()`
- `_ensure_session_state()`
- `_remember()`
- `_history_block()`

설명:

- 사용자별 세션을 안전한 키로 정규화
- 최근 대화와 오래된 대화를 분리 관리
- 오래된 대화는 요약 메모리로 축약

#### 지식 검색

- `_knowledge_context()`
- `_dense_retrieval_candidates()`
- `_sparse_retrieval_candidates()`
- `_fallback_knowledge_search()`

설명:

- 벡터 검색과 토큰 검색을 혼합
- 검색 결과를 문서 snippet 형태로 프롬프트에 주입
- 검색 실패 시에도 fallback 검색으로 최대한 복구

#### 직접 응답

- `_direct_ocr_text_answer()`
- `_direct_company_answer()`
- `_direct_knowledge_answer()`

설명:

- 일부 질문은 LLM 생성 대신 규칙 기반 응답
- 이 경로는 속도와 정확도가 모두 유리

#### 웹 검색

- `_prepare_context()`
- `_needs_fresh_data()`
- `_should_use_web_search()`
- `_web_context()`

설명:

- 최신성이 필요한 질문인지 판단
- 자동 웹 검색 또는 사용자가 강제한 웹 검색 수행
- 결과를 citations 포함 컨텍스트로 변환

#### 스트리밍 처리

- `_buffered_stream()`
- `_buffered_openai_stream()`

설명:

- 모델 토큰을 그대로 전달하지 않고 문장 경계 단위로 끊어서 보냄

#### 모델 선택

- `_get_llm()`
- `_get_openai_client()`

설명:

- `openai`, `gemini`, `vllm`, `vllm_fast` 등 provider 분기 지원
- 환경에 따라 LangChain 래퍼 또는 OpenAI SDK 직접 사용

리뷰 포인트:

- 이 파일에 책임이 너무 많이 몰려 있어서 장기적으로는 분리 여지가 큼
- 상태 관리와 검색, 웹 검색, 프롬프트 생성이 모두 한 파일에 있어 복잡도가 높음
- 반면 현재는 중앙집중형이라 디버깅과 운영 제어는 쉬운 구조

발표용 설명:

> `agent.py`는 이 모듈의 두뇌 역할을 하는 파일이고, 메모리, 검색, 웹 보강, 프롬프트 구성, 스트리밍 출력까지 전체 응답 경로를 총괄합니다.

---

### 16-4. `services/knowledge_service.py`

파일 역할:

- 지식 파일 수집
- 문서 파싱
- OCR
- 청크 분할
- 벡터 인덱싱
- 지식 상태 관리

핵심 함수:

- `get_knowledge_path()`
- `list_knowledge_files()`
- `update_knowledge()`
- `ensure_knowledge_current()`
- `reindex_knowledge()`
- `get_knowledge_status()`
- `load_knowledge_on_startup()`

파일 파싱 경로:

- `_load_text_document()`
- `_load_pdf_document()`
- `_load_image_document()`

중요 포인트:

```python
for path in knowledge_path.iterdir():
    if suffix == ".txt":
        all_docs.extend(_load_text_document(path))
    elif suffix == ".pdf":
        all_docs.extend(_load_pdf_document(path))
    elif suffix in _image_suffixes:
        all_docs.extend(_load_image_document(path, ingest_stats))
```

```python
_knowledge_state["last_error"] = "vector_dependencies_unavailable"
```

```python
if _knowledge_state["fingerprint"] != fingerprint:
    return update_knowledge()
```

설명 포인트:

- 이 파일은 단순 파일 업로드 처리가 아니라 "문서 ingestion 파이프라인"입니다.
- 파일 fingerprint를 저장해서 변경이 없으면 매번 비싼 OCR/인덱싱을 다시 하지 않습니다.
- 상태값을 `_knowledge_state`로 유지해서 API에서 바로 확인 가능하게 했습니다.

OCR 설명 시 강조할 점:

- 이미지 OCR은 OpenAI Vision 우선
- 로컬 OCR 대체 가능
- sidecar text 지원
- 실패해도 placeholder 문서 유지

리뷰 포인트:

- 상태값이 전역 dict라 멀티프로세스 환경에서는 한계가 있을 수 있음
- 인덱싱이 메모리 기반이라 대규모 문서셋에는 확장성 검토 필요
- 그래도 현 단계에서는 운영 편의성과 단순성이 장점

발표용 설명:

> `knowledge_service.py`는 문서를 읽고 검색 가능한 상태로 만드는 ingestion 레이어이고, OCR과 인덱싱, 상태 추적을 모두 담당합니다.

---

### 16-5. `llm_media_api.py`

파일 역할:

- 음성 인식(STT)
- 음성 합성(TTS)
- 이미지 생성

핵심 엔드포인트:

- `POST /llm/stt`
- `POST /llm/tts`
- `POST /llm/image`

STT 흐름:

1. 파일 업로드 수신
2. suffix 보정
3. 임시 파일 저장
4. 파일 크기 검증
5. OpenAI transcription/translation 호출
6. 옵션 실패 시 재시도
7. 텍스트 반환

핵심 코드:

```python
with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
    temp_path = temp.name
    shutil.copyfileobj(file.file, temp)
```

```python
if audio_size < min_audio_bytes:
    return {"text": "", "error": "..."}
```

TTS 흐름:

1. 텍스트 입력
2. 포맷/속도 보정
3. OpenAI speech API 호출
4. 오디오 바이트를 `StreamingResponse`로 반환

이미지 생성 흐름:

1. 프롬프트 검증
2. 기본 모델 시도
3. 실패 시 폴백 모델 시도
4. base64 또는 URL 형태 반환

리뷰 포인트:

- STT가 임시 파일 기반이라 안정적이지만 I/O 비용은 있음
- provider 분기가 아직 OpenAI 중심이라 추후 확장 여지 있음
- 에러를 예외로 던지기보다 JSON으로 반환하는 부분은 API 설계 일관성 측면에서 검토 가능

발표용 설명:

> `llm_media_api.py`는 음성/이미지 기능을 담당하는 파일이고, 단순 SDK 호출이 아니라 파일 검증과 재시도, 모델 폴백까지 포함해 실제 서비스형 API로 만들었습니다.

---

### 16-6. `llm_result_api.py`

파일 역할:

- 복잡한 메모리/검색 없이 단발성 생성만 수행하는 간단한 API

핵심 엔드포인트:

- `POST /llm/result`

핵심 코드:

```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    temperature=request.temperature,
    max_tokens=request.max_output_tokens,
    messages=[{"role": "user", "content": request.prompt}],
)
```

설명 포인트:

- 이 API는 `agent.py` 전체 파이프라인을 타지 않습니다.
- 빠른 연동 테스트나 단순 결과 생성용입니다.
- 채팅 에이전트와 비교했을 때 가장 "얇은" API입니다.

리뷰 포인트:

- 모델명이 하드코딩되어 있음
- 운영 환경에서 provider 확장성은 낮음
- 대신 테스트와 간단 호출엔 명확한 장점이 있음

발표용 설명:

> `llm_result_api.py`는 전체 에이전트 흐름이 필요 없는 경우를 위해 만든 단발성 텍스트 생성 API입니다.

---

### 16-7. `llm_question.py`

파일 역할:

- UI에서 쓸 추천 질문 생성

핵심 함수:

- `_default_questions()`
- `_call_model_for_questions()`
- `get_recommended_questions()`

핵심 코드:

```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    temperature=0.5,
    messages=[{"role": "user", "content": prompt}],
)
```

```python
except (RuntimeError, ValueError, json.JSONDecodeError):
    fallback = _default_questions(...)
```

설명 포인트:

- 추천 질문은 짧고 실무형이어야 하므로 prompt를 강하게 제한
- 번호나 불릿이 붙어 와도 `_extract_questions_from_text()`에서 정리
- 모델 실패 시에도 UI는 같은 응답 구조를 받음

리뷰 포인트:

- 캐시가 없어서 호출 빈도가 높으면 비용 이슈가 있을 수 있음
- 하지만 count 제한과 fallback 구조는 적절함

발표용 설명:

> 추천 질문은 모델이 만들어주되, UI에서 바로 쓰기 좋게 후처리하고 실패 시 기본 질문으로 내려가도록 했습니다.

---

### 16-8. `services/openai_service.py`

파일 역할:

- OpenAI 공용 클라이언트 초기화
- bool 문자열 파싱

핵심 함수:

- `to_bool()`
- `get_openai_client()`

핵심 코드:

```python
@lru_cache(maxsize=1)
def _get_cached_openai_client(api_key: str):
    return OpenAI(api_key=api_key)
```

설명 포인트:

- 요청마다 새 OpenAI 클라이언트를 만들지 않고 캐시합니다.
- `.env` 로딩도 여기서 공용으로 맞춥니다.
- 단순하지만 모듈 전반의 중복 코드를 줄이는 역할이 큽니다.

리뷰 포인트:

- 현재는 OpenAI 전용 공용 유틸
- 다른 provider까지 확장하려면 추상화 레벨을 올릴 수 있음

발표용 설명:

> `openai_service.py`는 작지만 중요한 공통 유틸이고, OpenAI 클라이언트 재사용과 공용 설정 처리를 맡습니다.

---

### 16-9. `services/security_utils.py`

파일 역할:

- 예외 메시지나 로그 문자열에서 민감정보를 마스킹

핵심 함수:

- `redact_text()`
- `redact_exception()`

핵심 코드:

```python
for secret in _secret_env_values():
    if secret in redacted:
        redacted = redacted.replace(secret, _mask_secret(secret))
```

설명 포인트:

- 실제 환경 변수 값과 정규식 패턴을 둘 다 기준으로 마스킹합니다.
- 단순히 `OPENAI_API_KEY`만 가리는 것이 아니라 token, bearer, password까지 포괄합니다.

리뷰 포인트:

- 완벽한 보안 도구라기보다는 운영 로그 안전장치
- 그래도 이 정도 유틸이 없으면 장애 로그에서 실제 키가 노출될 수 있음

발표용 설명:

> `security_utils.py`는 운영 중 예외 로그에 민감값이 그대로 찍히는 문제를 막기 위한 안전장치입니다.

---

### 16-10. `services/agent_service.py`

파일 역할:

- 싱글톤 에이전트 접근 래퍼

핵심 코드:

```python
from ..agent import CSAgent, agent_instance

def get_agent() -> CSAgent:
    return agent_instance
```

설명 포인트:

- FastAPI 프로세스 전체에서 하나의 에이전트 상태를 공유하게 해줍니다.
- `llm_chat_api.py`와 `knowledge_service.py`가 같은 에이전트를 보도록 연결합니다.

리뷰 포인트:

- 단순하지만 공유 상태 구조를 명확하게 드러내는 역할
- 멀티프로세스 환경에서는 프로세스별 인스턴스가 생긴다는 점은 이해 필요

발표용 설명:

> `agent_service.py`는 별도 로직은 없지만, 전체 모듈이 같은 에이전트 인스턴스를 보게 만드는 연결 지점입니다.

---

## 17. 코드 리뷰할 때 추천 체크포인트

파일별로 볼 때 아래 질문을 같이 가져가면 좋습니다.

1. `agent.py`의 책임이 너무 크지 않은가
2. 지식 인덱싱 상태가 멀티프로세스/재시작 환경에서도 충분한가
3. 웹 검색 관련 캐시 만료 전략이 적절한가
4. 직접 응답 규칙이 늘어날 때 유지보수가 쉬운 구조인가
5. 미디어 API의 에러 응답 형식이 전체 API 스타일과 일관적인가
6. OpenAI 의존이 강한 부분을 provider abstraction으로 더 분리할 필요가 있는가

---

## 18. 최종 한 줄 정리

이 LLM 모듈의 고도화 핵심은 아래 한 문장으로 설명할 수 있습니다.
> 단순 LLM 호출이 아니라, 문서 검색, OCR, 최신 정보 보강, 세션 메모리, 미디어 기능, 폴백과 안정성을 포함한 운영형 AI 모듈로 확장한 것입니다.
