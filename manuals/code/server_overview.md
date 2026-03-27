# Server Code Overview

## 1. 엔트리 포인트
- `server_api/src/main.py`
- FastAPI 앱 생성 후 `/health` 등록
- `api_v1_router`를 `settings.api_v1_prefix`(기본 `/api/v1`)로 마운트

## 2. 부팅 시 동작
1. `.env` 로드 (`load_project_dotenv()`)
2. SQLAlchemy 메타데이터 기반 테이블 생성 (`Base.metadata.create_all`)
3. 테스트 관리자 계정 시드 (`seed_test_admin_user`)

## 3. 라우팅 집계
- `server_api/src/api/v1/router.py`
- 포함 순서:
  - auth
  - dashboard
  - llm
  - items
  - voice
  - optimization
  - vision
  - rag
  - report

## 4. 설정/환경변수
- `server_api/src/lib/settings.py`
- Pydantic `BaseSettings` 사용
- 핵심 값:
  - `database_url`
  - `gemini_api_key`
  - `api_v1_prefix`

## 5. DB 계층
- `server_api/src/lib/database.py`
- `engine = create_engine(..., pool_pre_ping=True)`
- `SessionLocal` + `get_db()` 의존성 패턴

## 6. 코드 수정 가이드
- 라우트 추가: 각 모듈 `router.py` -> `api/v1/router.py` include 확인
- DB 모델 추가: 모델 import 경로가 부팅 시 메타데이터에 포함되는지 확인
- 설정값 추가: `settings.py` 필드 추가 + `.env` 문서 동기화

## 7. 빠른 점검 포인트
- 헬스체크: `GET /health`
- API 공통 prefix: `/api/v1`
- 인증 의존성: 모듈별 `Depends(get_current_user)` 여부 확인
