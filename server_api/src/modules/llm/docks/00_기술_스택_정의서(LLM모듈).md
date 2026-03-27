# 기술 스택 정의서 — LLM 모듈

> 경로: `server_api/src/modules/llm/`
> 기준: `server_api/requirements.txt` 실 설치 패키지 기준
> 작성일: 2026-03-23

---

## 1. 개요

| 항목 | 내용 |
|------|------|
| 모듈명 | LLM Integration Module |
| 경로 | `server_api/src/modules/llm/` |
| 주요 역할 | AI 챗봇, 음성/이미지 처리, 지식베이스 검색, 웹 검색 통합 |
| 언어 | Python 3.x |
| 아키텍처 | FastAPI REST API + Server-Sent Events (SSE) 스트리밍 |

---

## 2. 웹 프레임워크

| 라이브러리 | 버전 | 용도 |
|-----------|------|------|
| fastapi | 0.116.1 | API 라우터, 엔드포인트 정의 |
| uvicorn | 0.35.0 | ASGI 서버 (standard extras 포함) |
| starlette | 0.47.3 | StreamingResponse (SSE 스트리밍 응답) |
| pydantic | 2.10.1 | 요청/응답 데이터 검증 |
| pydantic-settings | 2.10.1 | 환경변수 설정 관리 |
| python-multipart | 0.0.9 | 파일 업로드 (multipart/form-data) |

---

## 3. LLM 프로바이더

| 프로바이더 | 기본 모델 | 용도 | 환경변수 |
|-----------|----------|------|----------|
| **OpenAI** | `gpt-4o-mini` | 일반 채팅 응답 | `OPENAI_MODEL` |
| **OpenAI** | `gpt-4.1-mini` | 웹 검색 포함 응답 | `OPENAI_WEB_MODEL` |
| **OpenAI** | `gpt-4o-mini-transcribe` | STT (음성 → 텍스트) | `OPENAI_STT_MODEL` |
| **OpenAI** | `gpt-4o-mini-tts` | TTS (텍스트 → 음성) | `OPENAI_TTS_MODEL` |
| **OpenAI** | `gpt-image-1` | 이미지 생성 | `OPENAI_IMAGE_MODEL` |
| **OpenAI** | `gpt-4.1-mini` | 이미지 OCR (Vision API) | `OPENAI_VISION_MODEL` |
| **Google Gemini** | `gemini-2.0-flash` | 대체 LLM 프로바이더 | `GEMINI_MODEL` |
| **vLLM** | 커스텀 | 자체 호스팅 LLM | `VLLM_MODEL` |

> 런타임 전환: API 요청의 `provider` 파라미터로 `openai` 선택

---

## 4. AI / LLM 프레임워크

| 라이브러리 | 버전 | 용도 |
|-----------|------|------|
| openai | 1.68.2 | OpenAI 공식 Python SDK |
| langchain | 0.3.27 | LLM 체인, 문서 로딩, 검색 통합 |
| langchain-core | 0.3.83 | LangChain 핵심 추상화 |
| langchain-community | 0.3.21 | FAISS 벡터 스토어 통합 |
| langchain-openai | 0.3.11 | OpenAI Embeddings + LangChain 연동 |
| langchain-text-splitters | 0.3.11 | 문서 청킹 (`RecursiveCharacterTextSplitter`) |

---

## 5. 벡터 검색 (RAG)

| 기술 | 버전 | 용도 |
|------|------|------|
| faiss-cpu | 1.8.0 | 벡터 유사도 검색 (Dense Retrieval) |
| OpenAI Embeddings | - | 텍스트 벡터화 (`text-embedding-3-small`) |
| Token Overlap 검색 | - | FAISS 불가 시 폴백 — 키워드 기반 희소 검색 (Sparse Retrieval) |

### 검색 전략 (Hybrid RAG)

