"""추천 질문 생성을 담당하는 헬퍼 모듈.

모델 응답을 우선 사용하되, 실패 시 안전한 기본 질문으로 폴백한다.
"""

import json
import re
from typing import List

from .services.openai_service import get_openai_client

DEFAULT_QUESTIONS_KO = [
    "설비 시작 전 점검 순서를 알려줘",
    "운전 중 오류가 나면 먼저 무엇을 확인해야 해?",
    "제품 변경 시 바꿔야 하는 핵심 설정은 뭐야?",
    "카메라 인식이 안 될 때 우선 점검 항목은 뭐야?",
    "NG 비율이 갑자기 높아졌을 때 원인 후보를 정리해줘",
]

DEFAULT_QUESTIONS_EN = [
    "What should I check before starting the equipment?",
    "What should I inspect first when an error occurs?",
    "Which settings change when the product type changes?",
    "What should I check if the camera is not detected?",
    "What are the likely causes when the NG ratio suddenly rises?",
]


def _default_questions(language: str, count: int) -> List[str]:
    source = DEFAULT_QUESTIONS_EN if language == "en" else DEFAULT_QUESTIONS_KO
    return source[:count]


def _normalize_language(language: str) -> str:
    return "en" if str(language).lower().startswith("en") else "ko"


def _extract_questions_from_text(text: str) -> List[str]:
    # 모델이 번호나 불릿을 붙여서 반환하는 경우가 있어
    # UI에서 바로 쓸 수 있도록 줄 단위로 한 번 정리한다.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned: List[str] = []
    for line in lines:
        item = re.sub(r"^\s*(\d+[\.)]|[-*])\s*", "", line).strip()
        if len(item) >= 6:
            cleaned.append(item)

    unique_items: List[str] = []
    seen = set()
    for item in cleaned:
        if item not in seen:
            seen.add(item)
            unique_items.append(item)
    return unique_items


def _call_model_for_questions(language: str, count: int) -> List[str]:
    client, err = get_openai_client()
    if err:
        raise RuntimeError(err)

    prompt = (
        "You are a factory operation assistant.\n"
        f"Language: {'English' if language == 'en' else 'Korean'}\n"
        f"Return exactly {count} short practical quick questions.\n"
        "Rules:\n"
        "- one question per line\n"
        "- no numbering if possible\n"
        "- no explanation\n"
        "- keep them useful for operators\n"
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.5,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.choices[0].message.content or ""
    questions = _extract_questions_from_text(text)
    if not questions:
        raise ValueError("No extractable questions")
    return questions[:count]


def get_recommended_questions(language: str = "ko", count: int = 5) -> dict:
    normalized_language = _normalize_language(language)
    normalized_count = max(1, min(int(count), 8))
    try:
        items = _call_model_for_questions(normalized_language, normalized_count)
        if len(items) < normalized_count:
            # 모델 응답이 일부만 왔을 때는 부족한 개수만 기본 질문으로 채워
            # 가능한 한 모델 생성 결과를 우선 유지한다.
            for item in _default_questions(normalized_language, normalized_count):
                if item not in items:
                    items.append(item)
                if len(items) >= normalized_count:
                    break
        return {
            "items": items[:normalized_count],
            "language": normalized_language,
            "source": "openai",
            "count": normalized_count,
        }
    except (RuntimeError, ValueError, json.JSONDecodeError):
        # 모델 클라이언트가 내려가도 이 엔드포인트는 항상 같은 형태로 응답하게 한다.
        fallback = _default_questions(normalized_language, normalized_count)
        return {
            "items": fallback,
            "language": normalized_language,
            "source": "fallback",
            "count": normalized_count,
        }
