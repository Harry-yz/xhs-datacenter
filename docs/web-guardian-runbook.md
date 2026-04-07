# XHS Web Guardian Runbook

## 1. 目标
- `web` 前端以 Docker 守护方式长期运行，避免 `3210` 进程丢失导致 `502`。
- 切换与回滚都走脚本，避免临时手工命令。
- 服务端搜索链路固定走内网 `INTERNAL_API_BASE_URL`，不再走公网重定向地址。

## 2. 一键上线
```bash
cd /opt/xhs_data_center
chmod +x scripts/deploy_web_guardian.sh
./scripts/deploy_web_guardian.sh
```

默认会执行：
1. 备份当前镜像到 `xhs_web:rollback`
2. 构建 `xhs_web:current`
3. `docker compose up -d web`
4. 健康检查与 smoke test（含 `POST /api/search/brand-category` 的 ready 闸门）
5. 失败自动回滚
6. 启动 `search_stability_watchdog.sh`（每分钟巡检）

## 3. 健康检查
```bash
cd /opt/xhs_data_center
./scripts/check_stack_health.sh
```

重点检查项：
- 页面：`/zh/datacenter/xhs`
- 搜索：`/zh/datacenter/xhs/search?type=category&q=YSL`
- API：`/health` 与 `/api/v1/dashboard/xhs/overview?days=90`
- 搜索代理闸门：`POST /api/search/brand-category` 返回 `ready + items`

## 4. 常用运维命令
```bash
cd /opt/xhs_data_center
docker compose ps web fastapi
docker compose logs -f web
docker compose restart web
tail -f /tmp/xhs_search_watchdog.log
```

## 5. 回滚
- 脚本会自动回滚。
- 手工回滚：
```bash
cd /opt/xhs_data_center
docker image tag xhs_web:rollback xhs_web:current
docker compose up -d web
./scripts/check_stack_health.sh
```

## 6. 故障排查
- `502 Bad Gateway`：
  - 先看 `docker compose ps web` 是否 `Up`
  - 再看 `ss -ltnp | rg :3210` 是否监听
  - 最后看网关回源是否可达（openresty 容器内 `curl http://127.0.0.1:3210/zh/datacenter`）
- 首屏卡顿：
  - 确认前端运行在生产模式（`next start`，不是 `next dev`）
  - 确认 `INTERNAL_API_BASE_URL=http://fastapi:8000/api/v1`
  - `NEXT_PUBLIC_API_BASE_URL` 只用于浏览器公开能力，不参与服务端搜索代理
