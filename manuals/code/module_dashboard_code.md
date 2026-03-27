# DASHBOARD Module (Code)

## 목적
역할별 화면(worker/qa/manager/promo)에 필요한 KPI/데이터셋/상세 데이터를 제공합니다.

## 핵심 파일
- `server_api/src/modules/dashboard/router.py`
- `server_api/src/modules/dashboard/service.py`
- `server_api/src/modules/dashboard/repository.py`
- `server_api/src/modules/dashboard/schemas.py`

## 라우트 prefix
- `/api/v1/dashboard`

## 주요 흐름
1. router에서 screen/filter 파라미터 검증
2. service에서 live snapshot 조회 + mock fallback 병합
3. response schema로 직렬화 반환

## 핵심 설계 포인트
- live 데이터 불완전 시 하이브리드 응답 지원
- `detailId` + `targetType` + `targetId` 조합으로 상세 패널 응답
- screen별 필수 dataset/kpi 키 정의 후 누락 여부 계산

## 수정 시 주의
- screen 값 정규식(4종) 유지
- 프런트에서 기대하는 key 이름 변경 금지
- mock/live 병합 로직 수정 시 `detail` 응답과 동기화 필요
