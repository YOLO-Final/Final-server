from fastapi import APIRouter

from src.modules.rag.service import rag_status_placeholder

router = APIRouter(prefix="/rag", tags=["rag"])


@router.get("/status")
def rag_status():
    return rag_status_placeholder()
