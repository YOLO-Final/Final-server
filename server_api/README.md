# server_api

FastAPI + SQLAlchemy 기반 API 서버입니다.

## 프로젝트 구조

```text
src/
	main.py
	lib/
		settings.py
		database.py
	modules/
		items/
			model.py
			schema.py
			crud.py
			router.py
	api/
		v1/
			router.py
```

## 실행 (Docker Compose)

프로젝트 루트에서:

```bash
docker compose up -d --build postgres server_api
```

## 로컬 실행

```bash
pip install -r requirements.txt
uvicorn src.main:app --reload
```

## 주요 엔드포인트

- `GET /health`
- `POST /api/v1/items`
- `GET /api/v1/items`
- `GET /api/v1/items/{item_id}`
- `PUT /api/v1/items/{item_id}`
- `DELETE /api/v1/items/{item_id}`

## DB 설정

기본값은 PostgreSQL(`postgresql+psycopg://rss_user:rss_password@postgres:5432/rss_db`)이며, `.env`의 `DATABASE_URL`로 변경할 수 있습니다.
