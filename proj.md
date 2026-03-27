# Final Project RSS 모듈 README

이 문서는 `/home/orugu/Docker/Final_project_rss` 저장소의 백엔드 모듈을 코드 기준으로 정리한 기술 README입니다.
요청하신 "전제 모듈"은 전체 모듈로 해석해서 작성했고, 현재 실제로 라우터에 연결된 모듈과 내부 공통 모듈을 함께 정리했습니다.

## 1. 프로젝트 한눈에 보기

이 프로젝트는 FastAPI 기반 API 서버와 Nginx 정적 웹, PostgreSQL, Redis로 구성된 제조/품질 대시보드 시스템입니다.

- 웹 서버: `nginx`
- API 서버: `server_api`
- DB: `postgres`
- 캐시/브로커 성격의 저장소: `redis`

`compose.yml` 기준 외부 포트:

- `40943`: HTTPS 웹
- `40916`: HTTP 웹
- `40918`: FastAPI 서버
- `40919`: PostgreSQL
- `40917`: Redis

핵심 구성 코드는 아래처럼 연결됩니다.

```python
# server_api/src/main.py
app = FastAPI(title=settings.app_name, version=settings.app_version)

@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        seed_test_admin_user(db)
    ensure_dashboard_dummy_data()

app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
```

즉, 서버 시작 시 다음이 자동으로 수행됩니다.

1. SQLAlchemy 메타데이터 기준 테이블 생성
2. 개발 환경 기본 관리자 계정 시드
3. 대시보드 더미 데이터 보장
4. `/api/v1` 라우터 연결

---

## 2. 실행 구조

### 2-1. 컨테이너 구조

`compose.yml` 기준 서비스 관계는 아래와 같습니다.

```yaml
services:
  webserver:
    ports: ["40916:80", "40943:443"]

  server_api:
    ports: ["40918:8000"]
    volumes:
      - ./server_api/src:/app/src
      - ./.env:/app/.env:ro
    depends_on:
      postgres:
        condition: service_healthy

  postgres:
    ports: ["40919:5432"]

  redis:
    ports: ["40917:6379"]
```

### 2-2. 설치해야 할 목록

이 프로젝트를 올리기 전에 최소한 아래 항목이 준비되어 있어야 합니다.

- Linux PC 또는 Linux 계열 개발 환경
- `git`
- `docker`
- `docker compose`
- 프로젝트 루트 `.env` 파일
- 선택 사항: OpenAI/Gemini API Key

확인 명령:

```bash
git --version
docker --version
docker compose version
```

선택적으로 있으면 좋은 도구:

- `curl`
- `python3`
- `openssl`

### 2-3. 설치 순서

아래 순서대로 준비하면 됩니다.

1. 저장소 받기

```bash
git clone <저장소_URL>
cd Final_project_rss
```

2. Docker 설치 확인

```bash
docker --version
docker compose version
```

3. 프로젝트 루트에 `.env` 준비

최소 예시:

```env
POSTGRES_DB=Final_Project_DB
POSTGRES_USER=FP_ADMIN
POSTGRES_PASSWORD=CHANGE_ME_DB_PASSWORD
DATABASE_URL=postgresql+psycopg://FP_ADMIN:CHANGE_ME_DB_PASSWORD@postgres:5432/Final_Project_DB
SECRET_KEY=CHANGE_ME_TO_LONG_RANDOM_STRING
APP_ENV=development
```

중요 규칙:

- `POSTGRES_PASSWORD`와 `DATABASE_URL` 비밀번호는 같아야 합니다.
- `SECRET_KEY`는 길고 예측 불가능한 값으로 설정해야 합니다.
- AI 기능을 쓸 경우 `OPENAI_API_KEY` 같은 키를 추가합니다.

4. 설정 문법 확인

```bash
docker compose config
```

5. 컨테이너 빌드 및 설치

```bash
docker compose up -d --build
```

이 단계에서 실제로 설치되는 실행 구성은 아래와 같습니다.

- `webserver` 이미지 빌드
- `server_api` 이미지 빌드
- `postgres:16-alpine` 다운로드
- `redis` 이미지 빌드
- 볼륨 `postgres_data`, `redis_data` 생성

6. 실행 상태 확인

```bash
docker compose ps
```

정상 기대 상태:

