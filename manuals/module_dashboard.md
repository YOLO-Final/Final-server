# DASHBOARD 모듈 운영 가이드

## 1. 한 줄 설명

작업자/QA/관리자/공용송출 화면에 필요한 KPI와 데이터셋을 제공합니다.

## 2. API 기본 경로

- `/api/v1/dashboard`

## 3. 주요 기능

- 화면별 KPI 조회
- 화면별 데이터셋 조회
- 상세 패널 데이터 조회
- 웹 대시보드 통합 응답 제공

## 4. 주요 엔드포인트

- `GET /api/v1/dashboard/status`
- `GET /api/v1/dashboard/kpis?screen=worker|qa|manager|promo`
- `GET /api/v1/dashboard/datasets?screen=worker|qa|manager|promo`
- `GET /api/v1/dashboard/detail?screen=...&detailId=...`
- `GET /api/v1/dashboard/web/worker`
- `GET /api/v1/dashboard/web/qa`
- `GET /api/v1/dashboard/web/manager`
- `GET /api/v1/dashboard/web/promo`

## 5. 운영 점검 포인트

1. 모든 엔드포인트는 로그인 토큰이 필요
2. `screen` 값은 4종(worker/qa/manager/promo)만 허용
3. 값이 비면 DB 데이터 또는 필터 파라미터 확인

## 6. 자주 발생하는 문제

- 증상: 카드/차트가 빈 화면으로 표시
- 원인: 인증 토큰 누락 또는 DB 데이터 부족
- 조치: 로그인 재확인, `server_api` 로그 확인, 필터 초기화
