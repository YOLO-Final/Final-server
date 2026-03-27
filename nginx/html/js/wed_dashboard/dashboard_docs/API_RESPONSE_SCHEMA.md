# API_RESPONSE_SCHEMA

이 문서는 현재 `web_dashboard`의 **live 응답 계약 기준 문서**입니다.  
공식 OpenAPI 전체 대체 문서는 아니지만, 실제 프론트와 백엔드가 합의한 top-level 구조와 핵심 필드를 정리합니다.

## 1. 엔드포인트

| 탭 | 엔드포인트 |
| --- | --- |
| `worker` | `/api/v1/dashboard/web/worker` |
| `qa` | `/api/v1/dashboard/web/qa` |
| `manager` | `/api/v1/dashboard/web/manager` |
| `promo` | `/api/v1/dashboard/web/promo` |

지원 query:

- `factory`
- `line`
- `shift`
- `period`
- `tz`
- `date_from`
- `date_to`

## 2. 공통 응답 원칙

- 응답은 현재 **직접 번들 반환** 형태를 기준으로 본다
- `meta`, `kpis`는 항상 존재해야 한다
- 숫자는 가능하면 숫자 타입 유지
- 값이 없더라도 기존 키는 가능한 한 유지
- 날짜 필터 값은 `meta.filters.date_from`, `meta.filters.date_to`에 ISO 문자열(`YYYY-MM-DD`)로 반영

## 3. 공통 구조

```json
{
  "meta": {
    "screen": "worker",
    "screenId": "WEB-WORKER",
    "timezone": "Asia/Seoul",
    "effectiveAt": "2026-03-23T00:00:00+09:00",
    "updatedAt": "2026-03-23T00:05:00+09:00",
    "requestedDate": "2026-03-15",
    "scenarioDate": "2026-03-15",
    "line": "LINE-C",
    "viewMode": "realtime_day",
    "requestedDateRange": null,
    "filters": {
      "factory": null,
      "line": null,
      "shift": null,
      "period": null,
      "tz": "Asia/Seoul",
      "date_from": "2026-03-15",
      "date_to": "2026-03-15"
    },
    "dataMode": "live"
  },
  "kpis": [],
  "notice": null
}
```

## 4. meta 규칙

| 필드 | 설명 |
| --- | --- |
| `screen` | 화면 키 (`worker / qa / manager / promo`) |
| `screenId` | 화면 식별자 |
| `timezone` | 응답 기준 타임존 |
| `effectiveAt` | 집계 기준 시각 |
| `updatedAt` | 실제 응답 생성 시각 |
| `requestedDate` | 단일 날짜 조회 기준일 |
| `scenarioDate` | 실제 스냅샷 계산 기준일 |
| `line` | 화면 기준 라인 |
| `viewMode` | `realtime_day` 또는 `period_compare` |
| `requestedDateRange` | 기간 비교 모드일 때 `{from,to,days}` |
| `dataMode` | `live` 또는 `period_compare` |

`meta.line` 정책:

- `worker`: 항상 실제 담당 라인
- `qa / manager / promo`: line filter가 없으면 `null`
- line filter가 명시되면 해당 값을 반영

## 5. notice

`notice`는 선택 필드입니다.

```json
{
  "notice": {
    "key": "manager-delay",
    "message": "최신 데이터 반영이 지연되고 있습니다."
  }
}
```

## 6. kpis 공통 구조

```json
{
  "id": "qa_recheck",
  "label": "재검 대기",
  "value": 171,
  "unit": "건",
  "target": 200,
  "status": "critical",
  "meta": "actual/db",
  "detailId": "qa.reinspection.queue",
  "targetType": "lot",
  "targetId": "LOT-88436",
  "clickable": true,
  "detailTitle": "재검 상세"
}
```

| 필드 | 설명 |
| --- | --- |
| `id` | KPI 식별자 |
| `label` | 카드 제목 |
| `value` | KPI 값 |
| `unit` | 단위 |
| `target` | 목표값, 없을 수 있음 |
| `status` | `ok / warning / critical` |
| `meta` | 데이터 출처 문자열 (`actual/db`, `derived/db`, `predicted/db`, `actual/mock` 등) |
| `detailId` | 상세 API용 detail 식별자 |
| `targetType` | 상세 API용 target type |
| `targetId` | 상세 API용 target id |
| `clickable` | 클릭 상세 가능 여부 |
| `detailTitle` | 상세 모달 제목 |

규칙:

- `detailId / targetType / targetId / detailTitle`는 clickable KPI에서만 사용
- 일반 KPI는 이 필드들이 없거나 `clickable: false`

## 7. 탭별 핵심 필드

### worker

필수 top-level:

- `meta`
- `kpis`
- `lineTemperature`
- `hint`
- `statusGrid`
- `actionQueue`
- `globalNotices`
- `ngTrend`
- `ngTypes`
- `events`

핵심 규칙:

- `statusGrid[].status`는 `run / idle / down / maint`
- `actionQueue`는 내 라인 조치 항목만
- `globalNotices`는 공용/타 라인 알림만
- 현재 clickable KPI: `worker_recent_10m_ng`

### qa

필수 top-level:

- `meta`
- `kpis`
- `hint`
- `topDefects`
- `recheckQueue`
- `defectTrend`
- `issues`
- `events`

핵심 규칙:

- `topDefects[].class_name`은 live에서 대문자 문자열일 수 있음
- `recheckQueue[]`는 `lotId / defectClass / priority / severity / queuedAt / count / cause`
- 현재 clickable KPI:
  - `qa_defect_rate`
  - `qa_recheck`

### manager

필수 top-level:

- `meta`
- `kpis`
- `managerLineOee`
- `managerProductionTrend`
- `managerDefectTrend`
- `riskOverall`
- `riskLines`
- `pendingActions`
- `activeAlarms`
- `events`

핵심 규칙:

- `managerLineOee[].actual`은 `0~100` 범위
- `activeAlarms[].ack`는 `ack / hold / unack` 계열 문자열
- 현재 clickable KPI:
  - `mgr_oee`
  - 단, 활성 알람이 있을 때만 clickable

### promo

필수 top-level:

- `meta`
- `kpis`
- `promoWeekProduction`
- `promoLines`
- `promoTopDefects`
- `promoCurrentAlarms`
- `promoMonthlyCompare`
- `promoTicker`

핵심 규칙:

- 기간 비교 시 `dailyCompare`와 `requestedDateRange`가 함께 반영
- line 표기는 `LINE-A` 형식 유지

## 8. 날짜/기간 비교 규칙

- `date_from == date_to`
  - `meta.viewMode = realtime_day`
  - `meta.dataMode = live`
- `date_from != date_to`
  - `meta.viewMode = period_compare`
  - `meta.dataMode = period_compare`
  - `meta.requestedDateRange` 존재
  - `dailyCompare` 배열 존재

## 9. 상세 API 연결 규칙

프론트는 `/api/v1/dashboard/detail`을 아래 메타로 호출합니다.

```json
{
  "screen": "qa",
  "detailId": "qa.reinspection.queue",
  "targetType": "lot",
  "targetId": "LOT-88436"
}
```

현재 KPI/목록에서 실제 사용 중인 대표 detail 연결:

- `qa.reinspection.queue`
- `qa.defect.detail`
- `common.alarm.detail`
- `worker.action.detail`

## 10. 한 줄 결론

현재 `web_dashboard`의 응답 계약 기준은 **live API 응답 + backend response model + 본 문서**이며,  
mock 데이터는 이 계약을 따라가는 fallback 용도로만 유지합니다.
