
| 日期 | 会话主题 | 改动文件 | 一句话说明 | 遗留问题 | 明日待办 |
|---|---|---|---|---|---|
| 2026-09-21 | 项目骨架初始化 | CONTEXT.md, DECISIONS.md, CHANGELOG.md, scripts/auto_log.py | 建立上下文、决策、日志规范与自动归档脚本 | 无 | D1：FastAPI 骨架 + /health |
| 2026-10-11 | D1 补跑验收 + settings 缓存约束 | CONTEXT.md, .gitignore, settings/(新增), backend/.env(不入库), backend/app/models.py, backend/alembic/versions/ad96f59252ef_init_three_tables.py, TODO.md, DECISIONS.md | 建 settings/ 分类目录并用用户级环境变量(PIP_CONFIG_FILE/MPLCONFIGDIR)把 pip 与 matplotlib 缓存重定向出 C 盘(释放94MB)；依赖经清华源安装并降级对齐白名单(numpy2.0.2/matplotlib3.9.4/alembic1.13.3)；models.py 补齐三表 ORM；MySQL80 启动、建库 anomaly_detection、alembic upgrade head 落三张表；uvicorn 起服务 /health 返回 200 | 沙箱会拦截 pip 联网安装(需 dangerouslyDisableSandbox)；pip.ini 含中文注释会被 cp936 拒绝(已改纯 ASCII)；t_user 手动 INSERT 留待 D2 | D2：注册/登录/JWT 鉴权链路(security.py 四个函数实现+auth.py 路由) |
| 2026-10-11 | D2 认证链路 | backend/app/security.py, schemas.py, deps.py, routers/auth.py, main.py, requirements.txt, TODO.md, DECISIONS.md | 实现注册/登录/JWT鉴权全链路，路由前缀对齐/api/v1；passlib1.7.4+bcrypt5.0冲突崩溃，降级bcrypt→4.0.1修复；6项验收全过，入库密码$2b$12$前缀，篡改token返回401 | 启动时有一条无害的 (trapped) version 读取警告（passlib探测bcrypt版本失败但不影响功能）；admin角色鉴权留待D5 | D3：train.py 首次跑出数字 |
