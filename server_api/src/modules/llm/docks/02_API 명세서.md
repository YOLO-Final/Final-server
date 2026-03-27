# LLM 모듈 API 명세서

> **Base URL:** `/api/v1/llm`
> **작성일:** 2026-03-23 | **버전:** v1.0
> **응답 기본 형식:** `application/json` (스트리밍 제외)

---

## 전체 구조 한눈에 보기

```
클라이언트
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│                   /api/v1/llm                           │
│                                                         │
│  💬 채팅           🗂️ 지식베이스        🎙️ 미디어         │
│  POST /chat        GET  /knowledge     POST /stt        │
│  GET  /memory      GET  /knowledge/    POST /tts        │
│  POST /memory/     files               POST /image      │
│       reset        POST /knowledge/                     │
│                    reindex             🔧 유틸           │
│                    POST /upload        POST /result     │
│                    GET  /health/web    GET  /recommended│
│                                            -questions   │
└─────────────────────────────────────────────────────────┘
```

---

## 채팅 흐름 이해하기

`POST /chat` 을 호출하면 내부적으로 아래 순서로 처리됩니다.

```
사용자 메시지
      │
      ▼
 ① 빠른 우회 응답 가능?
   ├─ OCR 텍스트 요청 → OCR 결과 그대로 반환
   ├─ 회사 정보 질문  → 지식베이스 직접 반환
   └─ 단순 보드 정보  → 지식베이스 직접 반환
      │ (우회 불가 시 계속)
      ▼
 ② 최신 정보가 필요한 질문인가?
   ├─ "현재", "지금", "최신", 연도 포함 등 → 웹 검색 자동 활성화
   └─ 일반 질문 → 지식베이스만 사용
      │
      ▼
 ③ 컨텍스트 수집 (병렬 처리)
   ├─ 지식베이스 검색 (벡터 + 키워드)
   ├─ 웹 검색 (Serper → Tavily → OpenAI 순 폴백)
   └─ 세션 대화 히스토리
      │
      ▼
 ④ 프롬프트 구성 → LLM 호출 → 스트리밍 응답
      │
      ▼
 ⑤ 출처 인용 첨부 (웹 검색 사용 시)
```

---

## 웹 검색 폴백 체인

웹 검색이 필요할 때, 아래 순서로 시도합니다. 앞 단계가 실패해야 다음 단계로 넘어갑니다.

```
1순위: Serper API  ──────── 빠름, 외부 검색엔진
    실패 시 ↓
2순위: Tavily API  ──────── 보통, 심층 검색 특화
    실패 시 ↓
3순위: OpenAI Responses API ── 느리지만 안정적
```

> **참고:** `GET /health/web` 엔드포인트는 **3순위(OpenAI)만** 테스트합니다.
> Serper/Tavily 상태는 별도로 확인해야 합니다.

---

## OCR 처리 체인

이미지나 PDF를 지식베이스에 추가할 때, 텍스트 추출 순서입니다.

```
1단계: OpenAI Vision (gpt-4.1-mini) ──── 가장 정확
    실패 시 ↓
2단계: 사이드카 .txt 파일 찾기
       (같은 폴더의 filename.txt / filename_ocr.txt / filename.ocr.txt)
    없을 시 ↓
3단계: 로컬 Tesseract OCR ──── 서버에 설치된 경우만
    없을 시 ↓
4단계: 플레이스홀더 텍스트 (인덱싱 실패로 기록)
```

---

## 엔드포인트 상세

---

### 1. 채팅 API

#### `POST /chat`

AI와 대화합니다. 응답은 텍스트가 생성되는 즉시 스트리밍으로 전달됩니다.

**Content-Type:** `multipart/form-data`

**요청 파라미터**

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `message` | string | `""` | 사용자 메시지 |
| `session_id` | string | `"default"` | 대화 세션 ID (사용자별로 구분) |
| `provider` | string | `"openai"` | AI 모델 선택: `openai`|
| `language` | string | `"ko"` | 응답 언어: `ko`(한국어) / `en`(영어) |
| `empathy_level` | string | `"balanced"` | 응답 말투: `low`(간결) / `balanced`(보통) / `high`(공감적) |
| `web_search` | string | `"false"` | 웹 검색 강제 활성화: `"true"` / `"false"` |
| `disable_auto_web` | string | `"false"` | 자동 웹 검색 비활성화: `"true"` / `"false"` |
| `reset_memory` | string | `"false"` | 이 요청 전에 대화 기록 초기화: `"true"` / `"false"` |

