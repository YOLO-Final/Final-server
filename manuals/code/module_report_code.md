# REPORT Module (Code)

## 목적
결과 요약 조회와 PDF 보고서 생성을 담당합니다.

## 핵심 파일
- `server_api/src/modules/report/router.py`
- `server_api/src/modules/report/service.py`
- `server_api/src/modules/report/report.py`
- `server_api/src/modules/report/db/*`

## 라우트 prefix
- `/api/v1/report`

## 주요 엔드포인트
- `GET /status`
- `GET /result-summary`
- `GET /pdf`

## 수정 시 주의
- `target_date` 파라미터 포맷(`YYYY-MM-DD`) 유지
- PDF 생성 로직 변경 시 브라우저 inline 렌더 헤더 확인
