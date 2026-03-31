from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import APIResponse
from app.api.callback import (
    note_callback,
    anchor_callback,
    fans_callback,
    comment_callback,
    keyword_callback,
    brand_callback,
)

router = APIRouter(prefix="/test", tags=["callback-compat"])


@router.post("/noteInfo/back", response_model=APIResponse)
async def note_info_back(
    request: Request,
    db: Session = Depends(get_db),
) -> APIResponse:
    return await note_callback(request, db)


@router.post("/anchorInfo/back", response_model=APIResponse)
async def anchor_info_back(
    request: Request,
    db: Session = Depends(get_db),
) -> APIResponse:
    return await anchor_callback(request, db)


@router.post("/fansProfile/back", response_model=APIResponse)
async def fans_profile_back(
    request: Request,
    db: Session = Depends(get_db),
) -> APIResponse:
    return await fans_callback(request, db)


@router.post("/noteComment/back", response_model=APIResponse)
async def note_comment_back(
    request: Request,
    db: Session = Depends(get_db),
) -> APIResponse:
    return await comment_callback(request, db)


@router.post("/keywordAnalysis/back", response_model=APIResponse)
async def keyword_analysis_back(
    request: Request,
    db: Session = Depends(get_db),
) -> APIResponse:
    return await keyword_callback(request, db)


@router.post("/brandAnalysis/back", response_model=APIResponse)
async def brand_analysis_back(
    request: Request,
    db: Session = Depends(get_db),
) -> APIResponse:
    return await brand_callback(request, db)