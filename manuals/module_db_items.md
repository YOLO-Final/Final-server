# DB ITEMS 모듈 운영 가이드

## 1. 한 줄 설명

샘플 Item 데이터에 대한 기본 CRUD API(생성/조회/수정/삭제)를 제공합니다.

## 2. API 기본 경로

- `/api/v1/items`

## 3. 주요 기능

- 아이템 생성
- 아이템 목록 조회
- 단건 조회
- 수정
- 삭제

## 4. 주요 엔드포인트

- `POST /api/v1/items`
- `GET /api/v1/items`
- `GET /api/v1/items/{item_id}`
- `PUT /api/v1/items/{item_id}`
- `DELETE /api/v1/items/{item_id}`

## 5. 운영 점검 포인트

1. 404는 존재하지 않는 item_id일 가능성이 큼
2. 목록 조회 파라미터 `skip`, `limit`로 페이징 가능
3. 입력 형식 오류 시 요청 JSON 구조 확인

## 6. 자주 발생하는 문제

- 증상: 수정/삭제 시 404
- 원인: 이미 삭제됐거나 잘못된 ID
- 조치: 목록 조회로 ID 재확인 후 재요청
