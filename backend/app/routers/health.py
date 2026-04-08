from fastapi import APIRouter
from ..config import settings

router = APIRouter()


@router.get("/")
def root():
    return {"message": "Website Cloner API running"}


@router.get("/health")
async def health():
    return {
        "status": "healthy",
        "api_key_configured": bool(settings.anthropic_api_key),
    }
