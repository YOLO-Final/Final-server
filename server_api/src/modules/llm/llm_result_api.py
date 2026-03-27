"""간단한 프롬프트-결과 조회용 비스트리밍 엔드포인트."""

from fastapi import APIRouter  # type: ignore
from pydantic import BaseModel, Field

from .services.openai_service import get_openai_client

result_router = APIRouter(tags=["llm"])


class LlmResultRequest(BaseModel):
    """단발성 텍스트 생성 요청용 검증 모델."""

    prompt: str = Field(..., min_length=1, description="Prompt text for the LLM")
    temperature: float = Field(default=0.3, ge=0.0, le=1.0)
    max_output_tokens: int = Field(default=256, ge=32, le=2048)


@result_router.post("/result")
def llm_result(request: LlmResultRequest):
    client, err = get_openai_client()
    if err:
        return {"ok": False, "source": "fallback", "text": "", "message": err}

    try:
        # 이 라우트는 단순 연동 용도이므로
        # 전체 채팅 에이전트 파이프라인 대신 가벼운 1회 호출만 사용한다.
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=request.temperature,
            max_tokens=request.max_output_tokens,
            messages=[{"role": "user", "content": request.prompt}],
        )
        return {
            "ok": True,
            "source": "openai",
            "text": response.choices[0].message.content or "",
        }
    except Exception as exc:
        return {
            "ok": False,
            "source": "fallback",
            "text": "",
            "message": str(exc),
        }
