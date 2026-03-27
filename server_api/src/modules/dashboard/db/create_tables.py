from src.lib.database import Base, engine

# 모델 import가 되어야 Base.metadata에 테이블이 등록됩니다.
from src.modules.dashboard.db import model as dashboard_models  # noqa: F401


def create_dashboard_tables() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    create_dashboard_tables()
    print("Dashboard tables created or already exist.")
