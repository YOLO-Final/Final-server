"""저수준 Gemini 텍스트 생성 헬퍼.

이 모듈은 의도적으로 범용 유틸만 담고,
도메인 전용 프롬프트 로직은 두지 않는다.
"""

import json
from urllib import request

from src.lib.settings import settings

GEMINI_MODEL_NAME = "gemini-2.0-flash"
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def call_gemini_text(
    prompt: str,
    *,
    temperature: float = 0.5,
    max_output_tokens: int = 220,
    timeout: int = 8,
) -> str:
    if not settings.gemini_api_key:
        raise ValueError("gemini_api_key is not configured")

    # 추가 SDK 의존성 없이도 사용할 수 있도록
    # Gemini REST 요청 형식에 맞춰 직접 payload를 구성한다.
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        },
    }

    endpoint = f"{GEMINI_API_BASE}/{GEMINI_MODEL_NAME}:generateContent?key={settings.gemini_api_key}"
    req = request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with request.urlopen(req, timeout=timeout) as response:  # noqa: S310
        raw = response.read().decode("utf-8")

    parsed = json.loads(raw)
    candidates = parsed.get("candidates") or []
    if not candidates:
        raise ValueError("No Gemini candidates")

    parts = ((candidates[0].get("content") or {}).get("parts") or [])
    # Gemini 응답은 텍스트가 여러 part로 나뉠 수 있어
    # 호출부에서는 일반 문자열 하나처럼 쓸 수 있도록 다시 합친다.
    text = "\n".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise ValueError("Empty Gemini text")

    return text
