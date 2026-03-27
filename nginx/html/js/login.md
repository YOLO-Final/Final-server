# 로그인 기획 및 인증 설계

> 범위 메모: 이 문서는 기본적으로 `login.html + js/login.js` 기준의 로그인 설계를 설명합니다. `web_dashboard` 전용 로그인 경계는 `web_login.html + js/web_login/web_login.js` 문서 세트를 우선 참고합니다.

> **v13 변경사항**: 로그아웃 절 신규 추가 (POST /auth/logout — token_version +1 즉시 무효화), 비밀번호 변경 UI 위치 수정 (로그인 화면 → 로그인 후 작업자 영역), 전체 인증 흐름에 로그아웃 흐름 추가, API 목록 및 에러 응답표 갱신, 미구현 항목 최신화.

---

## 1. 로그인 기능 요구사항

| # | 항목 | 내용 | 비고 |
|---|------|------|------|
| 1 | **로그인 ID** | 회사에서 부여한 사원번호 사용 | 현실적이고 실무적인 방식 |
| 2 | **초기 비밀번호** | 생년월일로 초기 설정 (YYYYMMDD 형식) | hr_admin이 계정 생성 시 자동 설정 |
| 3 | **비밀번호 변경** | 본인이 직접 변경 가능 | 로그인 후 작업자 영역 [비밀번호 변경] 버튼 (로그인 전 API 호출 불가) |
| 4 | **권한 분리** | hr_admin / manager / quality_manager / worker 4단계 | 역할 기반 접근 제어 (RBAC) |
| 5 | **얼굴인식 로그인** | InsightFace를 통한 얼굴인식으로도 로그인 가능 | 이 프로젝트의 핵심 기능 |
| 6 | **퇴사자 즉시 차단** | 퇴사 처리 시 즉시 로그인 불가 처리 | DB에서 `ID_active = False` 처리 |
| 7 | **로그인 실패 잠금** | 5회 실패 시 계정 잠금, hr_admin만 해제 가능 | 보안 기본 요소 |
| 8 | **birth_date 형식 검증** | 초기 비밀번호(생년월일) 입력 시 YYYYMMDD 형식 강제 | `field_validator`로 422 반환 |

---

## 2. 인증 방식 비교 (Firebase vs JWT)

### 이 프로젝트의 환경 특성

```
- 공장 내부 인트라넷 환경
- 인터넷 연결이 불안정하거나 없을 수 있음
- InsightFace가 자체 서버에서 직접 실행됨
- PyQt6 온디바이스 중심 구조
```

### 방식 1. Firebase만 사용

**단점**
- 인터넷 필수 → 공장 인트라넷 환경에서 끊기면 로그인 불가
- InsightFace 얼굴인식과 연동이 복잡함
- 퇴사자 처리를 Firebase 콘솔에서 수동으로 해야 함

> **결론: ❌ 이 프로젝트 환경에 맞지 않음**

### 방식 2. JWT만 사용

**장점**
- 인터넷 없어도 작동 (오프라인 완전 대응)
- InsightFace 연동 자유로움
- 퇴사자 처리, 권한 관리를 우리 설계대로 구현 가능
- FastAPI + PostgreSQL과 완벽하게 호환

> **결론: ✅ 이 프로젝트에 가장 적합**

### 방식 3. Firebase + JWT 혼용

> **결론: ❌ 복잡도만 증가, 이 프로젝트 규모에서 불필요**

### 비교 요약표

| 항목 | Firebase | JWT | Firebase + JWT |
|------|----------|-----|----------------|
| 오프라인 작동 | ❌ | ✅ | ❌ |
| InsightFace 연동 | 복잡 | 자유로움 | 복잡 |
| 퇴사자 즉시 차단 | 수동 처리 | 자동 처리 가능 | 수동 처리 |
| 커스텀 권한 관리 | 불편 | 자유로움 | 가능하나 복잡 |
| 구현 난이도 | 쉬움 | 중간 | 어려움 |
| 이 프로젝트 적합성 | ❌ | ✅ | ❌ |

---

## 3. 최종 선택: JWT 단독 사용

### 전체 인증 흐름

