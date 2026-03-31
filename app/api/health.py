from __future__ import annotations

from fastapi import APIRouter
from app.schemas import APIResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=APIResponse)
def health() -> APIResponse:
    return APIResponse(data={"status": "ok", "service": "xhs-data-center"})
