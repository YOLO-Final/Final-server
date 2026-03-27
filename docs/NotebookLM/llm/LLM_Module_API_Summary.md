# LLM Module API Summary

이 문서는 `/api/v1/llm` 기준으로 확인되는 LLM 모듈 API를 요약한 문서다. 목적은 엔드포인트를 전부 나열하는 것이 아니라, PM용 보고서 작성에 필요한 수준으로 `기능`, `입력/출력`, `운영 연계 여부`, `주의점`을 보수적으로 정리하는 것이다.

## 해석 기준
- `운영 연계됨`: `nginx/html/js/dashboard.js`에서 직접 호출 근거가 확인된 API
- `구현 존재, 운영 미확인`: 백엔드 구현은 확인되지만 현재 운영 UI 직접 호출 근거는 확인하지 못한 API
- `보조/관리`: 사용자 핵심 흐름보다 관리성 또는 부가 기능 성격이 강한 API

## API 요약

| 경로 | 메서드 | 기능 | 주요 입력 | 주요 출력 | 운영 상태 | 비고 |
| --- | --- | --- | --- | --- | --- | --- |
| `/api/v1/llm/chat` | POST | 질문에 대한 스트리밍 답변 생성 | `message`, `provider`, `web_search`, `reset_memory`, `empathy_level`, `session_id` | text/plain 스트리밍 응답 | 운영 연계됨 | 핵심 질문 처리 API |
| `/api/v1/llm/memory` | GET | 세션 메모리 상태 조회 | `session_id` | 세션 메모리 스냅샷 JSON | 구현 존재, 운영 미확인 | 개발/관리 확인용 성격 |
| `/api/v1/llm/memory/reset` | POST | 세션 메모리 초기화 | `session_id` | reset 결과 JSON | 구현 존재, 운영 미확인 | 샘플 UI에서는 사용 흔적이 있으나 운영 `dashboard.js` 직접 호출은 미확인 |
| `/api/v1/llm/knowledge` | GET | 지식 상태 조회 | 없음 | 경로, 파일, indexed_chunks, status | 구현 존재, 운영 미확인 | 관리성 API |
| `/api/v1/llm/knowledge/files` | GET | 지식 파일 목록 조회 | 없음 | 경로, 파일 목록 | 구현 존재, 운영 미확인 | 관리성 API |
| `/api/v1/llm/knowledge/reindex` | POST | 지식 재색인 | 없음 | 경로, 파일 목록, indexed_chunks, status | 구현 존재, 운영 미확인 | 관리성 API |
| `/api/v1/llm/upload` | POST | 지식 파일 업로드 후 인덱싱 | `file` | 업로드 결과, indexed_chunks | 구현 존재, 운영 미확인 | TXT/PDF/Image 허용 |
| `/api/v1/llm/health/web` | GET | 웹 검색 진단 | `probe_query` | 웹 검색 진단 JSON | 구현 존재, 운영 미확인 | 점검용 성격 |
| `/api/v1/llm/stt` | POST | 음성 -> 텍스트 변환 | `file`, `provider`, `language`, `prompt`, `translate_to_english` | `text`, `error`, `detected_language` | 운영 연계됨 | OpenAI provider 중심 |
| `/api/v1/llm/tts` | POST | 텍스트 -> 음성 변환 | `text`, `provider`, `voice`, `audio_format`, `speed` | audio stream 또는 error JSON | 운영 연계됨 | OpenAI provider 중심 |
| `/api/v1/llm/image` | POST | 이미지 생성 | `prompt`, `provider`, `size` | image URL 또는 base64 data URL | 구현 존재, 운영 미확인 | OpenAI provider 중심 |
| `/api/v1/llm/recommended-questions` | GET | 추천 질문 반환 | `lang`, `count` | `items`, `language`, `source`, `count` | 운영 연계됨 | OpenAI 실패 시 fallback 질문 가능 |
| `/api/v1/llm/result` | POST | 단일 프롬프트 결과 생성 | `prompt`, `temperature`, `max_output_tokens` | `ok`, `source`, `text`, `message` | 구현 존재, 운영 미확인 | 핵심 운영 흐름보다는 보조 API 성격 |

## 운영 UI와 직접 연결이 확인된 API
- `/api/v1/llm/chat`
- `/api/v1/llm/stt`
- `/api/v1/llm/tts`
- `/api/v1/llm/recommended-questions`

위 네 개는 `nginx/html/js/dashboard.js`에서 직접 호출이 확인된다.

## 현재 운영 UI 직접 호출이 확인되지 않은 API
- `/api/v1/llm/memory`
- `/api/v1/llm/memory/reset`
- `/api/v1/llm/knowledge`
- `/api/v1/llm/knowledge/files`
- `/api/v1/llm/knowledge/reindex`
- `/api/v1/llm/upload`
- `/api/v1/llm/health/web`
- `/api/v1/llm/image`
- `/api/v1/llm/result`

이 API들은 `미구현`이 아니라 `구현 존재, 운영 미확인`으로 보는 것이 맞다.

## API 해석 시 주의점
- `chat`은 스트리밍 텍스트 응답이므로 일반 JSON 응답 API처럼 설명하면 안 된다.
- `stt`, `tts`, `image`는 OpenAI provider 중심으로 보이며, provider 다중 운영을 단정하면 안 된다.
- `upload`와 `knowledge/reindex`는 관리성 API일 가능성이 높으므로, 사용자 핵심 기능과 분리해 서술하는 것이 적절하다.
- `recommended-questions`는 핵심 챗봇 처리보다 UX 보조 기능으로 보는 것이 안전하다.
- `result`는 별도 단일 프롬프트 API지만 현재 운영 핵심 흐름으로 확인되지는 않았다.