```
[ ID/PW 로그인 ]

사원번호 + 비밀번호 (bcrypt 해싱)
            ↓
       FastAPI 서버
            ↓
    PostgreSQL에서 사용자 확인
    1. 사용자 존재 여부 확인
    2. ID_active 체크 (퇴사자 차단) ← 비밀번호 검증 전
    3. ID_locked 체크 (잠금 여부)  ← 비밀번호 검증 전
    4. 비밀번호 검증 (bcrypt)
    5. 실패 시 login_fail_count +1 / 5회 이상 → ID_locked=True, token_version+1
    6. 성공 시 login_fail_count=0, last_login 갱신
            ↓
    Access Token 발급 (20분, payload에 ver=token_version 포함)
    + Refresh Token 발급 (12시간, payload에 ver=token_version 포함)
       ┌──────────┬──────────────────┬──────────────────┐
    hr_admin    manager        quality_manager      worker
    (인사팀)  (총괄관리자)      (품질관리자)         (작업자)


[ 얼굴인식 로그인 — 서버 매칭 방식 ]

단말(카메라)로 얼굴 캡처
            ↓
    단말에서 embedding 벡터를 생성해 TLS(HTTPS)로 서버에 전송
    # raw image는 네트워크로 전송하지 않음
            ↓
    서버가 face_embedding_table의 embedding_json과 cosine similarity 비교
    # threshold: 0.35 이상이면 매칭 성공
            ↓
    매칭 성공 → ID_active / ID_locked 체크 → last_login 갱신
            ↓
    Access Token + Refresh Token 발급 (동일한 흐름)


[ API 요청 시 토큰 검증 ]

모든 인증 필요 API 요청마다:
    토큰의 ver == DB의 token_version 비교
            ↓
    불일치 → 즉시 401 차단
    일치   → ID_active / ID_locked 재확인 → 정상 처리


[ 퇴사자 처리 ]

hr_admin이 퇴사 처리
            ↓
    DB: ID_active = False
        token_version = token_version + 1  ← 기존 토큰 즉시 무효화
            ↓
    이후 모든 API 요청 → ver 불일치 → 401 차단


[ 계정 잠금 ]

5회 로그인 실패
            ↓
    DB: ID_locked = True
        token_version = token_version + 1  ← 기존 토큰 즉시 무효화
            ↓
    hr_admin이 잠금 해제 시:
        ID_locked = False
        login_fail_count = 0
    # token_version은 변경하지 않는다 (옵션 A)
    # 이유: 잠금 해제는 관리자가 직접 승인하는 행위이므로
    #       추가 세션 정리 없이 정상 복구로 처리


[ 비밀번호 변경 흐름 ]

로그인된 사용자가 "비밀번호 수정" 클릭
            ↓
    현재 비밀번호 + 새 비밀번호 + 새 비밀번호 확인 입력
            ↓
    서버에서 현재 비밀번호 bcrypt 검증
            ↓
    검증 실패 → 401 반환
    검증 성공 → 새 비밀번호 bcrypt 해싱 후 저장
               token_version + 1  ← 기존 토큰 즉시 무효화
            ↓
    재로그인 유도 (기존 세션 강제 종료)


[ Refresh Token 흐름 ]

# ※ 범위 선언:
# 본 프로젝트에서는 Refresh Token의 rotation/device_id/해시 저장 정책은 생략하고
# 재발급은 단순 갱신으로 처리한다.

Access Token 만료 (20분)
            ↓
    앱이 자동으로 Refresh Token을 서버에 전송
            ↓
    서버가 Refresh Token 유효성 확인
    + type == "refresh" 확인
    + ver == DB token_version 비교
    + ID_active / ID_locked 재확인
            ↓
    새 Access Token 발급 (20분)
            ↓
    Refresh Token 만료 (12시간) → 다음 출근 시 재로그인


[ 로그아웃 흐름 ]

사용자가 [Log out] 버튼 클릭
            ↓
    클라이언트가 POST /auth/logout 호출
    Authorization: Bearer {access_token}
            ↓
    서버: token_version + 1  ← 기존 발급된 모든 토큰 즉시 무효화
    DB commit
            ↓
    클라이언트: 토큰 전체 삭제
    웹앱   → localStorage 전체 삭제 → /login.html 이동
    PyQt6  → 인스턴스 변수 초기화 → 카메라 종료 → 로그인 화면 이동
            ↓
    이후 해당 토큰으로 API 호출 시 → ver 불일치 → 401 차단

# ※ 서버 호출 실패 시에도 클라이언트 토큰은 반드시 삭제 처리.
# ※ 단순 로그아웃(사용자 직접)은 위 흐름. 강제 종료(퇴사/잠금/비밀번호 변경)도
#    동일하게 token_version +1로 처리되어 일관된 무효화 정책 유지.
```

