# API_ERROR_RESPONSE_SPEC

이 문서는 `web_dashboard` 백엔드에서 사용할 **에러 응답 형식**을 정리한 문서입니다.  
DB 연결 여부와 상관없이, 프론트가 일관되게 해석할 수 있도록 상태코드와 메시지 규칙을 먼저 고정하는 목적입니다.

대상 경로:

- `GET /api/v1/dashboard/web/worker`
- `GET /api/v1/dashboard/web/qa`
- `GET /api/v1/dashboard/web/manager`
- `GET /api/v1/dashboard/web/promo`

## 1. 기본 원칙

권장 원칙:

1. 상태코드는 HTTP 의미와 맞게 사용
2. 프론트 표시용 메시지는 짧고 명확하게 유지
3. 내부 예외 문자열을 그대로 노출하지 않음
4. 같은 종류의 에러는 같은 형식으로 응답

권장 형식:

```json
{
  "ok": false,
  "error": {
    "code": "DASHBOARD_UNAVAILABLE",
    "message": "대시보드 데이터를 불러오지 못했습니다."
  }
}
```

## 2. 상태코드별 권장 응답

### `200 OK`

- 정상 응답
- `meta`, `kpis` 포함 bundle 반환

### `401 Unauthorized`

의미:

- 로그인 토큰 없음
- access token 만료
- refresh 실패 후 재인증 필요

권장 응답:

```json
{
  "ok": false,
  "error": {
    "code": "UNAUTHORIZED",
    "message": "로그인이 필요합니다."
  }
}
```

현재 프로젝트 계열 메시지:

- `인증이 만료되었습니다. 다시 로그인해주세요.`
- `유효하지 않은 인증 정보입니다. 다시 로그인해주세요.`

### `403 Forbidden`

의미:

- 로그인은 되었지만 접근 권한 부족
- 비활성화 계정
- 잠긴 계정

권장 응답:

```json
{
  "ok": false,
  "error": {
    "code": "FORBIDDEN",
    "message": "해당 화면에 접근할 권한이 없습니다."
  }
}
```

### `404 Not Found`

의미:

- 라우트 경로 불일치
- 프론트 endpointMap 오타
- 배포/반영 누락

권장 응답:

```json
{
  "ok": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "요청한 대시보드 경로를 찾을 수 없습니다."
  }
}
```

### `422 Unprocessable Entity`

의미:

- query parameter validation 실패
- 타입 불일치
- 허용되지 않은 값 입력

권장 응답:

```json
{
  "ok": false,
  "error": {
    "code": "INVALID_REQUEST",
    "message": "요청 파라미터를 확인해주세요."
  }
}
```

### `500 Internal Server Error`

의미:

- `service.py` 내부 집계/조립 실패
- import 오류
- 응답 키 누락
- 예기치 않은 런타임 예외

권장 응답:

```json
{
  "ok": false,
  "error": {
    "code": "DASHBOARD_UNAVAILABLE",
    "message": "대시보드 데이터를 불러오지 못했습니다."
  }
}
```

## 3. 상태코드별 프론트 기대 동작

- `200`: 정상 렌더
- `401`: refresh 시도 후 실패 시 로그인 화면 이동
- `403`: 권한 문제 메시지 또는 로그인 화면 복귀
- `404`: 배포/라우트 문제로 인식
- `422`: 프론트 요청값 점검
- `500`: 서버 내부 에러, fallback 또는 오류 안내

## 4. 권장 error.code 목록

- `UNAUTHORIZED`
- `FORBIDDEN`
- `NOT_FOUND`
- `INVALID_REQUEST`
- `DASHBOARD_UNAVAILABLE`

확장 가능:

- `TOKEN_EXPIRED`
- `ACCOUNT_LOCKED`
- `ACCOUNT_INACTIVE`

## 5. 현재 프로젝트에 바로 적용 가능한 최소 기준

지금 바로 적용할 최소 기준:

1. `401 / 403 / 404 / 422 / 500` 의미를 문서 기준으로 고정
2. 에러 메시지는 한국어 짧은 문장 유지
3. 내부 예외 원문 노출 금지
4. 인증 실패는 로그인 복귀 기준 유지

## 6. 한 줄 요약

`web_dashboard` 백엔드는 **상태코드의 의미를 고정하고, 짧고 일관된 한국어 메시지 + 선택적 error.code 구조**로 가는 것이 가장 안정적입니다.

