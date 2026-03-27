# Final Project RSS 사용 매뉴얼 (비개발자용)

이 문서는 개발 지식이 없어도 시스템을 실행하고, 화면을 열고, 기본 점검까지 할 수 있도록 작성되었습니다.

## 1. 이 시스템이 하는 일

- 생산/품질/운영 현황을 웹 대시보드로 보여줍니다.
- 역할별 화면(작업자, QA, 관리자, 공용송출)을 제공합니다.
- 브라우저로 접속해서 확인합니다.

## 2. 준비물

- Linux PC 1대
- Docker / Docker Compose 설치 완료
- 인터넷 연결(외부 API를 쓰는 기능이 있을 수 있음)

확인 명령어:

```bash
docker --version
docker compose version
```

## 3. 최초 1회 확인 (.env) - 중요

프로젝트 루트에 `.env` 파일이 있어야 하며, 아래 항목은 반드시 채워야 합니다.

### 3-1. 필수 항목 (없으면 실행 실패 가능)

```env
# DB
POSTGRES_DB=Final_Project_DB
POSTGRES_USER=FP_ADMIN
POSTGRES_PASSWORD=CHANGE_ME_DB_PASSWORD
DATABASE_URL=postgresql+psycopg://FP_ADMIN:CHANGE_ME_DB_PASSWORD@postgres:5432/Final_Project_DB

# JWT 인증
SECRET_KEY=CHANGE_ME_TO_LONG_RANDOM_STRING
```

작성 규칙:

1. `POSTGRES_PASSWORD`와 `DATABASE_URL`의 비밀번호는 반드시 동일해야 합니다.
2. `SECRET_KEY`는 최소 32자 이상 긴 랜덤 문자열을 권장합니다.
3. 값에 공백을 넣지 않습니다.

### 3-2. 선택 항목 (AI 기능 사용 시)

```env
OPENAI_API_KEY=
GEMINI_API_KEY=
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
LLM_KNOWLEDGE_PATH=/app/src/modules/llm/sample/knowledge_base
```

설명:

- 대시보드 기본 기능은 DB/인증 설정만으로도 동작합니다.
- OpenAI/Gemini 키가 비어 있으면 일부 AI 관련 기능만 제한될 수 있습니다.

### 3-3. 안전한 `SECRET_KEY` 생성 방법

아래 명령 중 하나를 사용해 생성한 값을 `SECRET_KEY=` 뒤에 넣으세요.

```bash
openssl rand -hex 32
```

또는

```bash
python - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
```

### 3-4. 저장 후 빠른 점검

1. `.env` 저장
2. 아래 명령 실행

```bash
docker compose config
```

이 명령이 오류 없이 끝나면 문법 문제는 없는 상태입니다.

### 3-5. 보안 주의

- `.env` 파일은 절대 메신저/이메일/문서로 공유하지 않습니다.
- 키가 노출된 적이 있으면 즉시 새 키로 교체합니다.
- 운영용 비밀번호는 예시값(`FP_PASSWORD`)을 그대로 쓰지 않습니다.

## 4. 실행 방법 (가장 중요)

프로젝트 루트에서 아래 명령을 순서대로 실행합니다.

```bash
docker compose up -d --build
```

정상 실행 확인:

```bash
docker compose ps
```

아래 4개 서비스가 `Up` 상태면 정상입니다.

- `webserver`
- `server_api`
- `postgres`
- `redis`

## 5. 접속 주소

같은 PC에서 브라우저로 접속:

- 메인(HTTPS 권장): `https://localhost:40943`
- 메인(HTTP): `http://localhost:40916`
- API 직접 확인: `http://localhost:40918`

자주 쓰는 페이지:

- 로그인: `https://localhost:40943/login.html`
- 대시보드: `https://localhost:40943/web_dashboard.html`
- 자동 화면: `https://localhost:40943/auto.html`

참고: 사설 인증서 경고가 뜨면 "고급" -> "계속 진행"을 선택합니다.

## 6. 화면 사용 순서 (비개발자 추천 흐름)

1. `login.html`에서 로그인
2. `web_dashboard.html` 진입
3. 상단 탭으로 역할 전환
   - 작업자: 현재 이상/알람/설비 상태 빠른 확인
   - QA: 불량률, 재검 큐, 원인코드 확인
   - 관리자: OEE/달성률/리스크 우선순위 확인
   - 공용송출: 회의실/현장 모니터용 요약 화면
4. 필터(공장/라인/기간) 변경 후 지표 변화를 확인

## 7. 매일 점검 체크리스트

아래 5가지만 보면 운영 상태를 빠르게 확인할 수 있습니다.

1. 컨테이너 상태: `docker compose ps`에서 모두 `Up`
2. 웹 접속: `https://localhost:40943` 접속 가능
3. 대시보드 로딩: `web_dashboard.html`에서 카드/차트 표시
4. API 상태: `http://localhost:40918/health` 응답 확인
5. 갱신 시간: 화면 상단 마지막 갱신 시각이 계속 업데이트되는지 확인