---

## 4. DB 테이블 설계

### 4-1. 유저정보 테이블 (user_table)

| 필드명 | 타입 | 설명 |
|--------|------|------|
| `employee_no` | VARCHAR(50) | 사원번호 (PK, 로그인 ID) |
| `line_id` | INT | 소속 라인 (NULL 허용 — hr_admin/manager는 라인 없음) |
| `employee_name` | VARCHAR(100) | 사원 이름 — 화면 표시용 |
| `password_hash` | VARCHAR(255) | bcrypt 해싱된 비밀번호 (평문 저장 절대 금지) |
| `role` | VARCHAR(20) | `hr_admin` / `manager` / `quality_manager` / `worker` |
| `ID_active` | BOOLEAN | `False` = 퇴사자, 로그인 차단 |
| `ID_locked` | BOOLEAN | `True` = 로그인 5회 실패 잠금 |
| `login_fail_count` | INT | 로그인 실패 횟수 카운트 |
| `token_version` | INT | 토큰 강제 무효화용 (퇴사/잠금/비밀번호 변경 시 +1) |
| `join_date` | TIMESTAMP | 입사일 |
| `last_login` | TIMESTAMP | 마지막 로그인 시간 (NULL 허용) |

> ⚠️ **ERD 불일치 이슈**: 현재 ERD의 role 주석이 `worker / manager / admin`으로 되어 있으나
> 실제 코드 및 설계는 `worker / manager / quality_manager / hr_admin` 4단계.
> DB 담당자에게 ERD 주석 수정 요청 필요.

> ⚠️ **seed.py 필드 확인**: 현재 seed.py는 `employee_no`, `password_hash`, `role`, `id_active`, `id_locked`, `login_fail_count`, `token_version` 7개 필드만 초기화함.
> `employee_name`, `line_id`, `join_date`는 seed에서 설정하지 않으므로 해당 컬럼이 NULL 허용인지 DB 담당자 확인 필요.

---

### 4-2. face_embedding_table (얼굴 인증용)

| 필드명 | 타입 | 설명 |
|--------|------|------|
| `embedding_id` | INT | PK |
| `employee_no` | VARCHAR(50) | FK → user_table |
| `embedding_json` | TEXT | InsightFace 512차원 벡터 JSON 저장 |

- 실제 얼굴 매칭(cosine similarity)에 사용되는 테이블
- raw image는 저장하지 않음
- 재등록 시 upsert (기존 값 덮어쓰기)
- 삭제 API 구현 완료: `DELETE /auth/face/{employee_no}` (hr_admin 전용)

---

### 4-3. vector_table (등록 상태 조회용)

| 필드명 | 타입 | 설명 |
|--------|------|------|
| `vector_id` | INT | PK |
| `employee_no` | VARCHAR(50) | FK → user_table |
| `face_embedding` | TEXT | 현재 tsvector 형식 임시 저장 |

> ⚠️ **구조 재검토 필요**: tsvector는 텍스트 검색용 타입으로 얼굴 벡터 저장에 의미상 부적합.
> 현재는 등록 여부 확인(등록/미등록 상태 조회)용으로만 사용 중.
> 실제 인증은 face_embedding_table.embedding_json으로 수행.
>
> 향후 선택지:
> - **A안 (현재)**: vector_table은 등록 상태 조회용으로만 유지
> - **B안**: pgvector 확장 도입 → `vector(512)` 타입으로 전환

---

## 5. 초기 계정 생성 정책 (Seed)

### 최초 hr_admin 계정 생성

| 항목 | 내용 |
|------|------|
| 생성 주체 | 시스템 관리자 (배포 시 seed.py 실행) |
| 생성 방식 | `seed.py` 스크립트로 초기 hr_admin 계정 1개 생성 |
| 초기 비밀번호 | `admin123` (개발용 고정값) |
| 초기 사원번호 | `admin` (개발용 고정값) |
| 중복 방지 | 동일 employee_no 존재 시 생성 스킵 |
| 운영 환경 분리 | `APP_ENV=production` 설정 시 seed 자동 스킵 ✅ |