- `final_project_rss_webserver`
- `final_project_rss_server_api`
- `final_project_rss_postgres`
- `final_project_rss_redis`

### 2-4. 실행 순서

프로젝트 루트에서:

```bash
docker compose up -d --build
```

API 상태 확인:

```bash
curl http://localhost:40918/health
```

정상 응답:

```json
{"status":"ok"}
```

처음 올릴 때 권장 실행 순서는 아래와 같습니다.

1. `.env` 작성
2. `docker compose config`로 설정 검증
3. `docker compose up -d --build`
4. `docker compose ps`로 컨테이너 상태 확인
5. `curl http://localhost:40918/health`로 API 헬스 체크
6. 브라우저에서 `https://localhost:40943/login.html` 접속
7. `admin / admin123` 또는 준비된 계정으로 로그인
8. 대시보드 화면 진입

### 2-5. 서비스 내부 부팅 순서

코드 기준 실제 내부 실행 순서는 아래에 가깝습니다.

1. `postgres` 기동 및 healthcheck 통과
2. `server_api` 컨테이너 시작
3. `.env` 로드
4. FastAPI 앱 생성
5. `Base.metadata.create_all()` 실행
6. 개발 환경이면 기본 `admin` 계정 시드
7. dashboard 더미 데이터 보강
8. `/api/v1` 라우터 연결된 상태로 서비스 시작
9. `webserver`를 통해 HTML/JS 정적 화면 제공

### 2-6. 재실행/중지 순서

재시작:

```bash
docker compose up -d
```

전체 중지:

```bash
docker compose down
```

이미지 재빌드 포함 재실행:

```bash
docker compose up -d --build
```

---

## 3. 백엔드 디렉터리 구조

문서화 대상의 중심은 `server_api/src`입니다.

```text
server_api/src
├── main.py
├── api/v1/router.py
├── lib
│   ├── database.py
│   ├── env_loader.py
│   └── settings.py
├── modules
│   ├── auth
│   ├── common
│   ├── dashboard
│   ├── db
│   ├── llm
│   ├── optimization
│   ├── rag
│   ├── report
│   ├── vision
│   └── voice_interaction
└── scripts
```

라우터 집선은 `server_api/src/api/v1/router.py`에서 이루어집니다.

```python
api_v1_router.include_router(auth_router)
api_v1_router.include_router(dashboard_router)
api_v1_router.include_router(llm_router)
api_v1_router.include_router(items_router)
api_v1_router.include_router(voice_router)
api_v1_router.include_router(optimization_router)
api_v1_router.include_router(vision_router)
api_v1_router.include_router(rag_router)
api_v1_router.include_router(report_router)
```

즉, 현재 외부 API로 노출되는 대표 모듈은 다음 9개입니다.

- `auth`
- `dashboard`
- `llm`
- `db/items`
- `voice_interaction`
- `optimization`
- `vision`
- `rag`
- `report`

---

## 4. 공통 라이브러리 계층

### 4-1. `lib/settings.py`

환경 변수 기반 설정을 담당합니다.

```python
class Settings(BaseSettings):
    app_name: str = "Final Project RSS API"
    app_version: str = "0.2.0"
    api_v1_prefix: str = "/api/v1"
    database_url: str = (
        "postgresql+psycopg://FP_ADMIN:FP_PASSWORD@postgres:5432/Final_Project_DB"
    )
```

핵심 포인트:

- 기본 API prefix는 `/api/v1`
- 기본 DB는 PostgreSQL
- `.env` 값이 있으면 이를 우선 사용

### 4-2. `lib/env_loader.py`

`.env` 로딩 위치를 자동 탐색합니다.

탐색 순서:

1. 현재 작업 디렉터리 `.env`
2. `server_api/.env`
3. 프로젝트 루트 `.env`

### 4-3. `lib/database.py`

SQLAlchemy 엔진과 세션 생명주기를 담당합니다.

