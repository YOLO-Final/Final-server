from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

@lru_cache(maxsize=1)
def load_project_dotenv() -> str:
    """Load the nearest project .env file once and return loaded path (or empty string).

    The result is memoized at module level to avoid repeated filesystem traversal
    during imports/startup.
    """
    lib_dir = Path(__file__).resolve().parent
    src_dir = lib_dir.parent
    server_api_dir = src_dir.parent
    project_root_dir = server_api_dir.parent

    candidates = [
        Path.cwd() / ".env",
        server_api_dir / ".env",
        project_root_dir / ".env",
    ]

    seen = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            load_dotenv(dotenv_path=candidate, override=False)
            return str(candidate)

    return ""