**응답**

| 항목 | 내용 |
|---|---|
| Content-Type | `text/plain; charset=utf-8` |
| 형식 | 텍스트 스트리밍 (SSE 방식, 토큰 단위로 전달) |
| 헤더 | `Cache-Control: no-cache`, `X-Accel-Buffering: no` |

스트리밍 도중 오류 발생 시:
```
응답 생성 중 오류가 발생했습니다: {오류 내용}
```

**예시 요청**
```bash
curl -X POST http://localhost/api/v1/llm/chat \
  -F "message=현재 설비 불량률은?" \
  -F "session_id=operator_01" \
  -F "language=ko"
```

> **`web_search` vs `disable_auto_web` 차이**
>
> | 상황 | web_search | disable_auto_web | 결과 |
> |---|---|---|---|
> | 자동 판단에 맡김 | false | false | 최신성 키워드 있으면 자동 웹 검색 |
> | 무조건 웹 검색 | true | false | 항상 웹 검색 |
> | 웹 검색 완전 금지 | false | true | 지식베이스만 사용 |

---

### 2. 메모리 관리 API

#### `GET /memory`

세션의 대화 기록을 조회합니다.

**Query Parameter:** `session_id` (기본값: `"default"`)

**응답 예시 (200 OK)**
```json
{
  "session_id": "operator_01",
  "chat_turns": 5,
  "message_count": 10,
  "memory_summary": "사용자는 PCB 불량 원인에 대해 질문하였으며...",
  "recent_messages": [
    { "role": "user", "content": "최근 불량률은?" },
    { "role": "assistant", "content": "최근 불량률은 2.3%입니다." }
  ],
  "knowledge_memory": [
    { "query": "PCB 불량 원인", "context": "..." }
  ],
  "web_history": [
    { "query": "PCB 시장 동향", "url": "https://...", "snippet": "..." }
  ]
}
```

> **응답 데이터 제한사항**
> - `recent_messages`: 최근 **6개** 메시지만 반환 (전체 히스토리 아님)
> - `knowledge_memory`: 최근 **4개**
> - `web_history`: 최근 **4개**

---

#### `POST /memory/reset`

세션 대화 기록을 초기화합니다.

**Content-Type:** `multipart/form-data`

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `session_id` | string | `"default"` | 초기화할 세션 ID |

**응답 예시 (200 OK)**
```json
{
  "message": "Memory was reset successfully.",
  "session_id": "operator_01"
}
```

---

### 3. 지식베이스 API

지식베이스는 서버 시작 시 자동으로 인덱싱됩니다. 이후 파일 업로드나 수동 재인덱싱으로 갱신할 수 있습니다.

```
서버 시작
    │
    ▼
지식베이스 폴더 감시
    │
    ├─ 파일 변경 없음 → 기존 인덱스 재사용
    └─ 파일 추가/변경 → 자동 재인덱싱
          │
          ▼
       벡터 DB (FAISS) 구축 완료 → 검색 준비
```

---

#### `GET /knowledge`

지식베이스 인덱싱 상태를 조회합니다.

**응답 예시 (200 OK)**
```json
{
  "knowledge_path": "/app/knowledge_base",
  "files": ["pcb_defect.pdf", "manual.txt"],
  "indexed_chunks": 142,
  "vector_indexed_chunks": 142,
  "retriever_ready": true,
  "chunking": {
    "parsed_docs": 2,
    "chunked_docs": 142
  },
  "ocr": {
    "image_ocr_success": 3,
    "image_ocr_failed": 0,
    "local_ocr_used": 0,
    "sidecar_ocr_used": 0,
    "local_ocr_available": false,
    "local_ocr_reason": "tesseract not found",
    "tesseract_cmd": ""
  },
  "last_error": "",
  "status": "ok",
  "indexing": {
    "in_progress": false,
    "error": ""
  }
}
```

**`status` 필드 값**

| 값 | 의미 |
|---|---|
| `"ok"` | 벡터 검색 준비 완료 (정상) |
| `"fallback_only_or_embedding_unavailable"` | 벡터 검색 불가, 키워드 검색만 동작 |

---

#### `GET /knowledge/files`

지식베이스 파일 목록만 간단히 조회합니다.