```python
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

정리하면:

- 모든 DB 의존 라우터는 `Depends(get_db)`로 세션 주입
- 연결 죽음 감지는 `pool_pre_ping=True`

---

## 5. 서버 시작 시 초기화 동작

### 5-1. 관리자 계정 자동 시드

`server_api/src/modules/db/users/seed.py` 기준, `APP_ENV=production`이 아니면 기본 관리자 계정이 자동 생성됩니다.

```python
UserTable(
    employee_no="admin",
    password_hash=_hash_password("admin123"),
    role="hr_admin",
    id_active=True,
    id_locked=False,
)
```

초기 로그인 계정:

- ID: `admin`
- PW: `admin123`
- 권한: `hr_admin`

주의:

- 운영 환경에서는 이 시드에 의존하면 안 됩니다.
- 실제 배포 전에는 별도 계정 정책이 필요합니다.

### 5-2. 대시보드 더미 데이터 자동 보강

`main.py`에서 `ensure_dashboard_dummy_data()`를 호출합니다.

의도:

- 대시보드 화면이 빈 상태로 뜨지 않도록 샘플/시나리오 데이터를 준비
- 문서 및 시연 환경에서 worker, QA, manager, promo 화면을 바로 확인 가능

---

## 6. 전체 모듈 맵

| 모듈 | 기본 경로 | 역할 | 비고 |
|---|---|---|---|
| Auth | `/api/v1/auth` | 로그인, 얼굴 인증, 토큰, 사용자 관리 | 실사용 핵심 모듈 |
| Dashboard | `/api/v1/dashboard` | 역할별 KPI/차트/상세 데이터 | 실사용 핵심 모듈 |
| LLM | `/api/v1/llm` | 채팅, 메모리, 지식 파일, STT/TTS/이미지 | 외부 API 의존 |
| Items | `/api/v1/items` | 샘플 CRUD | 예제/테스트 성격 |
| Vision | `/api/v1/vision` | 카메라 상태, 프레임 업로드, 핸드셰이크 | 온프렘 연동 포함 |
| Report | `/api/v1/report` | 결과 요약, PDF 보고서 | DB 집계 기반 |
| RAG | `/api/v1/rag` | 상태 체크 | placeholder |
| Optimization | `/api/v1/optimization` | 상태 체크 | placeholder |
| Voice | `/api/v1/voice` | 상태 체크 | placeholder |
| Common | 내부 모듈 | RBAC/Audit 보조 | placeholder |
| DB 통합 모델 | 내부 모듈 | 레거시/통합 스키마 참조 | 현재 런타임 핵심 아님 |

---

## 7. Auth 모듈

### 7-1. 역할

`auth` 모듈은 로그인과 계정 제어를 담당하는 가장 중요한 모듈입니다.

주요 기능:

- 비밀번호 로그인
- 얼굴 로그인
- 토큰 재발급
- 얼굴 등록/삭제
- 사용자 생성
- 계정 잠금 해제
- 계정 비활성화
- 비밀번호 변경
- 작업자 라인 배정
- 로그아웃

### 7-2. 대표 엔드포인트

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/login/face`
- `POST /api/v1/auth/refresh`
- `GET /api/v1/auth/face/registrations`
- `POST /api/v1/auth/face/register`
- `DELETE /api/v1/auth/face/{employee_no}`
- `POST /api/v1/auth/users`
- `PATCH /api/v1/auth/users/{employee_no}/unlock`
- `PATCH /api/v1/auth/users/{employee_no}/deactivate`
- `PATCH /api/v1/auth/users/{employee_no}/password`
- `PATCH /api/v1/auth/users/{employee_no}/line`
- `POST /api/v1/auth/logout`

### 7-3. 핵심 코드 흐름

비밀번호 로그인 라우터:

```python
@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    return login_with_password(
        db=db,
        employee_no=request.employee_no,
        password=request.password,
    )
```

서비스 계층의 핵심 규칙:

```python
if not _verify_password(password, stored_password):
    user_row.login_fail_count = (user_row.login_fail_count or 0) + 1
    if user_row.login_fail_count >= 5:
        user_row.id_locked = True
        user_row.token_version = (user_row.token_version or 0) + 1
```

의미:

- 로그인 5회 실패 시 계정 잠금
- 잠금과 동시에 `token_version` 증가
- 기존 토큰 강제 무효화

### 7-4. 인증 특징

1. 비밀번호는 현재 `bcrypt` 기반
2. 과거 `SHA-256` 해시는 성공 로그인 시 자동 승격
3. 비활성 계정과 잠금 계정은 비밀번호 확인 전 차단
4. 관리자 기능은 `hr_admin` 권한으로 제한

