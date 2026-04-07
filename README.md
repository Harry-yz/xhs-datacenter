# xhs-data-center

XHS Data Center 是一个面向小红书数据分析的全栈系统，包含：
- `FastAPI` 查询与回调服务
- `Celery + Redis` 异步抓取任务
- `PostgreSQL` 数据存储与检索
- `Next.js` 数据中心前端

本文档用于快速理解项目框架、运行方式、清理策略、回滚流程。

## 1. 项目架构

### 1.1 组件与职责
- `app/`
  - `api/`: HTTP 接口（搜索、看板、回调、健康检查、认证）
  - `services/`: 检索、入库、领域解析、外部 API 封装
  - `tasks/`: Celery 任务定义
  - `init_db.py`: 初始化/补齐数据库结构
- `web/`
  - `app/`: Next.js App Router 页面与 API Route
  - `components/`: 页面组件
  - `services/`: 前端数据聚合与接口适配
- `scripts/`
  - 调度、补采、迁移、环境辅助脚本
- `sql/`
  - SQL 初始化脚本与历史结构定义
- `docs/`
  - 设计文档、说明材料（不影响运行）

### 1.2 数据流（简化）
1. 用户在前端发起搜索。
2. 前端请求后端搜索接口（`/api/v1/search/*`）。
3. 后端优先查数据库；命中不足时触发异步抓取任务。
4. 抓取任务回调进入 `app/api/callback*.py`，写入 ODS 与事实表。
5. 前端轮询任务状态并自动刷新结果。

## 2. 目录说明（运行相关）

- 运行必须：`app/`、`web/`、`scripts/`、`requirements.txt`、`docker-compose.yml`、`.env`
- 预览环境：`docker-compose.preview.yml`、`.env.preview`、`web/.env.preview`、`scripts/run_search_preview.sh`
- 非运行必需（可保留）：`docs/`、`tests/`、`api.ts`、`小红书api.html`、`数据采集字段需求.xlsx`

## 3. 环境变量

核心变量（见 `.env`）：
- 数据库：`DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD`
- Redis/Celery：`CELERY_BROKER_URL`、`CELERY_RESULT_BACKEND`
- 外部服务：`HUITUN_BASE_URL`、`HUITUN_CLIENT_ID`、`HUITUN_SECRET_KEY`
- 服务地址：`APP_PUBLIC_BASE_URL`、`API_PREFIX`
- 前端 API 地址：`NEXT_PUBLIC_API_BASE_URL=https://api.datacenter.photog.art/api/v1`

新增检索与灰度变量（默认值在 `app/config.py`）：
- `SEARCH_STALE_MINUTES=30`
- `SEARCH_V2_ENABLED=true`
- `SEARCH_V2_DUAL_READ=false`
- `SEARCH_V2_FALLBACK_ON_ERROR=true`
- `SEARCH_V2_CANDIDATE_LIMIT=5000`
- `SEARCH_V2_NOTE_CANDIDATE_LIMIT=8000`
- `SEARCH_AUTO_POLL_ENABLED=true`

## 4. 本地启动

### 4.1 后端
```bash
cd /opt/xhs_data_center
pip install -r requirements.txt
python -m app.init_db
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 3
```

### 4.2 Worker
```bash
cd /opt/xhs_data_center
celery -A app.tasks.celery_app:celery_app worker -Q xhs_priority_queue,xhs_queue --loglevel=info
```

### 4.3 前端（仅开发调试）
```bash
cd /opt/xhs_data_center/web
npm install
npm run dev -- --hostname 127.0.0.1 --port 3210
```

线上环境请勿将 `next dev` 作为常驻进程。

### 4.4 Docker（主栈）
```bash
cd /opt/xhs_data_center
docker compose up -d --build
```

仅重建前端守护服务：
```bash
cd /opt/xhs_data_center
docker compose build web
docker compose up -d web
```

## 5. 预览环境

```bash
cd /opt/xhs_data_center
chmod +x scripts/run_search_preview.sh
./scripts/run_search_preview.sh
```

默认端口：
- 预览后端：`127.0.0.1:8100`
- 预览前端：`127.0.0.1:3100`

## 6. 安全清理策略

只清理可重建运行垃圾，不删除业务代码与文档。

### 6.1 干跑（推荐先执行）
```bash
cd /opt/xhs_data_center
./scripts/safe_cleanup.sh --dry-run
```

### 6.2 实际清理
```bash
cd /opt/xhs_data_center
./scripts/safe_cleanup.sh
```

会清理：
- `web/.next`
- `web/.next-preview`
- `web/.next_bak_*`
- `logs/*.log` `logs/*.pid` `logs/*.tmp`

不会清理：
- `app/`、`web/app`、`web/components`、`scripts/`、`tests/`、`docs/`

## 7. 清理前后健康检查

```bash
cd /opt/xhs_data_center
./scripts/check_stack_health.sh
```

可通过变量覆盖地址：
```bash
API_BASE=http://127.0.0.1:8000 WEB_BASE=http://127.0.0.1:3210 ./scripts/check_stack_health.sh
```

## 8. 回滚手册

### 8.1 运行异常时快速回滚
1. 关闭检索新路径开关：
   - `SEARCH_V2_ENABLED=false`
2. 保持旧路径在线：
   - `SEARCH_V2_DUAL_READ=false`
   - `SEARCH_V2_FALLBACK_ON_ERROR=true`（仅异常时回退旧查询）
3. 重启后端服务。

### 8.2 前端守护上线/回滚（推荐）
```bash
cd /opt/xhs_data_center
chmod +x scripts/deploy_web_guardian.sh
./scripts/deploy_web_guardian.sh
```

该脚本会执行：`build -> up -d -> health check -> smoke test -> fail fast rollback`。

如需仅重启并回归检查（跳过构建）：
```bash
cd /opt/xhs_data_center
SKIP_BUILD=1 ./scripts/deploy_web_guardian.sh
```

### 8.3 前端构建缓存误删后恢复（开发模式）
```bash
cd /opt/xhs_data_center/web
npm install
npm run dev -- --hostname 127.0.0.1 --port 3210
```

### 8.4 容器环境恢复
```bash
cd /opt/xhs_data_center
docker compose up -d --build
```

## 9. 常用脚本

- `scripts/safe_cleanup.sh`: 安全清理运行垃圾
- `scripts/check_stack_health.sh`: 清理前后健康检查
- `scripts/deploy_web_guardian.sh`: 前端守护上线 + 自动回滚
- `scripts/industry_scheduler.py`: 行业低频调度
- `scripts/migrate_search_engine_v2.py`: 检索相关结构迁移
- `run_beauty_full_pipeline.sh`: 一键跑美妆链路

## 10. 常见问题

- Q: 清理后网页打不开？
  - A: 线上请执行 `./scripts/deploy_web_guardian.sh` 重建前端守护容器，再跑 `check_stack_health.sh`。
- Q: 搜索一直 pending？
  - A: 检查 worker 是否在线、Redis 是否可用、回调地址是否可达。
- Q: 为什么保留 docs 和 xlsx/html 文件？
  - A: 它们不影响运行，且用于交接与业务上下文，不纳入运行垃圾清理范围。