**응답 예시 (200 OK)**
```json
{
  "knowledge_path": "/app/knowledge_base",
  "files": ["pcb_defect.pdf", "manual.txt"],
  "indexing": {
    "in_progress": false,
    "error": ""
  }
}
```

---

#### `POST /knowledge/reindex`

지식베이스를 수동으로 재인덱싱합니다. 인덱싱 완료 후 결과를 반환합니다.

**요청 Body:** 없음

**응답 예시 (200 OK)**
```json
{
  "status": "reindexed",
  "indexed_chunks": 142,
  "vector_indexed_chunks": 142,
  "files": ["pcb_defect.pdf", "manual.txt"],
  "ocr": {
    "image_ocr_success": 3,
    "image_ocr_failed": 0
  }
}
```

---

#### `POST /upload`

지식베이스에 파일을 업로드하고 즉시 인덱싱합니다.

**Content-Type:** `multipart/form-data`

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `file` | file | ✅ | 업로드할 파일 |

**지원 파일 형식**

| 유형 | 확장자 |
|---|---|
| 문서 | `.txt`, `.pdf` |
| 이미지 | `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.gif` |

> ⚠️ **파일 크기 제한 없음** (업로드 자체에는 제한 없으나 서버 메모리 고려 필요)

**응답 예시 (200 OK) - 성공**
```json
{
  "message": "Upload complete: pcb_defect.pdf (indexed chunks: 58)",
  "indexed_chunks": 58
}
```

**응답 예시 (200 OK) - 실패** ← HTTP 상태코드는 200이지만 에러 포함
```json
{
  "error": "TXT/PDF/Image files are supported (.txt, .pdf, .png, .jpg, .jpeg, .webp, .bmp, .gif)."
}
```

> **주의:** 업로드 실패 시에도 HTTP 상태코드는 **200**입니다.
> 응답 JSON의 `error` 필드 존재 여부로 성공/실패를 판단해야 합니다.

---

#### `GET /health/web`

웹 검색(OpenAI Responses API) 연결 상태를 진단합니다.

> **주의:** 이 엔드포인트는 3순위 폴백인 OpenAI Responses API만 테스트합니다.
> Serper API, Tavily API 상태는 이 엔드포인트로 확인할 수 없습니다.

**Query Parameter:** `probe_query` (기본값: `"current market data now"`)

**응답 예시 (200 OK)**
```json
{
  "probe_query": "current market data now",
  "openai_api_key_set": true,
  "openai_web_model": "gpt-4.1-mini",
  "openai_web_timeout_sec": 25,
  "openai_web_retries": 3,
  "web_fresh_source_mode": "relaxed",
  "direct_answer_ok": true,
  "direct_links_count": 3,
  "direct_links": ["https://..."],
  "elapsed_ms": 1234,
  "last_web_error": ""
}
```

> `direct_links`는 최대 **5개**까지 반환됩니다.

---

### 4. 미디어 API

#### `POST /stt` — 음성 → 텍스트

음성 파일을 텍스트로 변환합니다.

**Content-Type:** `multipart/form-data`

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `file` | file | (필수) | 음성 파일 |
| `provider` | string | `"openai"` | 현재 `openai`만 지원 |
| `language` | string | `""` | ISO 언어 코드 (예: `ko`, `en`). 비워두면 자동 감지 |
| `prompt` | string | `""` | 전사 정확도 향상을 위한 힌트 텍스트 |
| `translate_to_english` | string | `"false"` | `"true"` 설정 시 영어로 번역하여 반환 |

**지원 오디오 형식 및 제한**

| 항목 | 내용 |
|---|---|
| 지원 형식 | `.wav` `.mp3` `.m4a` `.webm` `.mp4` `.mpeg` `.mpga` `.ogg` |
| 최소 크기 | 1,500 bytes (약 1~2초 분량 미만 거부) |
| 최대 크기 | 20MB (환경변수 `MAX_AUDIO_BYTES`로 조정 가능) |
| 모델 | `gpt-4o-mini-transcribe` (환경변수 `OPENAI_STT_MODEL`로 변경 가능) |

**응답 예시 (200 OK) - 성공**
```json
{
  "text": "설비 시작 전 점검 순서를 알려주세요.",
  "error": "",
  "detected_language": "ko"
}
```

**응답 예시 (200 OK) - 실패** ← HTTP 상태코드는 항상 200
```json
{
  "text": "",
  "error": "The audio file is too short. Please try speaking for at least 1 to 2 seconds."
}
```

