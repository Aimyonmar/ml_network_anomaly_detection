


# 项目进度看板

> 本文件记录计划与实际偏差，不粘贴给 AI（AI 只需 CONTEXT.md）。
> 创建：2026-09-21 | 最后更新：2026-09-21

---

## 一、开发节奏（D1~D7）

| 天 | 智能体 | 验收标准（可验证动作） | 计划日期 | 实际完成 | 偏差说明 |
|---|---|---|---|---|---|
| D1 | ①后端 | uvicorn 能起；/health 返回 200；alembic upgrade head 后 MySQL 能看到三张表 | 2026-09-21 | 2026-10-11 | 停滞约20天后补跑；实际建库名为 anomaly_detection（非计划中的 ids_demo，以 config.py/.env 为准）；requirements.txt 与 venv 残留版本冲突（numpy/matplotlib/alembic），已按白名单降级 |
| D2 | ④+① | 注册→登录→拿 token→/auth/me 返回用户名；库里密码是 $2b$…；token 篡改返回 401 | 2026-09-22 | 2026-10-11 | passlib 1.7.4 与 bcrypt 5.0 冲突（__about__ 移除 + >72字节抛错），经确认降级 bcrypt 到 4.0.1 并钉死写入 requirements.txt；路由前缀对齐 CONTEXT.md §4 的 /api/v1 |
| D3 | ③ML | train.py 不报错；产出 model.pkl + features.json；有基线对照数字；混淆矩阵 png 存在 | 2026-09-23 | — | — |
| D4 | ③ML | predict.py 能跑并打印吞吐；**故意删一列重跑能看到明确报错**（必做） | 2026-09-24 | — | — |
| D5 | ①后端 | 上传 1 万行 CSV，1 秒内返回 task_id；轮询 status 从 pending 变 success；stats 总数与 count(*) 一致 | 2026-09-25 | — | — |
| D6 | ②前端 | 能登录、能上传、报告页三张图渲染且中文不乱码；关掉后端时页面提示错误而非白屏 | 2026-09-26 | — | — |
| D7 | ⑤设计文档+④ | 需求分析/架构/数据库设计/测试用例/Q&A 齐全；所有数字是真实结果或【待填】 | 2026-09-27 | — | — |

**填写规则（重要）：**
1. 「验收标准」列**永远不许改**。它是承诺，不是目标。改了它就等于自己给自己放水。
2. 延期时只填「实际完成」和「偏差说明」，**不准删行、不准挪行、不准重写验收标准**。
3. 偏差说明要写具体原因（如 passlib 与 bcrypt 版本冲突），这是设计文档「开发过程」段落的原始素材。

每天收尾：`python scripts/auto_log.py changelog` → `git add . && git commit -m "Dx: ..."`
每周日：`python scripts/auto_log.py images` → `check` → 给记录员发 `/report 本周`

---

## 二、当前状态（今日待办）

### 环境搭建（今天，约 30 分钟）
- [x] 确认 `python --version` 显示 3.12.5
- [x] `python -m venv venv` 并激活（实际目录名 venv，非原计划 .venv，确认保留）
- [x] 建项目骨架：CONTEXT.md / CHANGELOG.md / DECISIONS.md / BUGS.md / METRICS.md / TODO.md
- [x] `scripts/auto_log.py` 就位
- [x] `docs/schema.sql` 就位（手写，不让 AI 写；已落盘 3 张表）
- [x] `backend/requirements.txt`（pymysql 同步驱动，决策已记入 DECISIONS.md）+ `.env.example`
- [x] `git init` + 首次 commit（c6ab434；本地占位身份 ml-dev，未配置全局）
- [x] `python scripts/auto_log.py check` 跑一遍（当前 1 条警告为 models.py docstring 示例文字被正则误匹配，D1 建模型类后自动对齐）
- [ ] 记第一条日志：`/log 今天：建项目骨架……`

### D1：后端骨架（今天，环境完成后）
- [x] 新建对话，用智能体①开场模板（CONTEXT.md 全文 + 本次任务）
- [x] 核对它输出的「schema.sql ↔ models.py 对照表」（3 表 3 类一致，索引/默认值/注释对齐）
- [x] 核对它输出的目录树（ml/ 在 backend/ 下，__init__.py 正确）
- [x] `pip install -r requirements.txt`（清华源；冲突包已降级对齐白名单）
- [x] MySQL 建库：`CREATE DATABASE IF NOT EXISTS ids_demo CHARACTER SET utf8mb4;`（实际按 config.py/.env 建为 anomaly_detection，ids_demo 为原计划名，以代码为准）
- [x] `alembic upgrade head`（初始迁移 ad96f59252ef，三张表+全部索引落库）
- [x] `uvicorn app.main:app --reload` → curl /health 返回 200 `{"status":"ok"}`
- [x] `DESC t_user;` 确认 password varchar(100)；（手动 INSERT 留待 D2 注册接口验证）
- [x] git commit + 勾掉 D1 + 写 CHANGELOG

### 后续（暂不执行）
- [x] D2：注册/登录/JWT 鉴权链路（2026-10-11 完成：6 项链路验证全过，入库密码 $2b$12$ 前缀，篡改 token 401）
- [ ] D3：train.py 首次跑出数字 → 填写 METRICS.md 的 ## FINAL
- [ ] D4：predict.py + 列序校验
- [ ] D5：上传与异步检测链路
- [ ] D6：前端四页 + 图表
- [ ] D7：文档初稿 + 测试用例

---

## 三、历史里程碑

| 日期 | 事件 |
|---|---|
| 2026-09-21 | 项目立项，CONTEXT.md v0.1 → v0.4，骨架建立 |
| 2026-10-11 | D1 补跑验收通过（依赖对齐白名单、三表落库、/health 200）；新增 settings/ 缓存约束并全局重定向 pip/matplotlib 缓存出 C 盘 |

> 每完成一个阶段，在此追加一行。不要删除上文。