> ⚠️ **운영 주의사항**:
> - 현재 seed.py의 계정 정보(`employee_no="admin"`, `password="admin123"`)는 개발용 하드코딩 값
> - 운영 배포 전 반드시 환경변수 또는 별도 설정 파일로 분리 필요
> - `APP_ENV=production` 설정으로 운영 환경에서 seed 자동 스킵 처리 완료
> - 초기 로그인 후 즉시 비밀번호 변경 권장

### 이후 직원 계정 생성 흐름

```
hr_admin이 로그인
        ↓
    POST /auth/users 호출
    - employee_no (사원번호)
    - name (이름)
    - role (hr_admin / manager / quality_manager / worker)
    - birth_date (생년월일 YYYYMMDD) ← 초기 비밀번호로 사용
    - line_id (소속 라인 — worker는 필수, 그 외 NULL 가능)
        ↓
    서버: birth_date를 bcrypt 해싱 → password_hash 저장
    직원에게 사원번호 + 초기 비밀번호(생년월일) 전달
        ↓
    직원 최초 로그인 후 비밀번호 변경 권장
```

---

## 6. worker line_id 배정 정책

| 항목 | 내용 |
|------|------|
| 배정 주체 | hr_admin |
| 배정 시점 | 계정 생성 시 (`POST /auth/users`) 같이 입력 |
| 필수 여부 | worker는 필수 / hr_admin·manager·quality_manager는 NULL 허용 |
| 변경 | ✅ **구현 완료** — `PATCH /auth/users/{employee_no}/line` (hr_admin 전용) |

> ~~현재 미구현 — 향후 hr_admin 전용 수정 API 추가 예정~~ → **v12에서 완료 처리**

---

## 7. 비밀번호 변경 정책

| 항목 | 내용 |
|------|------|
| 변경 주체 | 본인만 가능 (타인 변경 불가) |
| 검증 방식 | 현재 비밀번호 bcrypt 검증 후 새 비밀번호 저장 |
| 변경 효과 | token_version +1 → 기존 발급된 모든 토큰 즉시 무효화 |
| 재로그인 | 변경 후 자동 로그아웃 → 재로그인 필요 |
| UI 위치 | **로그인 후** 작업자 영역 [비밀번호 변경] 버튼 |

> ⚠️ **v13 수정**: 기존 "로그인 화면 하단 비밀번호 수정 링크"에서 변경.  
> `PATCH /auth/users/{employee_no}/password`는 JWT 인증이 필요한 API이므로  
> 로그인 전 호출이 불가능함. 로그인 후 작업자 영역으로 위치 이동.

### UI 배치 (PyQt6 기준)

```
┌────────────────────────────────────────────┐
│  작업자 : 홍길동   [비밀번호 변경]  [Log out]  │
└────────────────────────────────────────────┘
```

### 비밀번호 변경 흐름

```
[비밀번호 변경] 버튼 클릭
        ↓
현재 비밀번호 + 새 비밀번호 + 새 비밀번호 확인 입력
        ↓
PATCH /auth/users/{employee_no}/password 호출
        ↓
성공(200) → 자동 로그아웃 처리 (POST /auth/logout → 토큰 삭제 → 로그인 화면)
실패(401) → "현재 비밀번호가 올바르지 않습니다."
실패(400) → "새 비밀번호가 일치하지 않습니다."
```

### 비밀번호 변경 요청 스키마

```json
PATCH /auth/users/{employee_no}/password

Request:
{
  "current_password": "19960417",
  "new_password": "newpass123",
  "new_password_confirm": "newpass123"
}

Response (성공 200):
{
  "employee_no": "1001",
  "message": "Password changed successfully. Please log in again."
}

Response (실패 401):
{
  "detail": "Current password is incorrect."
}

Response (실패 400):
{
  "detail": "New passwords do not match."
}
```

---

## 7-1. 로그아웃 정책

> ✅ **v13 신규 추가**

| 항목 | 내용 |
|------|------|
| 로그아웃 방식 | 서버 token_version +1 + 클라이언트 토큰 삭제 |
| 무효화 범위 | 해당 계정으로 발급된 모든 토큰 즉시 차단 |
| API | `POST /auth/logout` (Access Token 필요) |
| 서버 실패 시 | 클라이언트 토큰은 반드시 삭제 처리 |

