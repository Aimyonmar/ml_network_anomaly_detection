# 接口文档（docs/api.md）

> 与代码实测一致（2026-10-11 D7 核对，基准 commit e529265）。
> 统一返回结构 `{code, msg, data}`（CONTEXT.md §4），`code` 与 HTTP 状态码一致，错误时 `data` 为 `null`。
> 例外：由依赖注入（`deps.get_current_user`）抛出的 401/403 走 FastAPI `HTTPException`，响应体为 `{"detail": "..."}`。
> 服务基准地址：`http://127.0.0.1:8000`，业务接口前缀 `/api/v1`。

## 认证（auth）

### POST /api/v1/auth/register — 用户注册
- 请求体：`{"username": "string(3~50)", "password": "string(6~64)"}`
- 成功 `201`：`{"code":201,"msg":"注册成功","data":{"id":1,"username":"...","role":"user","status":1,"created_at":"..."}}`
- 用户名已存在 `409`：`{"code":409,"msg":"用户名已存在","data":null}`
- 参数校验失败 `422`（FastAPI 默认）
- 密码入库为 bcrypt `$2b$...` 哈希，绝不存明文

### POST /api/v1/auth/login — 登录取 JWT
- 请求体：`{"username": "string", "password": "string"}`
- 成功 `200`：`{"code":200,"msg":"ok","data":{"token":"eyJ...","role":"user"}}`
- 用户名不存在或密码错误 `401`：`{"code":401,"msg":"用户名或密码错误","data":null}`（同一提示，防账号枚举）
- 账号被禁用 `403`：`{"code":403,"msg":"账号已被禁用","data":null}`
- token 为 HS256 JWT，`sub`=username，有效期 `ACCESS_TOKEN_EXPIRE_MINUTES`（默认 60 分钟）

### GET /api/v1/auth/me — 当前用户信息
- 请求头：`Authorization: Bearer <token>`
- 成功 `200`：`{"code":200,"msg":"ok","data":{同 register 的 data}}`
- token 无效/篡改/过期 `401`：`{"detail":"无效或过期的登录凭证"}`

## 检测（tasks）

以下接口均需 `Authorization: Bearer <token>`。

### POST /api/v1/tasks — 上传 csv 创建检测任务（异步）
- 请求：`multipart/form-data`，字段 `file`（仅 `.csv`，≤50MB；parquet 为预留扩展，未实现，见 DECISIONS.md 2026-10-11）
- 成功 `201`（立即返回，不等检测完成）：`{"code":201,"msg":"ok","data":{"task_id":12,"status":"pending"}}`
- 后缀不合法 / 超 50MB / 空文件 `400`：`{"code":400,"msg":"<具体原因>","data":null}`
- 检测由 BackgroundTasks 异步执行：`pending → running → success/failed`；
  失败时任务表 `error_msg` 写明原因（如列校验失败的字段级错误），临时文件清理不留 orphan
- 列校验：csv 须为 features.json 的 41 列（带表头，列名集合一致），或 NSL-KDD 无表头 42 列原始格式；缺列/多列/乱序均判 failed

### GET /api/v1/tasks — 我的任务列表（分页）
- Query：`page`(≥1，默认 1)、`page_size`(1~100，默认 20)
- 成功 `200`：`data = {"total":n,"page":p,"page_size":s,"items":[TaskOut...]}`
- `TaskOut`：`{id, file_name, total_rows, attack_rows, normal_rows, status, error_msg, cost_seconds, created_at, updated_at}`（不含 file_path）

### GET /api/v1/tasks/{task_id} — 任务详情（前端轮询 status 用）
- 成功 `200`：`data = TaskOut`
- 任务不存在 `404`：`{"code":404,"msg":"任务不存在","data":null}`
- 非本人任务且非 admin `403`：`{"code":403,"msg":"无权访问该任务","data":null}`

### GET /api/v1/tasks/{task_id}/results — 检测结果分页
- Query：`page`(≥1，默认 1)、`page_size`(1~200，默认 50)
- 成功 `200`：`data = {"total":n,"page":p,"page_size":s,"items":[ResultItem...]}`
- `ResultItem`：`{id, row_no, prediction("Normal"|"Attack"), attack_type(二分类暂为 null), confidence}`
- 实现约束：显式列查询，禁 `SELECT *` 全量拉取（CONTEXT.md §3）
- 归属校验同上（403/404）

### GET /api/v1/tasks/{task_id}/stats — 聚合统计（图表数据源）
- 成功 `200`：
```json
{"code":200,"msg":"ok","data":{
  "task_id":12,"status":"success","total_results":10000,
  "prediction_distribution":{"Normal":{"count":6000,"avg_confidence":0.93},"Attack":{"count":4000,"avg_confidence":0.88}},
  "task_rows":{"total_rows":10000,"attack_rows":4000,"normal_rows":6000},
  "cost_seconds":1.35}}
```
- 统计走 SQL 聚合（GROUP BY prediction），不拉明细；`total_results` 与任务表 `total_rows` 一致（D5 验收项）
- 归属校验同上（403/404）

## 健康检查

### GET /health — 存活探针（无需鉴权）
- `200`：`{"status":"ok"}`

## 未实现 / 预留（如实声明）

| 接口（CONTEXT.md §4 草案） | 状态 |
|---|---|
| GET /api/v1/admin/tasks（全平台任务） | 未实现，`admin.py` 仅占位 `/api/v1/admin/ping` |
| PUT /api/v1/admin/users/{id}/status（禁用/启用） | 未实现，同上 |
| GET /api/v1/model/info（模型信息） | 未实现，`model_api.py` 仅占位 `/api/v1/model/ping` |
| results.py 独立结果路由 | 结果查询已并入 `tasks/{id}/results`，`results.py` 仅占位 `/api/v1/results/ping` |
| `.parquet` 上传 | 预留扩展（白名单无 pyarrow，见 DECISIONS.md 2026-10-11） |
