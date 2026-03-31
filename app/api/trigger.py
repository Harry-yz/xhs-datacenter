from __future__ import annotations

from fastapi import APIRouter
from app.schemas import (
    APIResponse,
    AnchorTriggerRequest,
    BrandAccountsRequest,
    BrandAnalysisTriggerRequest,
    KeywordAnalysisTriggerRequest,
    NoteTriggerRequest,
    SearchTriggerRequest,
)
from app.services.huitun_client import HuitunClient
from app.tasks.jobs import (
    run_search_notes,
    sync_brand_info_and_accounts,
    trigger_anchor_info,
    trigger_brand_analysis,
    trigger_fans_portrait,
    trigger_keyword_analysis,
    trigger_note_comments,
    trigger_note_info,
)

router = APIRouter(prefix="/trigger", tags=["trigger"])
client = HuitunClient()


@router.post("/search", response_model=APIResponse)
def enqueue_search(req: SearchTriggerRequest) -> APIResponse:
    task = run_search_notes.delay(
        keyword=req.keyword,
        sort=req.sort,
        auto_enrich=req.auto_enrich,
        trigger_comments=req.trigger_comments,
        max_items=req.max_items,
    )
    return APIResponse(data={"task_id": task.id, "message": "queued"})


@router.post("/note", response_model=APIResponse)
def enqueue_note(req: NoteTriggerRequest) -> APIResponse:
    task = trigger_note_info.delay(req.note_id)
    return APIResponse(data={"task_id": task.id})


@router.post("/note-comments", response_model=APIResponse)
def enqueue_note_comments(req: NoteTriggerRequest) -> APIResponse:
    task = trigger_note_comments.delay(req.note_id)
    return APIResponse(data={"task_id": task.id})


@router.post("/anchor", response_model=APIResponse)
def enqueue_anchor(req: AnchorTriggerRequest) -> APIResponse:
    task = trigger_anchor_info.delay(req.anchor_id)
    return APIResponse(data={"task_id": task.id})


@router.post("/fans", response_model=APIResponse)
def enqueue_fans(req: AnchorTriggerRequest) -> APIResponse:
    task = trigger_fans_portrait.delay(req.anchor_id)
    return APIResponse(data={"task_id": task.id})


@router.post("/keyword-analysis", response_model=APIResponse)
def enqueue_keyword_analysis(req: KeywordAnalysisTriggerRequest) -> APIResponse:
    task = trigger_keyword_analysis.delay(
        keyword=req.keyword,
        last_days=req.last_days,
        priority=req.priority,
        note_type=req.note_type,
        business=req.business,
        goods=req.goods,
        max_note_num=req.max_note_num,
    )
    return APIResponse(data={"task_id": task.id})


@router.post("/brand-analysis", response_model=APIResponse)
def enqueue_brand_analysis(req: BrandAnalysisTriggerRequest) -> APIResponse:
    task = trigger_brand_analysis.delay(req.brand_name, req.priority, req.last_days)
    return APIResponse(data={"task_id": task.id})


@router.post("/brand-accounts", response_model=APIResponse)
def enqueue_brand_accounts(req: BrandAccountsRequest) -> APIResponse:
    task = sync_brand_info_and_accounts.delay(req.brand_name)
    return APIResponse(data={"task_id": task.id})


@router.get("/quota", response_model=APIResponse)
def get_quota() -> APIResponse:
    resp = client.get_quota()
    return APIResponse(data=resp)