### token_version +1 방식을 선택한 이유

| 방식 | 보안 | 구현 난이도 |
|------|------|------------|
| 클라이언트 토큰 삭제만 | 토큰 탈취 시 만료(20분)까지 유효 | 쉬움 |
| token_version +1 (채택) | 로그아웃 즉시 모든 토큰 무효화 | 엔드포인트 1개 추가 |

퇴사 처리 / 계정 잠금 / 비밀번호 변경이 이미 token_version +1 방식이므로  
로그아웃도 동일하게 처리해 **일관된 무효화 정책** 유지.

### API 명세

```
POST /api/v1/auth/logout
Authorization: Bearer {access_token}

Response (200):
{
  "message": "Logged out successfully."
}

Response (401 — 토큰 만료/무효):
{
  "detail": "Token has been invalidated. Please log in again."
}
```

### 클라이언트별 처리

| 환경 | 처리 방법 |
|------|-----------|
| 웹앱 | localStorage 전체 삭제 → `/login.html` 이동 |
| PyQt6 | 인스턴스 변수(access_token, employee_no) 초기화 → 카메라 종료 → 로그인 화면 이동 |

| 항목 | 기준 | 비고 |
|------|------|------|
| 조명 | 정면 자연광 또는 실내 형광등 권장 | 역광 시 인식률 저하 |
| 각도 | 정면 기준 ±15도 이내 | 측면 촬영 시 embedding 품질 저하 |
| 거리 | 카메라로부터 40~80cm | 너무 가깝거나 멀면 검출 실패 가능 |
| 해상도 | 최소 640×480 이상 권장 | |
| 마스크 / 선글라스 | 착용 시 등록·인증 불가 | 예외 메시지 안내 필요 |
| 복수 얼굴 | 화면 내 1인만 허용 | 다중 얼굴 감지 시 오류 처리 |

---

## 9. 얼굴 매칭 기준

- **유사도 측정 방식**: Cosine Similarity
- **매칭 성공 기준**: score ≥ 0.35
- **기준값 선정 이유**: InsightFace ArcFace 모델 기준 실험적 최적값
- **매칭 방식**: employee_no 제공 시 1:1 비교 / 미제공 시 전체 DB 대상 1:N 비교

> ※ 현재 로그인 UI(login.html)의 Face ID 섹션에는 별도 사원번호 입력란이 없어
> 실질적으로 1:N 비교만 사용됨. 1:1 비교는 API 레벨에서 지원하나 UI 미연결 상태.

> ※ 1:N 비교는 등록 사용자 수 증가 시 응답 속도 저하 가능.
> 현장 단말 전용 환경(소규모 인원)에서는 허용 가능한 수준.

---

## 10. Face ID 등록 요구사항

| # | 항목 | 내용 |
|---|------|------|
| 1 | 등록 권한 | 로그인한 본인 또는 hr_admin |
| 2 | 등록 방식 | 카메라 촬영 → embedding 추출 → 서버 전송 |
| 3 | raw image | 서버에 저장하지 않음 |
| 4 | 재등록 | 기존 embedding 덮어쓰기 (upsert) |
| 5 | 삭제 | ✅ **구현 완료** — `DELETE /auth/face/{employee_no}` (hr_admin 전용) |
| 6 | 등록 상태 조회 | hr_admin / manager만 전체 목록 조회 가능 |

> ~~삭제: 미구현 (향후 hr_admin 전용 기능으로 추가 예정)~~ → **v12에서 완료 처리**

---

## 11. Face ID 실패 시 처리 정책

| 실패 원인 | HTTP 코드 | 처리 방식 |
|-----------|-----------|-----------| 
| 얼굴 인식 엔진 장애 | 503 | 관리자 문의 안내 |
| 이미지 이상 / 얼굴 미검출 | 422 | "얼굴을 인식할 수 없습니다" 안내 후 재시도 |
| 등록된 embedding 없음 | 404 | "등록된 얼굴이 없습니다. ID/PW로 로그인하세요" |
| 유사도 threshold 미달 | 401 | "얼굴이 일치하지 않습니다. 재시도 또는 ID/PW 로그인" |
| 후보 없음 (전체 DB 빈 경우) | 404 | "등록된 얼굴 데이터가 없습니다" |