```
1. Dense Retrieval  → FAISS 벡터 유사도
2. Sparse Retrieval → 토큰 오버랩 스코어링 (한국어/영어 모두 지원)
3. 결과 병합       → 중복 제거 + 관련도 순 정렬
```

### 문서 청킹 설정

| 설정 | 값 |
|------|----|
| 청크 크기 | 900 tokens |
| 오버랩 | 120 tokens |
| 분할기 | `RecursiveCharacterTextSplitter` |

---

## 6. 웹 검색 통합

| 프로바이더 | 호출 방식 | 환경변수 |
|-----------|----------|----------|
| **Serper** (`google.serper.dev`) | httpx 비동기 | `SERPER_API_KEY` |
| **Tavily** (`api.tavily.com`) | httpx 비동기 | `TAVILY_API_KEY` |
| **OpenAI Web Search** | SDK 내장 | `OPENAI_API_KEY` |

> 폴백 순서: Serper 뉴스 → Serper 텍스트 → Tavily → OpenAI Web

---

## 7. 문서 처리 / OCR

### PDF

| 기술 | 버전 | 우선순위 | 비고 |
|------|------|---------|------|
| pypdf | 5.4.0 | 1순위 | 설치됨 |
| PyPDF2 | - | 코드 폴백 | 미설치 (코드에서 동적 임포트 시도) |
| Tesseract OCR (pytesseract) | 0.3.13 | 2순위 폴백 | 스캔 PDF 처리 |
| Sidecar `.txt` / `_ocr.txt` | - | 최종 폴백 | 미리 추출된 텍스트 |

### 이미지

| 기술 | 버전 | 우선순위 | 비고 |
|------|------|---------|------|
| OpenAI Vision API (`gpt-4.1-mini`) | - | 1순위 | `OPENAI_VISION_MODEL` |
| pytesseract | 0.3.13 | 2순위 폴백 | 로컬 Tesseract |
| Sidecar 텍스트 파일 | - | 최종 폴백 | |

### 이미지 처리 보조

| 라이브러리 | 버전 | 용도 |
|-----------|------|------|
| opencv-python-headless | 4.10.0.84 | 이미지 전처리 |
| Pillow | 12.1.1 | 이미지 처리 (transitive dependency) |

---

## 8. 지원 파일 형식

| 구분 | 형식 |
|------|------|
| 문서 (지식베이스) | `.txt`, `.pdf` |
| 이미지 (OCR 업로드) | `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.gif` |
| 음성 입력 (STT) | `.wav`, `.mp3`, `.m4a`, `.webm`, `.mp4`, `.mpeg`, `.mpga`, `.ogg` |
| 음성 출력 (TTS) | `.mp3`, `.wav`, `.opus`, `.flac`, `.aac`, `.pcm` |

---

## 9. 캐싱 전략

| 캐시 계층 | 구현 | 대상 |
|----------|------|------|
| 웹 검색 캐시 | `OrderedDict` + TTL 기반 만료 | 동일 쿼리 중복 검색 방지 |
| LLM 응답 캐시 | `OrderedDict` + TTL 기반 만료 | 동일 프롬프트 결과 재사용 |
| OpenAI 클라이언트 | `functools.lru_cache(maxsize=1)` | 클라이언트 싱글톤 |
| 지식베이스 핑거프린트 | `mtime + size` 해시 | 변경 없으면 재색인 생략 |

---

## 10. 세션 / 메모리 관리

| 항목 | 구현 |
|------|------|
| 세션 저장소 | Python `dict` (`_session_state[session_id]`) |
| 히스토리 방식 | 롤링 윈도우 (최근 N턴 유지, 이전 턴 요약) |
| 동시성 | `threading.Lock` |
| 세션 ID 정규화 | 영숫자 + 대시/점, 최대 80자 |
| 튜닝 환경변수 | `HISTORY_MAX_TURNS`, `HISTORY_RECENT_TURNS` |

---

## 11. HTTP 클라이언트