## 8. 자주 생기는 문제와 해결

### 8-1. 페이지가 열리지 않음

확인:

```bash
docker compose ps
```

조치:

- `webserver`가 내려가 있으면 전체 재기동

```bash
docker compose restart webserver
```

### 8-2. 데이터가 비어 보임

확인:

```bash
docker compose logs --tail=100 server_api
```

조치:

- `postgres` 상태 확인
- `.env`의 DB 정보 확인
- 필요 시 전체 재시작

```bash
docker compose down
docker compose up -d --build
```

### 8-3. DB 연결 오류

확인:

- `.env`의 `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DATABASE_URL`
- `postgres` 컨테이너 상태

조치:

```bash
docker compose restart postgres server_api
```

### 8-4. 포트 충돌 오류

증상:

- `40916`, `40943`, `40918`, `40919`, `40917` 중 일부가 이미 사용 중

조치:

- 해당 포트를 쓰는 다른 프로그램 종료
- 또는 `compose.yml` 포트를 다른 번호로 변경 후 재실행

## 9. 종료/재시작 방법

종료:

```bash
docker compose down
```

재시작:

```bash
docker compose up -d
```

완전 새로 빌드:

```bash
docker compose up -d --build
```

## 10. 운영 시 주의사항

- `.env`와 인증서 파일은 외부 전달 금지
- 관리자 계정/비밀번호는 메신저 공유 금지
- 시연 전에는 반드시 5분 전에 재기동 후 화면 확인
- 장시간 송출 시 공용송출 화면(`web_dashboard.html`의 공용 탭 또는 `auto.html`) 사용 권장

## 11. 빠른 실행 요약 (복붙용)

```bash
cd /home/orugu/Docker/Final_project_rss
docker compose up -d --build
docker compose ps
```

브라우저 접속:

- `https://localhost:40943/web_dashboard.html`
- `https://localhost:40943/login.html`

## 12. 모듈별 상세 문서

기능 단위로 확인할 때는 아래 문서를 참고하세요.

- `module_auth.md`: 로그인, 토큰, 얼굴인증 관련
- `module_dashboard.md`: 역할별 KPI/데이터셋 API
- `module_vision.md`: 카메라 프레임/오버레이/연동
- `module_llm.md`: 챗봇/STT/TTS/이미지 생성
- `module_report.md`: 요약 조회/보고서 PDF
- `module_rag.md`: RAG 상태 점검
- `module_optimization.md`: 최적화 모듈 상태
- `module_voice_interaction.md`: 음성 인터랙션 상태
- `module_db_items.md`: 샘플 Item CRUD API
- `module_common.md`: 공통 RBAC/Audit 유틸

## 12-1. 코드 관점 문서 (개발자용)

코드 구조/수정 포인트를 확인할 때는 `manuals/code` 문서를 참고하세요.

- `code/README.md`: 코드 문서 인덱스
- `code/server_overview.md`: 서버 전반 구조
- `code/module_auth_code.md`
- `code/module_dashboard_code.md`
- `code/module_vision_code.md`
- `code/module_llm_code.md`
- `code/module_report_code.md`
- `code/module_rag_code.md`
- `code/module_optimization_code.md`
- `code/module_voice_interaction_code.md`
- `code/module_db_items_code.md`
- `code/module_common_code.md`

## 13. 운영자용 빠른 장애 분류

### 13-1. 로그인 실패

- 확인: 비밀번호 로그인도 실패하는지
- 조치: `server_api` 로그에서 인증 오류 확인
- 추가: 최근 `SECRET_KEY`를 바꿨다면 재로그인 필요

### 13-2. 대시보드 숫자 미갱신

- 확인: 화면 상단 갱신시각이 멈췄는지
- 조치: `server_api`, `postgres`, `redis` 상태를 먼저 점검
- 추가: DB 연결 문자열(`DATABASE_URL`) 오타 여부 확인

### 13-3. AI 기능만 실패

- 증상: 챗봇/STT/TTS/이미지 기능만 오류
- 확인: `.env`의 `OPENAI_API_KEY`, `GEMINI_API_KEY`
- 조치: 키 교체 후 `docker compose restart server_api`

### 13-4. 카메라 연동 실패

- 확인: `/api/v1/vision/*` 요청이 401인지 확인
- 조치: `VISION_CAMERA_TOKEN` 또는 `VISION_API_TOKEN` 값 점검
- 추가: 테스트 환경이면 `VISION_ALLOW_NO_TOKEN=true`로 임시 확인 가능

### 13-5. 보고서 PDF 미출력

- 확인: `/api/v1/report/result-summary`는 정상인지
- 조치: DB 데이터 여부 확인 후 `/api/v1/report/pdf` 재호출

---
문의 시 전달할 정보(장애 대응 속도 향상):

- 발생 시각
- 어떤 화면 URL에서 문제 발생했는지
- `docker compose ps` 결과
- `docker compose logs --tail=100 server_api` 결과