- Face ID 실패는 **login_fail_count에 포함하지 않음**
- 인식 실패 시 ID/PW 로그인 화면으로 전환하는 fallback UI 제공

---

## 12. 카메라 권한 및 예외 처리

| 상황 | 처리 방식 |
|------|-----------| 
| 카메라 권한 거부 | "Camera permission denied or unavailable." 표시, ID/PW 로그인 유지 |
| 카메라 장치 없음 | Face ID 섹션 비활성화, ID/PW 로그인만 표시 |
| 카메라 스트림 오류 | 재시도 버튼 제공 |
| 다중 얼굴 감지 | "한 명씩 촬영해 주세요" 안내 |

> UI 확인: 로그인 화면에서 카메라 권한 거부 시 "Camera permission denied or unavailable." 메시지 표시 구현 완료.

---

## 13. 인증 관련 Logging

> ✅ **v12 추가**: logger.py 구현 완료에 따라 신규 절 추가

### 로깅 구조

- **구현 파일**: `src/modules/auth/logger.py`
- **로거 이름**: `auth` (인증 모듈 전용)
- **출력 대상**: 콘솔만 (파일 저장 없음 — `docker logs`로 확인)
- **출력 형식**: `[YYYY-MM-DD HH:MM:SS] 메시지`

### 색상 구분

| 레벨 | 색상 | 적용 상황 |
|------|------|-----------|
| `INFO` | 초록색 (ANSI `\033[92m`) | 로그인 성공, 얼굴 등록 성공 등 |
| `WARNING` / `ERROR` | 빨간색 (ANSI `\033[91m`) | 로그인 실패, 삭제, 예외 발생 등 |

### 사용 방법

```python
from src.modules.auth.logger import auth_logger

auth_logger.info("로그인 성공: employee_no=1001")
auth_logger.warning("로그인 실패: employee_no=9999 (5/5회)")
auth_logger.error("Face ID 엔진 장애: InsightFace unavailable")
```

> ⚠️ **주의**: `auth_logger.propagate`는 기본값 `True`이므로 루트 로거에도 전파됨.
> 중복 출력이 발생할 경우 `auth_logger.propagate = False` 추가 검토 필요.

---

## 14. 인증 API 엔드포인트 목록

| 메서드 | 경로 | 설명 | 인증 필요 |
|--------|------|------|-----------|
| POST | `/auth/login` | 사원번호 + 비밀번호 로그인 | ❌ |
| POST | `/auth/login/face` | 얼굴인식 로그인 | ❌ |
| POST | `/auth/logout` | 로그아웃 (token_version +1) | ✅ |
| POST | `/auth/refresh` | Access Token 재발급 | ❌ (Refresh Token) |
| GET | `/auth/face/registrations` | 얼굴 등록 현황 조회 | ✅ |
| POST | `/auth/face/register` | 얼굴 embedding 등록 | ✅ |
| DELETE | `/auth/face/{employee_no}` | 얼굴 embedding 삭제 | ✅ hr_admin |
| GET | `/auth/users/{employee_no}` | 사용자 프로필 조회 | ✅ |
| POST | `/auth/users` | 신규 직원 계정 생성 | ✅ hr_admin |
| PATCH | `/auth/users/{employee_no}/password` | 비밀번호 변경 | ✅ 본인만 |
| PATCH | `/auth/users/{employee_no}/line` | worker line_id 수정 | ✅ hr_admin |
| PATCH | `/auth/users/{employee_no}/deactivate` | 퇴사 처리 | ✅ hr_admin |
| PATCH | `/auth/users/{employee_no}/unlock` | 계정 잠금 해제 | ✅ hr_admin |

---

## 15. API 요청/응답 스키마 (schema.py 기준)

### POST /auth/login

```json
Request:
{
  "employee_no": "1001",
  "password": "19960417"
}

Response (200):
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "employee_no": "1001"
}
```

### POST /auth/logout *(v13 신규)*

```json
Request:
Authorization: Bearer {access_token}  (Body 없음)

Response (200):
{
  "message": "Logged out successfully."
}
```

### POST /auth/login/face