| 라이브러리 | 버전 | 용도 |
|-----------|------|------|
| httpx | 0.28.1 | 비동기 HTTP 요청 (OpenAI SDK 내부, Serper/Tavily 직접 호출) |
| urllib.request | stdlib | Gemini REST API 직접 호출 (`llm_simple.py`) |

> `requests`, `aiohttp`는 main `requirements.txt` 미포함 (sample 디렉터리 전용)

---

## 12. 보안

| 항목 | 구현 | 라이브러리 |
|------|------|-----------|
| API 키 마스킹 | `security_utils.py` — `sk-`, `tvly-` 등 정규식 감지 후 `first4***last4` 처리 | `re` |
| 예외 메시지 sanitize | `redact_exception()` — 로그/응답에서 시크릿 자동 제거 | |
| JWT 인증/인가 | 토큰 디코드 + 버전 검증 | python-jose 3.3.0 |
| 비밀번호 해싱 | bcrypt | passlib 1.7.4 |
| 환경변수 관리 | `.env` 파일 로딩 | python-dotenv 1.0.1 |

---

## 13. API 엔드포인트 목록

| 메서드 | 경로 | 기능 | 파일 |
|--------|------|------|------|
| `POST` | `/llm/chat` | 스트리밍 AI 채팅 (SSE) | `llm_chat_api.py` |
| `GET` | `/llm/memory` | 세션 메모리 조회 | `llm_chat_api.py` |
| `POST` | `/llm/memory/reset` | 세션 초기화 | `llm_chat_api.py` |
| `GET` | `/llm/knowledge` | 지식베이스 상태 조회 | `llm_chat_api.py` |
| `GET` | `/llm/knowledge/files` | 색인된 파일 목록 | `llm_chat_api.py` |
| `POST` | `/llm/knowledge/reindex` | 강제 재색인 | `llm_chat_api.py` |
| `POST` | `/llm/upload` | 지식베이스 파일 업로드 | `llm_chat_api.py` |
| `GET` | `/llm/recommended-questions` | 추천 질문 목록 | `llm_question.py` |
| `POST` | `/llm/stt` | 음성 → 텍스트 | `llm_media_api.py` |
| `POST` | `/llm/tts` | 텍스트 → 음성 스트리밍 | `llm_media_api.py` |
| `POST` | `/llm/image` | 이미지 생성 | `llm_media_api.py` |
| `POST` | `/llm/result` | 단순 프롬프트 실행 | `llm_result_api.py` |

---

## 14. 환경변수 전체 목록

| 분류 | 변수명 | 설명 | 기본값 |
|------|--------|------|--------|
| **API 키** | `OPENAI_API_KEY` | OpenAI 인증 키 | 필수 |
| | `GOOGLE_API_KEY` | Google Gemini 인증 키 | |
| | `SERPER_API_KEY` | Serper 웹 검색 키 | |
| | `TAVILY_API_KEY` | Tavily 웹 검색 키 | |
| **모델** | `OPENAI_MODEL` | 기본 채팅 모델 | `gpt-4o-mini` |
| | `OPENAI_WEB_MODEL` | 웹 검색용 모델 | `gpt-4.1-mini` |
| | `GEMINI_MODEL` | Gemini 모델명 | `gemini-2.0-flash` |
| | `EMBEDDING_MODEL` | 임베딩 모델 | `text-embedding-3-small` |
| | `OPENAI_VISION_MODEL` | OCR Vision 모델 | `gpt-4.1-mini` |
| | `OPENAI_STT_MODEL` | STT 모델 | `gpt-4o-mini-transcribe` |
| | `OPENAI_TTS_MODEL` | TTS 모델 | `gpt-4o-mini-tts` |
| | `OPENAI_IMAGE_MODEL` | 이미지 생성 모델 | `gpt-image-1` |
| **지식베이스** | `LLM_KNOWLEDGE_PATH` | 지식 문서 디렉터리 경로 | `./knowledge_base/` |
| **히스토리** | `HISTORY_MAX_TURNS` | 최대 히스토리 턴 수 | |
| | `HISTORY_RECENT_TURNS` | 최근 유지 턴 수 | |
| **캐시** | `WEB_CACHE_TTL_SEC` | 웹 검색 캐시 TTL (초) | |
| | `WEB_MAX_RESULTS` | 웹 검색 최대 결과 수 | |
| **미디어** | `MAX_AUDIO_BYTES` | 최대 오디오 크기 | 20 MB |
| | `MIN_AUDIO_BYTES` | 최소 오디오 크기 | 1.5 KB |
| **OCR** | `TESSERACT_CMD` | Tesseract 실행 파일 경로 | |
| | `TESSDATA_PREFIX` | Tesseract 데이터 디렉터리 | |
| | `LOCAL_OCR_LANG` | OCR 인식 언어 | |

