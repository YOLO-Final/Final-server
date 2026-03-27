import os
import re
from typing import Iterable, List


_RAW_SECRET_PATTERNS = [
    # OpenAI-style keys
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    # Tavily-style keys
    re.compile(r"\btvly-[A-Za-z0-9_-]{12,}\b"),
    # Generic key/value leaks
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\b\s*[:=]\s*([^\s,;\"']{6,})"),
    # Authorization header leaks
    re.compile(r"(?i)\b(authorization)\b\s*[:=]\s*bearer\s+([A-Za-z0-9._~-]{8,})"),
]


def _mask_secret(value: str) -> str:
    text = str(value or "")
    if len(text) <= 8:
        return "***"
    return f"{text[:4]}***{text[-4:]}"


def _candidate_secret_env_names() -> Iterable[str]:
    prefixes = ("OPENAI_", "SERPER_", "TAVILY_", "GOOGLE_", "VLLM_", "AWS_", "AZURE_")
    for key in os.environ.keys():
        upper = key.upper()
        if upper.endswith(("_KEY", "_TOKEN", "_SECRET", "_PASSWORD", "_PASSWD")):
            yield key
            continue
        if upper.startswith(prefixes) and any(word in upper for word in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            yield key


def _secret_env_values() -> List[str]:
    values: List[str] = []
    seen = set()
    for key in _candidate_secret_env_names():
        value = str(os.getenv(key, "") or "").strip()
        if len(value) < 8:
            continue
        if value in seen:
            continue
        seen.add(value)
        values.append(value)
    return values


def redact_text(text: object) -> str:
    redacted = str(text or "")
    if not redacted:
        return redacted

    for secret in _secret_env_values():
        if secret in redacted:
            redacted = redacted.replace(secret, _mask_secret(secret))

    for pattern in _RAW_SECRET_PATTERNS:
        def _repl(match: re.Match) -> str:
            if len(match.groups()) >= 2:
                head = match.group(1)
                tail = match.group(2)
                return f"{head}={_mask_secret(tail)}"
            return _mask_secret(match.group(0))

        redacted = pattern.sub(_repl, redacted)

    return redacted


def redact_exception(exc: Exception) -> str:
    return redact_text(exc)