```json
Request:
{
  "employee_no": null,          // 생략 시 1:N 비교, 입력 시 1:1 비교
  "image_base64": "data:image/jpeg;base64,..."
}

Response (200 — 성공):
{
  "verified": true,
  "message": "Face login successful.",
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "employee_no": "1001"
}

Response (401 — 실패):
{
  "verified": false,
  "message": "Face does not match.",
  "access_token": null,
  "refresh_token": null,
  "token_type": null,
  "employee_no": null
}
```

### POST /auth/refresh

```json
Request (Body):
{
  "refresh_token": "eyJ..."
}

Response (200):
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

### GET /auth/face/registrations

```json
Response (200):
{
  "items": [
    {
      "employee_no": "1001",
      "name": "홍길동",
      "registration_status": "registered"
    },
    {
      "employee_no": "1002",
      "name": "김철수",
      "registration_status": "unregistered"
    }
  ],
  "total": 2,
  "registered_count": 1,
  "unregistered_count": 1
}
```

### POST /auth/face/register

```json
Request:
{
  "employee_no": "1001",
  "image_base64": "data:image/jpeg;base64,..."
}

Response (200):
{
  "employee_no": "1001",
  "registration_status": "registered",
  "message": "Face embedding registered successfully."
}
```

### POST /auth/users

```json
Request:
{
  "employee_no": "1003",
  "name": "이영희",
  "role": "worker",
  "birth_date": "19960417",
  "line_id": 2
}

Response (201):
{
  "employee_no": "1003",
  "name": "이영희",
  "role": "worker",
  "message": "User created successfully."
}
```

### PATCH /auth/users/{employee_no}/line *(v12 신규)*

```json
Request:
{
  "line_id": 3
}

Response (200):
{
  "employee_no": "1001",
  "line_id": 3,
  "message": "Line ID updated successfully."
}
```

### PATCH /auth/users/{employee_no}/password

```json
Request:
{
  "current_password": "19960417",
  "new_password": "newpass123",
  "new_password_confirm": "newpass123"
}

