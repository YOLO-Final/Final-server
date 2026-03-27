from fastapi import APIRouter

from src.modules.voice_interaction.service import speech_status_placeholder

router = APIRouter(prefix="/voice", tags=["voice_interaction"])


@router.get("/status")
def speech_status():
    return speech_status_placeholder()
