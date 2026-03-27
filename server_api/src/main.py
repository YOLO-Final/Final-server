from fastapi import FastAPI
from sqlalchemy.orm import Session

from src.api.v1.router import api_v1_router
from src.lib.database import Base, engine
from src.lib.env_loader import load_project_dotenv
from src.lib.settings import settings
from src.modules.auth.db.model import FaceEmbeddingTable, VectorTable  # noqa: F401
from src.modules.db.items.db.model import Item  # noqa: F401
from src.modules.db.users.db.model import UserTable  # noqa: F401
from src.modules.db.users.seed import seed_test_admin_user
from src.modules.dashboard.db import model as dashboard_models  # noqa: F401
from src.scripts.generate_wed_dashboard_dummy import ensure_dashboard_dummy_data

load_project_dotenv()

app = FastAPI(title=settings.app_name, version=settings.app_version)


@app.on_event("startup")
def on_startup() -> None:
    # 등록된 모델 메타데이터 기준으로 테이블을 자동 생성합니다.
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        seed_test_admin_user(db)

    try:
        seeded = ensure_dashboard_dummy_data()
        if seeded:
            print("[startup] wed_dashboard dummy data seeded for 2026-03-20..2026-03-25")
    except Exception as exc:
        print(f"[startup] wed_dashboard dummy seed skipped: {exc}")


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
