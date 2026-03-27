# Dashboard BE/DB 참조 문서 — 8단계 최종 검수 기준

> 작성일: 2026-03-17
> 대상: 백엔드(FastAPI) / DB 담당자
> 기준: 스마트 팩토리 대시보드 FE 개편 8단계 최종 검수 결과
> 관련 파일: `server_api/src/modules/dashboard/` (service.py / repository.py / router.py / schemas.py)

---

## 목차

1. [즉시 수정 필요 항목 (배포 전 필수)](#1-즉시-수정-필요-항목)
2. [현재 라이브/mock 연동 현황](#2-현재-라이브mock-연동-현황)
3. [API 엔드포인트 계약](#3-api-엔드포인트-계약)
4. [Detail API — detailId × targetType 유효 조합표](#4-detail-api--detailid--targettype-유효-조합표)
5. [datasets 필드 계약 (화면별)](#5-datasets-필드-계약-화면별)
6. [DB 연결 현황 및 미구현 영역](#6-db-연결-현황-및-미구현-영역)
7. [오류 응답 규약](#7-오류-응답-규약)
8. [권장 개선 항목 (배포 후)](#8-권장-개선-항목-배포-후)

---

## 1. 즉시 수정 필요 항목

> 아래 항목은 현재 라이브 API 연동 경로에서 오류 패널이 노출되는 버그입니다.
> FE 버튼 클릭 → `/api/v1/dashboard/detail` 요청 → 백엔드 400/404 응답 순서로 발생합니다.

### F-4: `manager.alarm.detail` — `targetId="ALL"` 처리 누락 (404)

**현상**
FE `managerLayout`의 알람 전체 보기 버튼이 `data-target-id="all"`을 하드코딩하여 전송합니다.
`_find_mock_detail_content`는 `activeAlarms` 배열에서 `alarmId == "ALL"` 또는 `targetId == "ALL"`을 찾으려 하지만 일치하는 행이 없어 404를 반환합니다.

**위치**: `service.py` → `_find_mock_detail_content` 함수

**현재 코드 (alarm/event 분기)**:
```python
elif target_type in {"alarm", "event"}:
    summary = [row for row in datasets.get("activeAlarms", []) if same(row.get("alarmId")) or same(row.get("targetId"))]
    logs = [row for row in datasets.get("handoffLogs", []) if same(row.get("targetId"))]
    related = [row for row in datasets.get("eventTimeline", []) if same(row.get("targetId"))]
```

**수정 방법**
`alarm` 분기 앞에 sentinel "ALL" 특수 케이스를 추가합니다:

```python
elif target_type in {"alarm", "event"}:
    # manager.alarm.detail 은 targetId="all" 로 전체 알람 목록을 요청함
    if target_id == "ALL":
        alarms = datasets.get("activeAlarms", [])
        summary = sorted(alarms, key=lambda r: (
            0 if r.get("severity") == "critical" else
            1 if r.get("severity") == "warning" else 2
        ))
        logs = datasets.get("handoffLogs", [])
        related = datasets.get("eventTimeline", [])
    else:
        summary = [row for row in datasets.get("activeAlarms", []) if same(row.get("alarmId")) or same(row.get("targetId"))]
        logs = [row for row in datasets.get("handoffLogs", []) if same(row.get("targetId"))]
        related = [row for row in datasets.get("eventTimeline", []) if same(row.get("targetId"))]
```

> `target_id`는 이미 `.strip().upper()` 처리된 상태이므로 `"ALL"` 비교로 충분합니다.

---

### P-2: `_build_qa_live` — `activeAlarms` 미구성 (라이브 경로 한정)

**현상**
`qa.issue.detail` 모달 렌더러(`renderQaIssueDetail`)는 `ds.activeAlarms`를 읽습니다.
mock 경로에서는 7단계에서 `activeAlarms`를 QA 번들에 추가했기 때문에 정상 동작합니다.
그러나 라이브 API 경로(`_build_qa_live`)에는 `activeAlarms`를 구성하는 코드가 없습니다.
DB에 `vision_result` 데이터가 있어 `dataMode=live`가 되면 QA 이슈 모달이 빈 상태가 됩니다.

**위치**: `service.py` → `_build_qa_live` 함수 (L484~L546)

**수정 방법**
`_build_qa_live` 내부에 `activeAlarms` 구성 로직을 추가합니다.
현재 `DashboardLiveSnapshot`에는 알람 전용 쿼리가 없으므로 옵션 2가지 중 택일:

**옵션 A — mock `activeAlarms`를 라이브 경로에서도 유지 (빠른 임시방편)**
`_build_qa_live`에서 `datasets["activeAlarms"]`를 덮어쓰지 않으면, 번들 초기화 시 `_copy_mock_bundle`이 이미 mock activeAlarms를 복사했으므로 자동 유지됩니다. 별도 코드 추가 불필요. **현재 상태도 이미 이 방식**이며, `REQUIRED_LIVE_DATASETS["qa"]`에 `activeAlarms`가 없으므로 `coverage.mockDatasetKeys`에 표시됩니다.

**옵션 B — 실제 알람 쿼리 추가 (권장, 배포 후 작업)**
`DashboardLiveSnapshot`에 `active_alarms` 필드를 추가하고, `repository.py`에 알람 쿼리를 구성합니다. 상세는 [6. DB 연결 현황 및 미구현 영역](#6-db-연결-현황-및-미구현-영역)을 참조하세요.

---

## 2. 현재 라이브/mock 연동 현황

현재 백엔드는 `vision_result` 테이블 하나를 기반으로 라이브 데이터를 구성합니다.
DB에 `vision_result` 데이터가 없으면 전체 화면이 `dataMode=mock`으로 응답됩니다.

### 라이브 데이터 가능 항목 (`dataMode=live` 시)

| 화면 | 데이터셋 키 | 소스 |
|------|------------|------|
| worker | `ngTrend10m` | vision_result → 10분 rollup |
| worker | `topDefects` | vision_result → defect_type JOIN |
| worker | `ngLogs` | vision_result NG 최근 20건 |
| worker | `eventTimeline` | vision_result NG 기반 생성 |
| worker | `pendingActions` | vision_result 저신뢰도 행 기반 |
| qa | `defectTrend` | vision_result 일별 집계 |
| qa | `topDefects` | vision_result top5 |
| qa | `ngRows` | vision_result NG 목록 |
| qa | `recheckQueue` | vision_result request_id 기반 |
| qa | `summaryLine` | vision_result 저신뢰도 건수 |
| manager | `hourly` | vision_result 시간대별 rollup proxy |
| manager | `recommendation` | top_defects[0] 기반 텍스트 |
| promo | `lineTrend` | vision_result hourly proxy |
| promo | `top3`, `topIssues`, `rollingMessage` | vision_result top_defects |

### 항상 mock으로 내려오는 항목

아래 항목들은 DB 연결이 되어 있어도 mock 데이터가 반환됩니다.

| 항목 | 이유 |
|------|------|
| `statusGrid` (전체 화면) | 설비 상태 테이블 미연결 |
| `activeAlarms` (전체 화면) | 알람 테이블 미연결 |
| `downtimeHistory` | 다운타임 로그 테이블 미연결 |
| `downtimePareto` | 다운타임 원인 집계 미연결 |
| `lineCompare` | 생산 계획 테이블 미연결 |
| `statusDistribution` | 설비 상태 집계 미연결 |
| `riskLines`, `pendingActions` (manager) | 운영 리스크 테이블 미연결 |
| `handoffLogs` (전체 화면) | 인계 로그 테이블 미연결 |
| `recheckQueue` (qa) | QA 재검 테이블 미연결 (request_rollups proxy 사용) |
| KPI: `mgr_achievement`, `worker_achievement` | 생산 계획 대비 계산 불가 |
| KPI: `promo_achievement` | 생산 계획 미연결 |
| assistive `worker_ml_hint` | top_defects 기반으로 부분 live 가능 |

---

## 3. API 엔드포인트 계약

### 공통 쿼리 파라미터

모든 엔드포인트에서 아래 파라미터를 수신합니다 (현재 집계 반영은 미구현, 구조만 존재):

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `screen` | string | `worker` / `qa` / `manager` / `promo` |
| `tz` | string | 타임존 (예: `Asia/Seoul`) |
| `factory` | string | 공장 ID (미구현) |
| `line` | string | 라인 ID (미구현) |
| `shift` | string | 근무조 (미구현) |
| `period` | string | 기간 (미구현) |

### 공통 응답 root meta 필드

```json
{
  "screen": "worker",
  "screenId": "SCR-001",
  "timezone": "Asia/Seoul",
  "dataMode": "live | mock",
  "effectiveAt": "2026-03-15T23:59:59+09:00",
  "updatedAt": "2026-03-15T23:59:59+09:00",
  "isPartial": true,
  "isDelayed": false,
  "staleLabel": "정상 | 지연",
  "coverage": {
    "liveDatasetKeys": ["ngTrend10m", "topDefects"],
    "mockDatasetKeys": ["statusGrid", "activeAlarms"],
    "liveKpiKeys": ["worker_recent_10m_ng"],
    "mockKpiKeys": ["worker_achievement"],
    "note": "...",
    "liveSource": "vision_result"
  }
}
```

> `isDelayed`는 `vision_result.created_at` 최신값이 6시간 이상 경과 시 `true`가 됩니다.
> `isPartial`은 `REQUIRED_LIVE_DATASETS[screen]`의 모든 키가 live로 채워지지 않은 경우 `true`입니다.

### `GET /api/v1/dashboard/status`

```json
{
  "module": "dashboard",
  "message": "Dashboard API is ready.",
  "screens": ["manager", "promo", "qa", "worker"],
  "detailEndpoint": "/api/v1/dashboard/detail",
  "liveSources": {
    "vision_result": true,
    "latestDate": "2026-03-15"
  }
}
```

### `GET /api/v1/dashboard/kpis?screen=&...`

응답 구조:
```json
{
  // root meta 필드 (위 공통 참조)
  "kpis": {
    "items": [
      {
        "key": "worker_recent_10m_ng",
        "label": "최근 10분 NG",
        "value": 12,
        "unit": "건",
        "sourceType": "actual | derived | simulated | predicted | recommended",
        "dataMode": "live | mock",
        "detailId": "worker.event.detail",
        "targetType": "event",
        "targetId": "REQ-001",
        "clickable": true
      }
    ]
  },
  "assistive": {
    "items": [
      {
        "key": "worker_ml_hint",
        "label": "ML 힌트",
        "value": "short 발생 12건",
        "sourceType": "actual",
        "severity": "warning",
        "status": "warning",
        "reasonSummary": "...",
        "confidence": null,
        "detailId": null,
        "targetType": null,
        "targetId": null,
        "clickable": false
      }
    ]
  }
}
```

### `GET /api/v1/dashboard/datasets?screen=&...`

```json
{
  // root meta 필드
  "datasets": {
    "statusGrid": [...],
    "activeAlarms": [...],
    // 화면별 추가 키 (5절 참조)
  }
}
```

### `GET /api/v1/dashboard/detail?screen=&detailId=&targetType=&targetId=&subKey=`

```json
{
  // root meta 필드
  "detailId": "worker.line.detail",
  "targetType": "line",
  "targetId": "LINE-A",
  "subKey": "overview",
  "summary": [...],
  "logs": [...],
  "relatedItems": [...],
  "actions": []
}
```

---

## 4. Detail API — detailId × targetType 유효 조합표

> `_canonical_target_type()` 에서 허용된 targetType 이외의 값은 **HTTP 400** 을 반환합니다.
> `_validate_detail_id()` 에서 등록되지 않은 detailId는 **HTTP 400** 을 반환합니다.

### 허용된 targetType 값

```
line | equipment | lot | defect | inspection | alarm | event | shift
```

> ❌ 백엔드가 거부하는 값 (FE 버그로 일부 전송 가능, 이미 수정 예정):
> `cause`, `qa`, `action` — 이 값들은 `_canonical_target_type`에 alias 없음 → 400

### screen별 등록된 detailId

| screen | detailId | 허용 targetType (FE 기준) |
|--------|----------|--------------------------|
| worker | `worker.line.detail` | `line` |
| worker | `worker.equipment.detail` | `equipment` |
| worker | `worker.event.detail` | `event` |
| worker | `worker.action.detail` | `alarm` |
| qa | `qa.defect.detail` | `defect` |
| qa | `qa.reinspection.queue` | `lot` |
| qa | `qa.inspection.detail` | `inspection` |
| qa | `qa.lot.detail` | `lot` |
| qa | `qa.cause.detail` | `defect` ← (FE가 "cause"로 잘못 전송 중, 수정 예정) |
| qa | `qa.recheck.detail` | `lot` |
| qa | `qa.trend.detail` | `defect` ← (FE가 "qa"로 잘못 전송 중, 수정 예정) |
| qa | `qa.issue.detail` | `alarm` |
| manager | `manager.line.detail` | `line` |
| manager | `manager.risk.detail` | `line` |
| manager | `manager.bottleneck.detail` | `line` |
| manager | `manager.plan.detail` | `line` |
| manager | `manager.pareto.detail` | `line` |
| manager | `manager.event.detail` | `event` |
| manager | `manager.action.detail` | `alarm` ← (FE가 "action"으로 잘못 전송 중, 수정 예정) |
| manager | `manager.alarm.detail` | `alarm` + targetId="all" ← F-4 수정 필요 |
| 공통 | `common.alarm.detail` | `alarm` |

> FE 수정 예정 항목 (FE 담당자 작업):
> - `qa.cause.detail` 버튼: `data-target-type="cause"` → `"defect"` 로 수정
> - `qa.trend.detail` 버튼: `data-target-type="qa"` → `"defect"`, `data-target-id="defect_trend"` → `"short"` 로 수정
> - `manager.action.detail` 버튼: `data-target-type="action"` 기본값 → `"alarm"` 로 수정

### `_find_mock_detail_content` 매칭 로직 요약

| targetType | summary 소스 | logs 소스 | relatedItems 소스 |
|------------|-------------|-----------|------------------|
| `line` | `statusGrid[lineId]` | `activeAlarms[lineId]` | `downtimePareto[lineId]` |
| `equipment` | `statusGrid[equipmentId]` | `activeAlarms[equipmentId]` | `downtimeHistory[equipmentId]` |
| `lot` | `ngRows[lotId]` | `handoffLogs[targetId]` | `recheckQueue[lotId]` |
| `alarm` / `event` | `activeAlarms[alarmId 또는 targetId]` | `handoffLogs[targetId]` | `eventTimeline[targetId]` |
| `alarm` + targetId="ALL" | `activeAlarms` 전체 (severity 정렬) | `handoffLogs` 전체 | `eventTimeline` 전체 |
| `inspection` | `recheckQueue[inspectionId]` | `handoffLogs[targetId]` | `ngRows[lotId 또는 targetId]` |
| `defect` | `topDefects[causeCode 또는 class_name]` | `ngRows[defectClass 또는 defectType]` | `recheckQueue[defectClass]` |

---

## 5. datasets 필드 계약 (화면별)

### worker datasets

```typescript
statusGrid[]:    { lineId, equipmentId, status, severity, updatedAt, sourceType, targetType, targetId }
activeAlarms[]:  { alarmId, severity, status, occurredAt, lineId, equipmentId, causeCode, ackState, sourceType, targetType, targetId }
eventTimeline[]: { time, category, title, detailId, targetType, targetId }
ngTrend10m[]:    { time: "HH:MM", ng: number }
topDefects[]:    { class_name, count, color }
ngLogs[]:        { time, line, cls, conf }
downtimeHistory[]: { startedAt, lineId, equipmentId, reason, restartedAt }
pendingActions[]:  { owner, title, dueAt, targetType, targetId }
handoffLogs[]:   { actionId, targetId, actionType, memo, actor, shift, createdAt, handoffStatus }
```

### qa datasets

```typescript
defectTrend[]:  { time, actual, predicted }
topDefects[]:   { class_name, count, color, causeCode }
ngRows[]:       { detectedAt, lineName, boardId, lotId, equipmentId, defectType, defectClass, confidencePct, occurredAt, targetType, targetId }
recheckQueue[]: { inspectionId, lotId, defectClass, queuedAt, priority, recheckStatus, owner }
handoffLogs[]:  { actionId, targetId, actionType, memo, actor, shift, createdAt, handoffStatus }
summaryLine:    string
activeAlarms[]: { alarmId, severity, status, occurredAt, lineId, equipmentId, causeCode, ackState, sourceType, targetType, targetId }
pendingActions[]: { title, dueAt, targetType, targetId }
```

> `activeAlarms`와 `pendingActions`는 QA 화면에서도 필요합니다.
> `qa.issue.detail` 모달이 `activeAlarms`를, `qa.recheck.detail`이 `pendingActions.targetId`를 사용합니다.

### manager datasets

```typescript
statusGrid[]:         { lineId, equipmentId, status, severity, updatedAt, sourceType, targetType, targetId }
activeAlarms[]:       { alarmId, severity, status, occurredAt, lineId, equipmentId, causeCode, ackState, sourceType, targetType, targetId }
hourly[]:             { time: "HH:00", produced, defectRate, target, forecast }
lineCompare[]:        { line, actual, plan }
statusDistribution[]: { label, value, color }
downtimePareto[]:     { causeCode, downtimeMinutes, occurrenceCount, lineId, timeRange }
riskLines[]:          { lineId, riskScore, reason }
pendingActions[]:     { kind, count, summary }  ← 관리자 화면용 집계형 (작업자화면과 구조 다름)
handoffLogs[]:        { actionId, targetId, actionType, memo, actor, shift, createdAt, handoffStatus }
recommendation:       string
```

> **주의**: `manager.pendingActions`의 각 row에 `targetType`/`targetId`가 없으면 `manager.action.detail` 버튼 클릭 시
> FE가 기본값 `"action"`을 targetType으로 사용합니다 → FE 수정 예정이지만, BE mock 데이터에도 `targetType: "alarm"`, `targetId: "ALM-XXXX"` 형태로 명시하는 것을 권장합니다.

### promo datasets

```typescript
statusGrid[]:    { lineId, status, severity, updatedAt }
lineTrend[]:     { time, produced }
top3[]:          { class_name, count, color }
topIssues[]:     { rank, title, summary }
rollingMessage:  string
```

### status 값 enum

```
RUN | IDLE | DOWN | MAINT | UNKNOWN
```

### severity 값 enum

```
info | warning | critical | unknown
```

### sourceType 값 enum

```
actual | derived | simulated | predicted | recommended
```

---

## 6. DB 연결 현황 및 미구현 영역

### 현재 연결된 테이블

| 테이블 | 용도 | 쿼리 위치 |
|--------|------|-----------|
| `vision_result` | NG 판정 결과, 신뢰도, defect_type | `repository.py` — 7개 쿼리 |
| `defect_type` | defect class_name, desc | `repository.py` — top_defects JOIN |

**`vision_result` 스키마 (현재 사용 컬럼)**:
```sql
request_id      -- 요청 식별자 (YYYYMMDDHH24MISS 포맷 prefix 활용)
created_at      -- 검사 일자 (date 타입으로 사용)
result_status   -- 'OK' | 'NG' | ...
defect_type     -- 불량 유형 (defect_type.class_name과 JOIN)
confidence      -- 0.0~1.0 신뢰도
image_path      -- 이미지 경로
```

**`defect_type` 스키마 (현재 사용 컬럼)**:
```sql
class_name  -- defect_type과 JOIN 키
desc        -- 설명
```

### 미연결 / 미구현 테이블 (작업 필요)

아래 테이블들은 FE가 필요로 하는 데이터를 위해 향후 연결이 필요합니다.

| 테이블 (후보명) | 필요 데이터 | 영향 dashboard 키 |
|-----------------|------------|-------------------|
| `equipment` / `equipment_status_history` | 설비 상태, 최신 snapshot | `statusGrid` |
| `alarm_events` / `notifications` | 발생 알람, ACK 상태, causeCode | `activeAlarms` |
| `downtime_logs` | 다운타임 이력, 원인코드 | `downtimeHistory`, `downtimePareto` |
| `production_plan` | 라인별 목표 생산량 | `lineCompare.plan`, KPI 달성률 |
| `event_logs` | 운영 이벤트 타임라인 | `eventTimeline` |
| `inspection_results` | QA 검사 결과 | `recheckQueue` (현재 request_rollups proxy 사용) |
| `handoff_logs` / `qa_actions` | 조치/인계 로그 | `handoffLogs`, `pendingActions` |
| `ml_predictions` | ML 예측 리스크 점수 | `riskLines`, assistive items |

### 즉시 확인 가능한 DB 점검 쿼리

```sql
-- vision_result 데이터 존재 여부 및 최신 일자 확인
SELECT MAX(created_at) AS latest_date, COUNT(*) AS total_rows FROM vision_result;

-- 오늘 기준 NG 건수
SELECT COUNT(*) FROM vision_result WHERE created_at = CURRENT_DATE AND lower(result_status) = 'ng';

-- defect_type 매핑 확인
SELECT class_name, desc FROM defect_type ORDER BY class_name;

-- 스키마 내 기타 테이블 존재 여부 확인
SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;
```

---

## 7. 오류 응답 규약

FE는 아래 응답 코드와 body 구조를 기준으로 분기합니다.

| HTTP 코드 | `detail.code` | FE 동작 |
|----------|---------------|---------|
| `400` | `"unsupported"` | 오류 패널 표시 |
| `403` | `"forbidden"` | 오류 패널 표시 (promo에서 detail 접근 시) |
| `404` | `"not_found"` | 오류 패널 표시 |
| `5xx` | (없음) | 네트워크 오류로 간주 → mock 폴백 |

**오류 응답 body 형식**:
```json
{
  "detail": {
    "code": "unsupported | forbidden | not_found",
    "message": "설명 메시지"
  }
}
```

> `5xx` 응답은 FE가 네트워크 오류로 판정하여 mock 데이터로 폴백합니다.
> `400`, `403`, `404`는 오류 패널로 전환됩니다.

---

## 8. 권장 개선 항목 (배포 후)

우선순위 순으로 정리합니다.

| 순위 | 항목 | 설명 |
|------|------|------|
| 1 | `statusGrid` 라이브 연결 | `equipment` 또는 `equipment_status_history` 테이블에서 최신 상태 snapshot 구성 |
| 2 | `activeAlarms` 라이브 연결 | `alarm_events` 테이블에서 미해결 알람 조회; `ackState`, `causeCode`, `targetType`, `targetId` 필수 |
| 3 | `_build_qa_live` `activeAlarms` 구성 | `DashboardLiveSnapshot`에 알람 쿼리 추가 후 QA 번들에 포함 |
| 4 | `production_plan` 연결 | `lineCompare.plan`, `hourly.target`, KPI `*_achievement` 계산 |
| 5 | `handoffLogs` / `pendingActions` 라이브 연결 | 조치/인계 로그 조회 API 연결 |
| 6 | `inspection_results` / `reinspection_queue` 연결 | QA recheckQueue를 request_rollups proxy가 아닌 실제 검사 테이블로 교체 |
| 7 | `downtime_logs` 연결 | `downtimePareto`, `downtimeHistory` 라이브 집계 |
| 8 | 필터 파라미터 반영 | `factory`, `line`, `shift`, `period` 파라미터를 실제 쿼리 WHERE 절에 반영 |

---

## 참조

| 파일 | 내용 |
|------|------|
| `server_api/src/modules/dashboard/service.py` | 모든 비즈니스 로직, mock 번들, live 빌드, detail 라우팅 |
| `server_api/src/modules/dashboard/repository.py` | DB 쿼리 (vision_result 전용) |
| `server_api/src/modules/dashboard/router.py` | 4개 엔드포인트 정의 |
| `server_api/src/modules/dashboard/schemas.py` | Pydantic 스키마 (`DashboardDetailResponse.model_config = extra="allow"`) |
| `docs/dashboard_be_db_checklist.md` | 전체 BE/DB 체크리스트 (이전 단계 기준) |
| `nginx/html/js/wed_dashboard/dashboard_api.js` | FE API 호출 + MOCK_SCREENS 정의 |
| `nginx/html/js/wed_dashboard/dashboard_app.js` | FE 화면 렌더링, 버튼 클릭 → detail 요청 흐름 |
