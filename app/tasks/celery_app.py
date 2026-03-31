from __future__ import annotations

from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "xhs_data_center",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.jobs"],
)

celery_app.conf.task_default_queue = settings.task_default_queue
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.timezone = "Asia/Shanghai"
celery_app.conf.enable_utc = False
celery_app.conf.broker_connection_retry_on_startup = True
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.worker_concurrency = settings.celery_worker_concurrency
celery_app.conf.task_annotations = {
    "app.tasks.jobs.run_search_notes": {"rate_limit": settings.huitun_note_search_rate_limit},
    "app.tasks.jobs.trigger_note_info": {"rate_limit": settings.huitun_note_info_rate_limit},
    "app.tasks.jobs.trigger_note_comments": {"rate_limit": settings.huitun_note_comment_rate_limit},
    "app.tasks.jobs.trigger_anchor_info": {"rate_limit": settings.huitun_anchor_info_rate_limit},
    "app.tasks.jobs.trigger_fans_portrait": {"rate_limit": settings.huitun_fans_portrait_rate_limit},
}