### 7-5. Face ID 동작

얼굴 로그인은 두 모드가 있습니다.

- `employee_no` 제공: 1:1 비교
- `employee_no` 미제공: 등록된 전체 얼굴과 1:N 비교

기본 임계값:

```python
raw = os.getenv("FACE_MATCH_THRESHOLD", "0.30").strip()
```

즉, 얼굴 인식 민감도는 `FACE_MATCH_THRESHOLD`로 조정 가능합니다.

### 7-6. 예시 요청

```bash
curl -X POST http://localhost:40918/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"employee_no":"admin","password":"admin123"}'
```

---

## 8. Dashboard 모듈

### 8-1. 역할

대시보드 모듈은 worker, QA, manager, promo 화면에 필요한 KPI와 차트 데이터를 제공합니다.

지원 화면:

- `worker`
- `qa`
- `manager`
- `promo`

### 8-2. 대표 엔드포인트

- `GET /api/v1/dashboard/status`
- `GET /api/v1/dashboard/kpis?screen=worker|qa|manager|promo`
- `GET /api/v1/dashboard/datasets?screen=...`
- `GET /api/v1/dashboard/detail?screen=...&detailId=...`
- `GET /api/v1/dashboard/web/worker`
- `GET /api/v1/dashboard/web/qa`
- `GET /api/v1/dashboard/web/manager`
- `GET /api/v1/dashboard/web/promo`

### 8-3. 핵심 코드 구조

라우터는 요청 계약을 고정하고, 서비스 계층이 응답 번들을 조립합니다.

```python
@router.get("/web/worker", response_model=WorkerWebDashboardResponse)
def read_web_worker_dashboard(...):
    return get_web_worker_dashboard(...)
```

서비스 계층의 특징:

- 화면별 `response_model` 분리
- 공통 필터: `tz`, `factory`, `line`, `shift`, `period`, `date_from`, `date_to`
- 상세 모달용 `detailId/targetType/targetId` 검증

### 8-4. 중요한 비즈니스 규칙

작업자 계정은 임의의 라인을 조회하지 못하고, 로그인 사용자 라인으로 강제됩니다.

```python
if role in {"worker", "operator"}:
    line_code = get_employee_line_code(employee_no)
    filters["line"] = line_code
```

이 규칙 덕분에 worker 화면은 본인 배정 라인 중심으로만 조회됩니다.

### 8-5. 날짜 처리 규칙

대시보드 서비스는 날짜 범위 검증을 포함합니다.

- `date_from > date_to` 이면 400
- 최대 31일 범위만 허용
- 단일 날짜면 범위 조회 대신 기준일 조회처럼 처리

### 8-6. 상태 응답 예시

대시보드 상태 API는 지원 화면과 라이브 데이터 존재 여부를 알려줍니다.

```python
return {
    "module": "dashboard",
    "screens": sorted(VALID_SCREENS),
    "detailEndpoint": "/api/v1/dashboard/detail",
}
```

---

## 9. LLM 모듈

### 9-1. 역할

LLM 모듈은 채팅, 지식 파일 인덱싱, 메모리 관리, STT/TTS, 이미지 생성 기능을 담당합니다.

하위 구성:

- `llm_chat_api.py`: 채팅/메모리/지식 파일
- `llm_media_api.py`: STT/TTS/이미지 생성
- `llm_result_api.py`: 단발성 비스트리밍 생성
- `llm_question.py`: 추천 질문
- `services/*`: 실제 OpenAI/knowledge 처리

### 9-2. 대표 엔드포인트

- `POST /api/v1/llm/chat`
- `GET /api/v1/llm/memory`
- `POST /api/v1/llm/memory/reset`
- `GET /api/v1/llm/knowledge`
- `GET /api/v1/llm/knowledge/files`
- `POST /api/v1/llm/knowledge/reindex`
- `POST /api/v1/llm/upload`
- `POST /api/v1/llm/stt`
- `POST /api/v1/llm/tts`
- `POST /api/v1/llm/image`
- `POST /api/v1/llm/result`
- `GET /api/v1/llm/recommended-questions`

### 9-3. 채팅 API 특징