Response (200):
{
  "employee_no": "1001",
  "message": "Password changed successfully. Please log in again."
}
```

---

## 16. 에러 응답 구조

| 상황 | HTTP 코드 | detail 메시지 |
|------|-----------|---------------|
| 사원번호 없음 / 비밀번호 틀림 | 401 | "Invalid employee number or password." |
| 퇴사자 | 403 | "This account has been deactivated." |
| 잠금 계정 | 403 | "This account is locked. Please contact hr_admin." |
| 토큰 만료 / 무효 | 401 | "Token has been invalidated. Please log in again." |
| 토큰 타입 오류 (refresh로 API 접근) | 401 | "Could not validate credentials." |
| 권한 없음 | 403 | "Only hr_admin can [action]." |
| 사원번호 중복 | 409 | "Employee number already exists." |
| birth_date 형식 오류 | 422 | "birth_date must be in YYYYMMDD format." |
| 현재 비밀번호 불일치 | 401 | "Current password is incorrect." |
| 새 비밀번호 불일치 | 400 | "New passwords do not match." |

---

## 17. 권한별 기능 범위

| 기능 | 분류 | hr_admin | manager | quality_manager | worker |
|------|:----:|:--------:|:-------:|:---------------:|:------:|
| 실시간 불량 탐지 화면 (WorkerScreen) | 대시보드 | ❌ | ✅ | ✅ | ✅ 자기 라인만 |
| 품질 분석 대시보드 (QAScreen) | 대시보드 | ❌ | ✅ | ✅ | ❌ |
| 전체 생산 현황 (ManagerScreen) | 대시보드 | ❌ | ✅ | ❌ | ❌ |
| RAG 챗봇 사용 | 대시보드 | ❌ | ✅ | ✅ | ✅ |
| 불량 이력 조회 | 데이터 | ❌ | ✅ | ✅ | ✅ 자기 라인만 |
| 탐지 임계값 변경 | 데이터 | ❌ | ❌ | ✅ | ❌ |
| 로그 CSV 다운로드 | 데이터 | ❌ | ✅ | ✅ | ❌ |
| 시스템 설정 변경 | 데이터 | ❌ | ❌ | ❌ | ❌ |
| 직원 계정 생성 | 계정 | ✅ | ❌ | ❌ | ❌ |
| 퇴사자 처리 (ID_active=False) | 계정 | ✅ | ❌ | ❌ | ❌ |
| 계정 잠금 해제 | 계정 | ✅ | ❌ | ❌ | ❌ |
| 비밀번호 변경 | 계정 | ✅ 본인만 | ✅ 본인만 | ✅ 본인만 | ✅ 본인만 |
| worker line_id 수정 | 계정 | ✅ | ❌ | ❌ | ❌ |
| 얼굴인식 로그인 | 인증 | ✅ | ✅ | ✅ | ✅ |
| 얼굴 등록 현황 조회 | 인증 | ✅ | ✅ | ❌ | ❌ |
| 얼굴 embedding 삭제 | 인증 | ✅ | ❌ | ❌ | ❌ |

---

## 18. 역할 정의 요약

| 역할 | 한국어 | 대상 | 핵심 역할 |
|------|--------|------|-----------|
| `hr_admin` | 인사팀 | 인사 담당자 | 직원 계정 생성·삭제·잠금 해제 전담. 생산/품질 대시보드 접근 없음 |
| `manager` | 총괄관리자 | 부장·사장·차장급 | 전체 라인 생산량·불량 현황 열람. 모든 대시보드 접근 가능. 설정 변경 권한 없음 |
| `quality_manager` | 품질관리자 | 품질 관리 담당자 | 불량 분석·품질 관리 전담. QAScreen·WorkerScreen 열람, 탐지 임계값 조정, CSV 다운로드 가능 |
| `worker` | 작업자 | 현장 작업자 | 자기 라인 WorkerScreen만 접근. 실시간 불량 알림·NG 로그 확인. 다른 라인 열람 불가 |

---

## 19. 미구현 / 향후 과제

| 항목 | 현황 | 비고 |
|------|------|------|
| 얼굴 embedding 삭제 API | ✅ 완료 | `DELETE /auth/face/{employee_no}` — hr_admin 전용 |
| worker line_id 수정 API | ✅ 완료 | `PATCH /auth/users/{employee_no}/line` — hr_admin 전용 |
| Face ID 실패 시 ID/PW fallback UI | ✅ 완료 | 로그인 화면 좌측 ID/PW 폼으로 전환 |
| 카메라 권한 거부 예외 UI | ✅ 완료 | "Camera permission denied or unavailable." 표시 |
| SECRET_KEY fallback 제거 | ✅ 완료 | `.env` 미설정 시 서버 시작 시 `RuntimeError` 발생 |
| seed.py 운영 분리 | ✅ 완료 | `APP_ENV=production` 시 seed 자동 스킵 |
| 인증 관련 logging | ✅ 완료 | `logger.py` — ANSI 색상 콘솔 출력, `docker logs`로 확인 |
| POST /auth/logout API | 미완료 | token_version +1 즉시 무효화 — 백엔드 구현 예정 |
| PyQt6 로그아웃 버튼 연동 | 미완료 | POST /auth/logout 호출 + 인스턴스 변수 초기화 — PyQt6 담당자 |
| PyQt6 비밀번호 변경 버튼 | 미완료 | 작업자 영역 [비밀번호 변경] 버튼 추가 — PyQt6 담당자 |
| 웹앱 로그아웃 토큰 삭제 | 미완료 | localStorage 전체 삭제 + logout API 호출 — 프론트 담당자 |
| 웹앱 비밀번호 변경 UI 위치 | 미결정 | 로그인 화면에서 제거 — 위치 추후 결정 |
| vector_table tsvector → pgvector 전환 | 검토 중 | 현재 기능상 문제 없음. DB 담당자 협의 필요 |
| seed.py 운영용 계정 정보 환경변수 분리 | 미완료 | 현재 하드코딩(`admin` / `admin123`) — 운영 전 필수 분리 |
| auth_logger.propagate 설정 검토 | 미완료 | 루트 로거 중복 출력 가능성 — 운영 환경 로그 확인 후 결정 |

---

*인증 방식: FastAPI + PostgreSQL + JWT (python-jose) + bcrypt (passlib) + InsightFace*
*권한 구조: hr_admin / manager / quality_manager / worker 4단계 RBAC*
*토큰 구조: Access Token 20분 + Refresh Token 12시간 (token_version으로 즉시 무효화)*
*얼굴인식: 서버 매칭 방식 — embedding은 서버 외부로 유출되지 않음*
*최종 수정: v13 — 로그아웃 절 신규 추가, 비밀번호 변경 UI 위치 수정, 로그아웃 흐름 추가, API 목록 갱신*
