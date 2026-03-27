"""운영용 LLM 엔드포인트를 `/llm` 아래로 묶는 최상위 라우터."""

from fastapi import APIRouter, Query

from src.modules.llm.llm_chat_api import chat_router
from src.modules.llm.llm_media_api import media_router
from src.modules.llm.llm_question import get_recommended_questions
from src.modules.llm.llm_result_api import result_router

router = APIRouter(prefix="/llm", tags=["llm"])
# 기능별 라우터를 분리해 두면 chat/media/result 변경이 생겨도
# 엔드포인트 파일 하나가 과하게 비대해지지 않아 유지보수가 편하다.
router.include_router(chat_router)
router.include_router(media_router)
router.include_router(result_router)


@router.get("/recommended-questions")
def recommended_questions(
    lang: str = Query(default="ko", description="Language code (ko or en)"),
    count: int = Query(default=3, ge=1, le=8, description="Number of recommendations"),
):
    # 라우터는 요청 파라미터 정리만 담당하고,
    # 실제 추천 질문 생성/폴백 전략은 `llm_question.py`에 둔다.
    return get_recommended_questions(language=lang, count=count)