> **주의:** STT 실패 시에도 HTTP 상태코드는 **200**입니다.
> `error` 필드가 비어있는지로 성공/실패를 판단하세요.

---

#### `POST /tts` — 텍스트 → 음성

텍스트를 음성 파일로 변환합니다.

**Content-Type:** `multipart/form-data`

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `text` | string | (필수) | 음성으로 변환할 텍스트 |
| `provider` | string | `"openai"` | 현재 `openai`만 지원 |
| `voice` | string | `"alloy"` | 음성 종류: `alloy` / `echo` / `fable` / `onyx` / `nova` / `shimmer` |
| `audio_format` | string | `"mp3"` | 출력 형식: `mp3` / `wav` / `opus` / `flac` / `aac` / `pcm` |
| `speed` | string | `"1.0"` | 재생 속도: `0.25` ~ `4.0` (범위 초과 시 자동 보정) |

**응답 - 성공 (200 OK)**

| 항목 | 내용 |
|---|---|
| Content-Type | `audio/mpeg` (mp3) 또는 `audio/{format}` |
| 형식 | 바이너리 오디오 데이터 |

**응답 예시 - 실패 (200 OK)** ← HTTP 상태코드는 항상 200
```json
{
  "error": "Text is required for TTS."
}
```

> **모델:** `gpt-4o-mini-tts` (환경변수 `OPENAI_TTS_MODEL`로 변경 가능)

---

#### `POST /image` — 이미지 생성

텍스트 설명을 이미지로 생성합니다.

**Content-Type:** `multipart/form-data`

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `prompt` | string | (필수) | 생성할 이미지 설명 |
| `provider` | string | `"openai"` | 현재 `openai`만 지원 |
| `size` | string | `"1024x1024"` | 이미지 크기: `1024x1024` / `1024x1536` / `1536x1024` |

**응답 예시 - `gpt-image-1` 사용 시 (base64 반환)**
```json
{
  "error": "",
  "image_data_url": "data:image/png;base64,iVBORw0KGgo...",
  "model": "gpt-image-1"
}
```

**응답 예시 - `dall-e-3` 폴백 시 (URL 반환)**
```json
{
  "error": "",
  "image_url": "https://oaidalleapiprodscus.blob.core.windows.net/...",
  "model": "dall-e-3"
}
```

**응답 예시 - 실패**
```json
{
  "error": "Image generation failed."
}
```

> **중요:** `image_data_url`과 `image_url`은 **둘 중 하나만** 반환됩니다. 동시에 반환되지 않습니다.
>
> **모델 우선순위:** `gpt-image-1` → 실패 시 `dall-e-3` 폴백
>
> **DALL-E-3 폴백 특이사항:** `quality: standard`, `style: natural`, `n: 1` 자동 적용

---

### 5. 유틸리티 API

#### `POST /result`

단순 텍스트 생성 요청입니다. 스트리밍 없이 한 번에 결과를 반환합니다.

> **용도:** 채팅 에이전트 전체 파이프라인 대신, 단순 연동 테스트나 가벼운 1회성 호출에 사용합니다.

**Content-Type:** `application/json`

**요청 Body**
```json
{
  "prompt": "PCB 불량의 주요 원인을 요약해줘",
  "temperature": 0.3,
  "max_output_tokens": 256
}
```

| 필드 | 타입 | 기본값 | 범위 | 설명 |
|---|---|---|---|---|
| `prompt` | string | (필수) | 최소 1자 | 입력 텍스트 |
| `temperature` | float | `0.3` | `0.0` ~ `1.0` | 응답 다양성. 높을수록 창의적 |
| `max_output_tokens` | int | `256` | `32` ~ `2048` | 최대 출력 토큰 수 |

**응답 예시 (200 OK) - 성공**
```json
{
  "ok": true,
  "source": "openai",
  "text": "PCB 불량의 주요 원인은 납땜 불량, 부품 불량, 설계 오류입니다."
}
```

**응답 예시 (200 OK) - 실패**
```json
{
  "ok": false,
  "source": "fallback",
  "text": "",
  "message": "OpenAI API key is not set."
}
```

> **모델:** `gpt-4o-mini` 하드코딩 (환경변수로 변경 불가)

---

#### `GET /recommended-questions`

