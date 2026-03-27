from fastapi import APIRouter

from src.modules.auth.router import router as auth_router
#from src.modules.chatlog.router import router as chatlog_router
from src.modules.dashboard.router import router as dashboard_router
from src.modules.db.items.router import router as items_router
from src.modules.llm.router import router as llm_router
from src.modules.optimization.router import router as optimization_router
from src.modules.rag.router import router as rag_router
from src.modules.report.router import router as report_router
from src.modules.vision.router import router as vision_router
from src.modules.voice_interaction.router import router as voice_router

api_v1_router = APIRouter()
api_v1_router.include_router(auth_router)
#api_v1_router.include_router(chatlog_router)
api_v1_router.include_router(dashboard_router)
api_v1_router.include_router(llm_router)
api_v1_router.include_router(items_router)
api_v1_router.include_router(voice_router)
api_v1_router.include_router(optimization_router)
api_v1_router.include_router(vision_router)
api_v1_router.include_router(rag_router)
api_v1_router.include_router(report_router)
