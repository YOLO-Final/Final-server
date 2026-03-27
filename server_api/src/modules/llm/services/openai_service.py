"""LLM 모듈 전반에서 공용으로 쓰는 OpenAI 클라이언트/초기화 헬퍼."""

import os
from functools import lru_cache
from typing import Optional, Tuple

from src.lib.env_loader import load_project_dotenv

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None

load_project_dotenv()


def to_bool(value: Optional[str], default: bool = False) -> bool:
    """HTML/Form에서 자주 들어오는 불리언 문자열을 Python bool로 변환한다."""
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def _get_cached_openai_client(api_key: str):
    # API 키 단위로 클라이언트를 캐시해 반복 요청에서 SDK 인스턴스를 재사용한다.
    return OpenAI(api_key=api_key)


def get_openai_client() -> Tuple[object, str]:
    """성공 시 설정된 OpenAI 클라이언트와 빈 에러 문자열을 반환한다."""
    if OpenAI is None:
        return None, "The openai package is not installed."

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None, "OPENAI_API_KEY is not configured."

    # 요청마다 새 클라이언트를 만들지 않도록 재사용한다.
    # 키가 바뀌면 `lru_cache(maxsize=1)`가 새 값으로 교체된다.
    return _get_cached_openai_client(api_key), ""