사용자에게 보여줄 추천 질문 목록을 반환합니다.

**Query Parameter**

| 파라미터 | 타입 | 기본값 | 범위 | 설명 |
|---|---|---|---|---|
| `lang` | string | `"ko"` | `ko` / `en` | 응답 언어 |
| `count` | int | `3` | `1` ~ `8` | 반환할 질문 수 |

**응답 예시 (200 OK) - AI 생성**
```json
{
  "items": [
    "현재 설비 불량률은 얼마인가요?",
    "NG 비율이 갑자기 높아졌을 때 원인은?",
    "제품 변경 시 바꿔야 하는 핵심 설정은?"
  ],
  "language": "ko",
  "source": "openai",
  "count": 3
}
```

**응답 예시 (200 OK) - 폴백 (AI 호출 실패 시)**
```json
{
  "items": [
    "설비 시작 전 점검 순서를 알려줘",
    "운전 중 오류가 나면 먼저 무엇을 확인해야 해?",
    "제품 변경 시 바꿔야 하는 핵심 설정은 뭐야?"
  ],
  "language": "ko",
  "source": "fallback",
  "count": 3
}
```

> **`source` 필드 의미**
> - `"openai"`: AI가 그때그때 동적으로 생성한 질문
> - `"fallback"`: AI 호출 실패로 미리 준비된 고정 질문 반환

> **폴백 질문 주제:** 설비 점검, 오류 대처, 제품 변경 설정, 카메라 인식 문제, NG 비율 원인 등 **공장 운영 도메인 특화** 질문으로 구성되어 있습니다.

---

## 공통 에러 응답 패턴

이 모듈의 대부분의 엔드포인트는 **HTTP 상태코드가 항상 200**이고, 에러 여부를 응답 JSON으로 구분합니다.

| 엔드포인트 | 에러 판별 방법 |
|---|---|
| `POST /chat` | 스트리밍 텍스트에 "오류가 발생했습니다" 포함 여부 |
| `POST /upload` | 응답에 `error` 필드 존재 여부 |
| `POST /stt` | `error` 필드가 비어있지 않은 경우 |
| `POST /tts` | 응답이 오디오 바이트가 아닌 JSON(`{"error": "..."}`) |
| `POST /image` | `error` 필드가 비어있지 않은 경우 |
| `POST /result` | `ok` 필드가 `false` |

---

## 지원 LLM 제공자

| `provider` 값 | 모델 | 특징 |
|---|---|---|
| `openai` | gpt-4o-mini | **기본값**, 안정적, 권장 |
| `gemini` | gemini-2.0-flash | Google Gemini |
| `vllm` | Qwen/Qwen2.5-7B-Instruct | 자체 호스팅 서버 |
| `vllm_fast` | Qwen/Qwen2.5-7B-Instruct | 자체 호스팅 (고속 옵션) |

> `provider`는 `POST /chat` 에서만 사용합니다.
> `/result`, `/stt`, `/tts`, `/image` 는 OpenAI 고정입니다.

---

## 환경변수 요약

| 변수명 | 기본값 | 설명 |
|---|---|---|
| `OPENAI_API_KEY` | — | OpenAI 인증키 (필수) |
| `SERPER_API_KEY` | — | 웹 검색 1순위 API 키 |
| `TAVILY_API_KEY` | — | 웹 검색 2순위 API 키 |
| `OPENAI_MODEL` | `gpt-4o-mini` | 채팅 모델 |
| `OPENAI_WEB_MODEL` | `gpt-4.1-mini` | 웹 검색 모델 |
| `OPENAI_STT_MODEL` | `gpt-4o-mini-transcribe` | STT 모델 |
| `OPENAI_TTS_MODEL` | `gpt-4o-mini-tts` | TTS 모델 |
| `OPENAI_IMAGE_MODEL` | `gpt-image-1` | 이미지 생성 모델 |
| `MAX_AUDIO_BYTES` | `20971520` (20MB) | STT 최대 파일 크기 |
| `MIN_AUDIO_BYTES` | `1500` | STT 최소 파일 크기 |
| `HISTORY_MAX_TURNS` | `8` | 세션 최대 대화 턴 수 |
| `WEB_CACHE_TTL_SEC` | `180` | 웹 검색 캐시 유지 시간(초) |
| `LLM_KNOWLEDGE_PATH` | `knowledge_base/` | 지식베이스 폴더 경로 |
