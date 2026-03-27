# RAG Module (Code)

## 목적
RAG 관련 상태/확장 포인트 제공 모듈입니다.

## 핵심 파일
- `server_api/src/modules/rag/router.py`
- `server_api/src/modules/rag/service.py`
- `server_api/src/modules/rag/db/*`

## 라우트 prefix
- `/api/v1/rag`

## 현재 구현
- `GET /status` 중심의 placeholder 구조

## 확장 가이드
- 벡터 인덱스 조회 API 추가 시 router/service 분리 유지
- LLM 모듈과 결합 시 응답 스키마 고정 후 의존성 최소화 권장