```python
@chat_router.post("/chat")
async def chat(
    message: str = Form(""),
    provider: str = Form("openai"),
    web_search: str = Form("false"),
    disable_auto_web: str = Form("true"),
    reset_memory: str = Form("false"),
    empathy_level: str = Form("balanced"),
    language: str = Form("ko"),
    session_id: str = Form("default"),
):
```

특징:

- Form 기반 입력
- 세션별 메모리 지원
- 응답은 `StreamingResponse`
- 서버 시작 시 지식 인덱싱 백그라운드 수행

### 9-4. 지식 파일 처리

업로드 허용 확장자:

- `.txt`
- `.pdf`
- `.png`
- `.jpg`
- `.jpeg`
- `.webp`
- `.bmp`
- `.gif`

업로드 후에는 지식 저장소를 즉시 다시 인덱싱합니다.

```python
with path.open("wb") as buffer:
    shutil.copyfileobj(file.file, buffer)

chunks = update_knowledge()
```

### 9-5. 미디어 API 특징

STT:

- OpenAI provider만 지원
- 파일 크기 하한/상한 검증
- 기본 모델: `gpt-4o-mini-transcribe`

TTS:

- 기본 모델: `gpt-4o-mini-tts`
- 속도 범위: `0.25 ~ 4.0`
- 출력 포맷: `mp3`, `wav`, `opus`, `flac`, `aac`, `pcm`

이미지 생성:

- 기본 모델: `gpt-image-1`
- 폴백 모델: `dall-e-3`

### 9-6. 단발성 생성 API

```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    temperature=request.temperature,
    max_tokens=request.max_output_tokens,
    messages=[{"role": "user", "content": request.prompt}],
)
```

즉, `/result`는 에이전트 전체 파이프라인이 아니라 가벼운 1회성 텍스트 생성용입니다.

---

## 10. Vision 모듈

### 10-1. 역할

Vision 모듈은 카메라 장치 등록, 프레임 업로드, 오버레이 이미지 저장, 온프렘 연동, 카메라 상태 조회를 담당합니다.

### 10-2. 대표 엔드포인트

- `GET /api/v1/vision/status`
- `GET /api/v1/vision/stream/state`
- `GET|POST /api/v1/vision/stream/heartbeat`
- `GET /api/v1/vision/interop/ping`
- `GET /api/v1/vision/cameras`
- `GET /api/v1/vision/overlay-counts/today`
- `POST /api/v1/vision/cameras/{camera_id}/device`
- `POST /api/v1/vision/interop/handshake`
- `GET /api/v1/vision/interop/handshake/{camera_id}`
- `POST /api/v1/vision/cameras/{camera_id}/frames`
- `POST /api/v1/vision/inspect`

### 10-3. 토큰 검증 규칙

카메라 연동 요청은 헤더 기반 토큰 검증을 사용합니다.

```python
expected_token = (
    os.getenv("VISION_CAMERA_TOKEN")
    or os.getenv("VISION_API_TOKEN")
    or ""
).strip()
```

관련 환경 변수:

- `VISION_ALLOW_NO_TOKEN`
- `VISION_CAMERA_TOKEN`
- `VISION_API_TOKEN`
- `VISION_MAX_FRAME_BYTES`

### 10-4. 프레임 업로드 규칙

지원 콘텐츠 타입:

- `image/jpeg`
- `image/jpg`
- `image/png`

기본 최대 업로드 크기:

- `3 * 1024 * 1024` bytes

프레임 업로드 흐름:

```python
payload = await file.read()
result = await asyncio.to_thread(ingest_overlay_frame, camera_id, payload, 0)
return {"ok": True, **result}
```

즉, 무거운 처리 로직은 별도 스레드로 넘기고 API는 즉시 응답합니다.

### 10-5. 호환용 레거시 API

`/inspect`는 multipart 파일뿐 아니라 JSON base64 이미지도 허용합니다.

이유:

- 기존 온프렘 클라이언트와 호환 유지
- 점진적 마이그레이션 지원

---

## 11. Report 모듈

### 11-1. 역할

Report 모듈은 검사 결과 요약과 PDF 보고서 생성을 담당합니다.

### 11-2. 대표 엔드포인트

- `GET /api/v1/report/status`
- `GET /api/v1/report/result-summary?target_date=YYYY-MM-DD`
- `GET /api/v1/report/pdf?target_date=YYYY-MM-DD`

