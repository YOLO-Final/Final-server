# DB ITEMS Module (Code)

## 목적
샘플 CRUD 패턴을 제공하는 기준 모듈입니다.

## 핵심 파일
- `server_api/src/modules/db/items/router.py`
- `server_api/src/modules/db/items/db/crud.py`
- `server_api/src/modules/db/items/db/model.py`
- `server_api/src/modules/db/items/db/schema.py`

## 라우트 prefix
- `/api/v1/items`

## 주요 흐름
1. router에서 입력 수신
2. CRUD 함수 호출
3. schema(response_model)로 직렬화

## 수정 시 주의
- 404 처리 패턴 유지 (`Item not found`)
- 페이지네이션 파라미터(`skip`, `limit`) 하위 호환 유지
