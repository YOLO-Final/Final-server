"""운영용 LLM 채팅 기능을 노출하는 FastAPI 엔드포인트 모음.

이 파일의 핸들러는 의도적으로 얇게 유지한다.
요청 파싱과 최소한의 검증만 처리하고,
실제 상태 관리와 응답 생성은 agent/knowledge 서비스로 위임한다.
"""

import asyncio
import os
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from .services.knowledge_service import (
    ensure_knowledge_current,
    get_agent,
    get_knowledge_path,
    get_knowledge_status,
    list_knowledge_files,
    load_knowledge_on_startup,
    reindex_knowledge,
    update_knowledge,
)
from .services.openai_service import to_bool

chat_router = APIRouter(tags=["llm"])
_startup_index_task: Optional[asyncio.Task] = None
_startup_index_error: str = ""


def _indexing_in_progress() -> bool:
    """시작 시점 인덱싱 진행 여부만 간단히 노출한다."""
    return bool(_startup_index_task and not _startup_index_task.done())


def _indexing_status() -> dict:
    """상태 조회, 업로드, 재인덱싱 화면에서 공통으로 쓰는 상태 헬퍼."""
    return {
        "in_progress": _indexing_in_progress(),
        "error": _startup_index_error,
    }


def _start_background_knowledge_index() -> None:
    global _startup_index_task
    if _indexing_in_progress():
        return

    async def _runner() -> None:
        global _startup_index_error
        _startup_index_error = ""
        try:
            # PDF/이미지 OCR, 벡터화 작업이 오래 걸려도
            # 서버 시작 자체는 막히지 않도록 워커 스레드에서 처리한다.
            await asyncio.to_thread(load_knowledge_on_startup)
        except Exception as exc:
            _startup_index_error = str(exc)
            print(f"[startup] background knowledge indexing failed: {exc}")

    _startup_index_task = asyncio.create_task(_runner())


@chat_router.on_event("startup")
async def startup() -> None:
    _start_background_knowledge_index()


@chat_router.post("/chat")
async def chat(
    message: str = Form(""),
    provider: str = Form("openai"),
    web_search: str = Form("false"),
    disable_auto_web: str = Form("true"),
    reset_memory: str = Form("false"),
    empathy_level: str = Form("balanced"),
    language: str = Form("ko"),
    session_id: str = Form("default"),
):
    # API 레이어는 최대한 단순하게 유지하고,
    # 실제 채팅 동작은 `agent.py`에 모아 두어 이후 인수인계와 수정이 쉽도록 한다.
    if not _indexing_in_progress():
        # 시작 시 인덱싱이 끝난 뒤에도 파일 업로드나 수동 수정이 반영되도록
        # 요청 시점에 한 번 더 변경 여부를 느슨하게 확인한다.
        ensure_knowledge_current()
    agent = get_agent()
    use_web_search = to_bool(web_search)
    disable_auto_web_search = to_bool(disable_auto_web)
    normalized_session = (session_id or "default").strip() or "default"

    if to_bool(reset_memory):
        agent.reset_memory(normalized_session)

    async def stream_wrapper():
        try:
            # 에이전트가 이미 잘린 청크를 순차적으로 내보내므로,
            # 여기서는 sync generator를 FastAPI의 async 스트리밍 응답으로 연결만 해준다.
            for chunk in agent.get_ai_streaming_response(
                message,
                provider=provider,
                use_web_search=use_web_search,
                disable_auto_web=disable_auto_web_search,
                empathy_level=empathy_level,
                session_id=normalized_session,
                response_language=language,
            ):
                yield chunk
                await asyncio.sleep(0)
        except Exception as exc:
            print(f"[chat] streaming error: {exc}")
            yield f"응답 생성 중 오류가 발생했습니다: {exc}"

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(stream_wrapper(), media_type="text/plain; charset=utf-8", headers=headers)


@chat_router.get("/memory")
async def memory_status(session_id: str = "default"):
    return get_agent().get_memory_snapshot(session_id)


@chat_router.post("/memory/reset")
async def reset_memory(session_id: str = Form("default")):
    normalized_session = (session_id or "default").strip() or "default"
    get_agent().reset_memory(normalized_session)
    return {"message": "Memory was reset successfully.", "session_id": normalized_session}


@chat_router.get("/knowledge")
async def knowledge_status():
    status = get_knowledge_status()
    status["indexing"] = _indexing_status()
    return status


@chat_router.get("/health/web")
async def web_health(probe_query: str = "current market data now"):
    agent = get_agent()
    return agent.get_web_diagnostics(probe_query)


@chat_router.get("/knowledge/files")
async def knowledge_files():
    if not _indexing_in_progress():
        ensure_knowledge_current()
    result = {
        "knowledge_path": str(get_knowledge_path()),
        "files": list_knowledge_files(),
    }
    result["indexing"] = _indexing_status()
    return result


@chat_router.post("/knowledge/reindex")
async def knowledge_reindex():
    return reindex_knowledge()


@chat_router.post("/upload")
async def upload(file: UploadFile = File(...)):
    filename = os.path.basename(file.filename or "").strip()
    if not filename:
        return {"error": "File name is empty."}

    suffix = Path(filename).suffix.lower()
    allowed = {".txt", ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
    if suffix not in allowed:
        return {"error": "TXT/PDF/Image files are supported (.txt, .pdf, .png, .jpg, .jpeg, .webp, .bmp, .gif)."}

    knowledge_path = get_knowledge_path()
    knowledge_path.mkdir(parents=True, exist_ok=True)

    path = knowledge_path / filename
    # 감시 중인 지식 폴더에 바로 저장하고,
    # 업로드 직후 `update_knowledge()`로 메모리 내 검색 상태를 다시 만든다.
    with path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    chunks = update_knowledge()
    return {
        "message": f"Upload complete: {path.name} (indexed chunks: {chunks})",
        "indexed_chunks": chunks,
    }