### 11-3. 데이터 집계 방식

서비스는 SQLAlchemy ORM보다 SQL 텍스트 질의를 적극적으로 사용합니다.

```python
row = db.execute(text(stmt), params or {}).mappings().first()
```

`get_result_summary()`가 계산하는 대표 항목:

- 총 검사 건수
- OK 건수
- NG 건수
- 수율(`yield_pct`)
- NG 분포
- 모델 정보
- 시스템 상태

### 11-4. NG 분포 가공

불량 코드를 버킷 형태로 다시 집계합니다.

```python
label_map = [
    "short",
    "open",
    "mouse_bite",
    "spur",
    "missing_hole",
    "spurious_copper",
]
```

즉, 보고서는 raw defect code를 사람이 읽을 수 있는 defect label 집계로 변환합니다.

### 11-5. PDF 생성 흐름

- DB에서 결과 요약 조회
- `build_report_pdf()`에 전달
- `application/pdf`로 inline 응답

---

## 12. Items 모듈

### 12-1. 역할

`db/items` 모듈은 전형적인 CRUD 예제이자 기본 DB 패턴 예시입니다.

### 12-2. 대표 엔드포인트

- `POST /api/v1/items`
- `GET /api/v1/items`
- `GET /api/v1/items/{item_id}`
- `PUT /api/v1/items/{item_id}`
- `DELETE /api/v1/items/{item_id}`

### 12-3. 특징

- `Depends(get_db)` 사용 예시
- 404 처리 예시 포함
- 생성/조회/수정/삭제 패턴이 단순해 신규 모듈의 출발점으로 적합

예시:

```python
@router.get("/{item_id}", response_model=ItemRead)
def get_item_endpoint(item_id: int, db: Session = Depends(get_db)):
    item = crud.get_item(db=db, item_id=item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
```

---

## 13. Placeholder 성격 모듈

아래 모듈들은 현재 실기능보다는 연결 확인용 상태 API 중심입니다.

### 13-1. Optimization

- 경로: `/api/v1/optimization`
- 엔드포인트: `GET /status`
- 목적: 최적화 모듈 생존 확인

### 13-2. RAG

- 경로: `/api/v1/rag`
- 엔드포인트: `GET /status`
- 목적: RAG 연동 상태 확인

### 13-3. Voice Interaction

- 경로: `/api/v1/voice`
- 엔드포인트: `GET /status`
- 목적: 음성 모듈 상태 확인

이 세 모듈은 현재 확장 여지를 남겨 둔 skeleton에 가깝습니다.

---

## 14. 내부 공통 모듈

### 14-1. `modules/common/rbac.py`

현재는 placeholder 수준입니다.

```python
def require_role_placeholder(role: str) -> None:
    if not role:
        raise HTTPException(status_code=403, detail="Role is required")
```

의미:

- 완전한 RBAC 엔진은 아직 아님
- 실제 권한 판단 핵심은 `auth` + JWT 흐름에 더 가깝습니다

### 14-2. `modules/common/audit.py`

감사 로그 구조의 뼈대만 준비되어 있습니다.

```python
def audit_log_placeholder(actor: str, action: str) -> dict:
    return {
        "actor": actor,
        "action": action,
        "message": "Audit logging skeleton. Connect DB writer later.",
    }
```

정리:

- 현재는 DB 영속화 없음
- 향후 관리자 작업 이력, 로그인 추적, 운영 이벤트 추적에 확장 가능

---

## 15. DB 통합 모델 모듈

`modules/db/integrated_models.py`는 통합 스키마 참고용 파일입니다.

코드 주석상 중요한 문구:

```python
# This module is no longer part of the current web_dashboard table-registration path.
# For web_dashboard runtime and init_db, use src.modules.dashboard.db.model instead.
```

즉:

- 현재 웹 대시보드 런타임의 핵심 테이블 등록 경로는 아님
- 통합 모델 레퍼런스 또는 별도 관리 스키마 문서 역할

포함된 엔터티 예:

- `Factory`
- `ProductModel`
- `Line`
- `Equipment`
- `Employee`
- `ProductionRecord`
- `EquipmentStatusHistory`
- `InspectionResult`
- `DefectResult`

---

## 16. 환경 변수 정리

현재 코드 기준으로 자주 중요한 환경 변수는 아래와 같습니다.

