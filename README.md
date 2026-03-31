# xhs-data-center

## 目录用途
- `app/api/`：对外 HTTP 接口，包括搜索、查询、回调、看板、健康检查。
- `app/services/`：灰豚接口封装、签名、入库和解析逻辑。
- `app/tasks/`：Celery 配置和异步任务。
- `scripts/`：批量采集和补采脚本。
- `app/init_db.py`：数据库初始化脚本。
- `api.ts`：前端调用后端接口的 API client 类型定义。

## 本地启动
1. 准备 `.env` 并填写数据库、灰豚、Redis 配置。
2. 安装依赖：`pip install -r requirements.txt`
3. 初始化数据库：`python -m app.init_db`
4. 启动 API：`uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
5. 启动 worker：`celery -A app.tasks.celery_app:celery_app worker -Q xhs_queue --loglevel=info`

## 常用脚本
- 同步本地美妆分类维表：`python scripts/sync_beauty_catalog.py`
- 批量抓取美妆搜索结果：`python scripts/crawl_xhs_beauty.py crawl_keywords --limit 100`
- 补抓笔记详情：`python scripts/enqueue_note_info_backfill.py --limit 500`
- 补抓笔记评论：`python scripts/enqueue_note_comment_backfill.py --limit 300 --min-like 100`
- 一键跑美妆链路：`./run_beauty_full_pipeline.sh`

## 低频调度
- 一次性跑一轮低频调度：`python scripts/beauty_scheduler.py --once`
- 持续低频调度服务：`docker compose --profile scheduler up -d scheduler`
- 默认每 `24` 小时跑一轮美妆全量关键词，每轮只补最近 `24` 小时进入或更新过的数据，限额由 `.env` 中的 `BEAUTY_SCHEDULER_*` 控制。
