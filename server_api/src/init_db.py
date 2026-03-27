from src.lib.database import Base, engine

# 모델 모듈 import는 SQLAlchemy 메타데이터 등록(side effect) 목적입니다.
# web_dashboard 기준 테이블 등록 경로는 main.py와 동일하게 dashboard.db.model을 사용합니다.
from src.modules.db.items.db import model as _item_model  # noqa: F401
from src.modules.db.users.db import model as _user_model  # noqa: F401
from src.modules.dashboard.db import model as _dashboard_model  # noqa: F401

def init_db() -> None:
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()
    print("All tables created successfully.")