### 16-1. 공통

```env
DATABASE_URL=postgresql+psycopg://FP_ADMIN:FP_PASSWORD@postgres:5432/Final_Project_DB
APP_NAME=Final Project RSS API
APP_VERSION=0.2.0
API_V1_PREFIX=/api/v1
```

### 16-2. 인증

- `SECRET_KEY`
- `FACE_MATCH_THRESHOLD`

### 16-3. LLM

- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `LLM_MODEL`
- `EMBEDDING_MODEL`
- `OPENAI_STT_MODEL`
- `OPENAI_TTS_MODEL`
- `OPENAI_IMAGE_MODEL`

### 16-4. Vision

- `VISION_ALLOW_NO_TOKEN`
- `VISION_CAMERA_TOKEN`
- `VISION_API_TOKEN`
- `VISION_MAX_FRAME_BYTES`

### 16-5. 운영 분기

- `APP_ENV=production`이면 기본 admin 시드 비활성화

---

## 17. 요청 흐름 예시

### 17-1. 로그인 후 대시보드 조회

1. `POST /api/v1/auth/login`
2. access token 획득
3. `Authorization: Bearer <token>` 헤더로 대시보드 호출
4. `GET /api/v1/dashboard/web/worker` 또는 `/qa`, `/manager`, `/promo`

예시:

```bash
TOKEN=$(curl -s -X POST http://localhost:40918/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"employee_no":"admin","password":"admin123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s http://localhost:40918/api/v1/dashboard/web/manager \
  -H "Authorization: Bearer $TOKEN"
```

### 17-2. 카메라 연동 흐름

1. `POST /api/v1/vision/interop/handshake`
2. `POST /api/v1/vision/cameras/{camera_id}/device`
3. `POST /api/v1/vision/cameras/{camera_id}/frames`
4. 대시보드/리포트에서 집계 데이터 반영

### 17-3. LLM 지식 파일 흐름

1. `POST /api/v1/llm/upload`
2. 서버가 지식 폴더에 파일 저장
3. `update_knowledge()` 실행
4. `POST /api/v1/llm/chat`에서 갱신된 지식 사용

---

## 18. 현재 코드 기준 장점과 주의점

### 장점

- 모듈 경계가 비교적 명확함
- 라우터와 서비스 계층 분리가 잘 되어 있음
- 대시보드/인증/LLM/비전 기능이 각자 독립적으로 확장 가능
- 개발 환경에서 바로 확인 가능한 자동 시드가 있음

### 주의점

- `common`, `optimization`, `rag`, `voice_interaction`은 아직 skeleton 성격이 강함
- 기본 admin 계정은 개발 편의용이므로 운영에 그대로 쓰면 위험
- 대시보드 일부는 더미/시나리오 데이터에 기대고 있음
- LLM 기능은 외부 API 키와 모델 권한 상태에 직접 영향을 받음

---

## 19. 추천 문서화/개선 방향

이 저장소를 다음 단계로 정리하려면 아래 순서가 좋습니다.

1. `proj.md`를 기준 문서로 두고, 사용자용 매뉴얼과 개발자용 README를 분리
2. 각 모듈별 request/response 예제를 Swagger 기준으로 보강
3. `common`의 RBAC/Audit를 실제 구현으로 승격
4. placeholder 모듈(`rag`, `optimization`, `voice`)의 로드맵 명시
5. 운영용 `.env.example`를 확장해서 필수 키를 더 명확히 표시

---

## 20. 핵심 파일 요약

빠르게 봐야 할 파일만 꼽으면 아래 순서가 가장 좋습니다.

1. `server_api/src/main.py`
2. `server_api/src/api/v1/router.py`
3. `server_api/src/modules/auth/router.py`
4. `server_api/src/modules/auth/service.py`
5. `server_api/src/modules/dashboard/router.py`
6. `server_api/src/modules/dashboard/service.py`
7. `server_api/src/modules/llm/llm_chat_api.py`
8. `server_api/src/modules/vision/router.py`
9. `server_api/src/modules/report/service.py`
10. `compose.yml`

이 순서대로 읽으면 "서버 시작 -> 라우터 연결 -> 인증 -> 대시보드 -> AI/비전 -> 리포트" 흐름이 잡힙니다.
