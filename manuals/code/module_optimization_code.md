# OPTIMIZATION Module (Code)

## 목적
최적화 기능의 API 스켈레톤을 제공합니다.

## 핵심 파일
- `server_api/src/modules/optimization/router.py`
- `server_api/src/modules/optimization/service.py`
- `server_api/src/modules/optimization/db/schema.py`

## 라우트 prefix
- `/api/v1/optimization`

## 현재 구현
- `GET /status` placeholder

## 확장 가이드
- 계산형 API 추가 시 request schema와 response schema를 먼저 고정
- 장시간 작업은 비동기 작업 큐(예: Celery/RQ) 검토
