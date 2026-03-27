from fastapi import APIRouter

from src.modules.optimization.service import optimizer_status_placeholder

router = APIRouter(prefix="/optimization", tags=["optimization"])


@router.get("/status")
def optimizer_status():
    return optimizer_status_placeholder()
