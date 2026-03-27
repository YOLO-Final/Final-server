# PERIOD_COMPARE_MODE_DESIGN

## 목적

- 달력에서 `date_from ~ date_to`를 선택했을 때,
  - 기존 단일 시점(발생시각 중심) 표시가 아니라
  - **일자별 비교(일 단위 집계)** 중심으로 보여준다.

예시: `2026-03-08 ~ 2026-03-10`

- 8일 / 9일 / 10일 일별 생산·불량·알람을 비교
- KPI는 기간 합계/평균 기준으로 재계산
- 상세 이벤트 시간 목록은 보조 정보로 축소

---

## 1) 화면 모드 규칙

### 1.1 모드 판정

- `date_from`, `date_to` 모두 존재:
  - `viewMode = "period_compare"`
- 둘 다 없음:
  - `viewMode = "realtime_day"`

### 1.2 표시 원칙

- `realtime_day`: 기존 UI 유지
- `period_compare`: 일별 비교 UI로 전환

---

## 2) API 계약(확장)

대상 엔드포인트:

- `/api/v1/dashboard/web/worker`
- `/api/v1/dashboard/web/qa`
- `/api/v1/dashboard/web/manager`
- `/api/v1/dashboard/web/promo`

요청 파라미터:

- `date_from=YYYY-MM-DD`
- `date_to=YYYY-MM-DD`

응답 메타(추가):

```json
{
  "meta": {
    "viewMode": "period_compare",
    "requestedDateRange": {
      "from": "2026-03-08",
      "to": "2026-03-10",
      "days": 3
    }
  }
}
```

---

## 3) 공통 응답 필드(추가)

모든 탭 공통으로 `dailyCompare` 추가:

```json
{
  "dailyCompare": [
    {
      "date": "2026-03-08",
      "produced": 12400,
      "good": 11920,
      "ng": 480,
      "defect_rate": 3.87,
      "alarm_count": 12,
      "oee": 81.2
    }
  ]
}
```

원칙:

- 기간 선택 시 최소 1일~최대 31일 허용
- 일자가 비어도 row는 만들고 값은 `0` 처리(화면 끊김 방지)

---

## 4) 탭별 표시 변경

### 4.1 worker

- KPI:
  - `시간당 생산량` -> `기간 평균 생산량(일평균)` 라벨 전환
- 차트:
  - `최근 10분 NG` -> `일별 NG 추이`
- 상태그리드:
  - 실시간 설비 상태는 참고 영역으로 축소

### 4.2 qa

- KPI:
  - `불량률`, `재검 대기`를 기간 평균/합계로 변경
- 차트:
  - 불량 원인 Top은 기간 합계 기준
  - 추세는 일별 선형 비교

### 4.3 manager

- KPI:
  - OEE / 목표달성률 / 생산량을 기간 집계값으로
- 운영 리스크:
  - 일별 리스크 스코어 비교 테이블 추가

### 4.4 promo

- 주간 카드 대신:
  - 선택 기간 일별 생산 비교를 메인 카드로 사용
- ticker:
  - 실시간 문구보다 기간 요약 문구 우선

---

## 5) 백엔드 구현 가이드

### 5.1 입력 검증

- `date_from > date_to`면 400
- 범위 31일 초과면 400

### 5.2 repository 계층

- `get_web_dashboard_snapshot(...)`에 기간 집계 함수 추가:
  - `get_web_dashboard_period_snapshot(line_code, date_from, date_to)`
- SQL 기준:
  - `recorded_at::date` / `occurred_at::date` 그룹화
  - `GROUP BY work_date ORDER BY work_date`

### 5.3 service 계층

- `date_from/date_to` 있으면 period path 사용
- `meta.viewMode = "period_compare"` 설정
- 기존 `kpis`는 기간 집계로 재계산

---

## 6) 프론트 구현 가이드

### 6.1 모드 전환

- `bundle.meta.viewMode`로 분기
- 기존 레이아웃 유지 + 데이터 블록만 교체(점진 적용)

### 6.2 라벨/단위 동적 변경

- `시간당` -> `기간 평균`
- `최근 10분` -> `기간 일별`

### 6.3 초기화 버튼

- `초기화` 클릭 시:
  - `selectedDateRange = null`
  - `viewMode = realtime_day` 재조회

---

## 7) 단계별 적용 순서(권장)

1. backend: 메타 `viewMode`, `requestedDateRange` 먼저 반환
2. backend: `dailyCompare` 공통 필드 구현
3. frontend: `dailyCompare` 차트 1개 먼저 적용(qa 또는 promo)
4. frontend: 탭별 KPI 라벨/값 전환
5. QA: 기간 1일/3일/7일/31일 시나리오 점검

---

## 8) 완료 기준(DoD)

- 기간 선택 시 4개 탭 모두 200 응답
- `meta.viewMode="period_compare"` 확인
- 일별 비교 차트에서 날짜 축이 선택 기간과 일치
- `초기화` 클릭 시 당일 실시간 모드 복귀
- 빈 날짜가 있어도 화면 깨짐 없음(0값 처리)
