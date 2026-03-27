from pydantic_settings import BaseSettings, SettingsConfigDict

from src.lib.env_loader import load_project_dotenv


load_project_dotenv()


class Settings(BaseSettings):
    app_name: str = "Final Project RSS API"
    app_version: str = "0.2.0"
    api_v1_prefix: str = "/api/v1"

    # docker compose 내부 연결 기준 기본값
    database_url: str = (
        "postgresql+psycopg://FP_ADMIN:FP_PASSWORD@postgres:5432/Final_Project_DB"
    )
    gemini_api_key: str | None = None

    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")


settings = Settings()
