from fastapi import APIRouter
from app.api.sessions import router as sessions_router

router = APIRouter()
router.include_router(sessions_router)