---

## 15. 모듈 파일 구조

```
modules/llm/
├── __init__.py                  # 패키지 공개 API 정의
├── router.py                    # 메인 라우터 (prefix="/llm")
├── agent.py                     # CSAgent 클래스 — 핵심 AI 로직 (~2267 lines)
├── llm_simple.py                # Gemini REST 직접 호출 헬퍼
├── llm_chat_api.py              # 채팅 + 지식베이스 관리 엔드포인트
├── llm_question.py              # 추천 질문 생성 엔드포인트
├── llm_result_api.py            # 단순 프롬프트 엔드포인트
├── llm_media_api.py             # STT / TTS / 이미지 생성 엔드포인트
├── .env.example                 # 환경변수 템플릿
├── knowledge_base/              # 사용자 지식 문서 저장소
└── services/
    ├── agent_service.py         # CSAgent 싱글톤 접근자
    ├── openai_service.py        # OpenAI 클라이언트 관리
    ├── knowledge_service.py     # 지식베이스 색인 로직 (~546 lines)
    └── security_utils.py        # API 키 마스킹 유틸리티
```

---

## 16. 시스템 아키텍처 요약

```
[FastAPI Router /llm]
    │
    ├── /chat ──────────► CSAgent.get_ai_streaming_response()
    │                          ├── 세션 히스토리 로드
    │                          ├── 지식베이스 검색 (FAISS → Token Overlap)
    │                          ├── 웹 검색 (Serper → Tavily → OpenAI Web)
    │                          └── LLM 호출 (OpenAI / Gemini / vLLM)
    │                                └── SSE 청크 스트리밍 응답
    │
    ├── /stt ───────────► OpenAI Whisper API (gpt-4o-mini-transcribe)
    ├── /tts ───────────► OpenAI TTS API → StreamingResponse
    ├── /image ─────────► gpt-image-1 → (fallback) DALL-E 3
    │
    └── /upload ────────► knowledge_service.update_knowledge()
                               ├── PDF: pypdf → (fallback) Tesseract → sidecar .txt
                               ├── Image: OpenAI Vision → Tesseract → sidecar .txt
                               └── FAISS 인덱스 재생성
```

---

## 17. 핵심 설계 패턴

| 패턴 | 적용 위치 | 내용 |
|------|----------|------|
| **Singleton** | `CSAgent`, `OpenAI Client` | FastAPI 프로세스 내 단일 인스턴스 |
| **Fallback Chain** | OCR, 웹 검색, 추천 질문 | 상위 수단 실패 시 자동 하위 수단으로 전환 |
| **Rolling Window** | 세션 히스토리 | 최근 N턴 유지, 이전 기록 요약 압축 |
| **Fingerprint Cache** | 지식베이스 색인 | 파일 변경 없으면 재색인 생략 |
| **Intent Classification** | Query Router | 토큰 목록 + 정규식으로 웹 검색 필요 여부 자동 판단 |

---

*본 문서는 `server_api/requirements.txt` 실 설치 패키지를 기준으로 작성되었습니다.*
