# REPORT 모듈 운영 가이드

## 1. 한 줄 설명

검사/생산 결과 요약을 조회하고 PDF 보고서를 생성합니다.

## 2. API 기본 경로

- `/api/v1/report`

## 3. 주요 기능

- 모듈 상태 확인
- 일자 기준 결과 요약 조회
- PDF 보고서 다운로드/미리보기

## 4. 주요 엔드포인트

- `GET /api/v1/report/status`
- `GET /api/v1/report/result-summary?target_date=YYYY-MM-DD`
- `GET /api/v1/report/pdf?target_date=YYYY-MM-DD`

## 5. 운영 점검 포인트

1. `result-summary`가 먼저 정상인지 확인
2. 날짜 파라미터 형식은 `YYYY-MM-DD`
3. PDF가 비어 있으면 해당 날짜 원천 데이터 확인

## 6. 자주 발생하는 문제

- 증상: PDF가 열리지만 내용이 비어 있음
- 원인: 기준일 데이터 부재
- 조치: 날짜 변경 후 재조회, DB 적재 여부 확인
