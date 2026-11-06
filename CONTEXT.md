# 项目上下文：基于机器学习的网络异常检测系统设计与实现

> 本文件是项目唯一总纲。每次开启新对话时，必须将全文粘贴在第一条消息中。
> 版本：v0.5 | Python 3.12.5 | 最后更新：2026-09-22
> 变更：v0.4→v0.5 数据库链路由 asyncmy/async 改为 pymysql/同步（决策见 DECISIONS.md 2026-09-21 条）；v0.4 已将第 9、10 节移至 TODO.md

---

## 0. 定位（最高优先级，违反即视为设计错误）

本项目是**「带智能检测模块的 Web 系统」**，不是「一个检测模型」。
评审口径走软件工程「需求—设计—实现—测试」，模型只是 4.x 节中的一个模块。
文档与实现重心：系统工程约 65% / 算法约 20% / 其他约 15%。

任何功能决策优先保证：**系统能跑通、链路完整、可演示**。宁可功能降级，不能让链路断掉。

---

## 1. 技术栈（锁定，不许擅自更换或新增）

- 语言：**Python 3.12.5**（全部依赖需兼容 3.12，安装前核对版本；scikit-learn 用 1.5+）
- Web：FastAPI + Uvicorn + Pydantic v2
- ORM：SQLAlchemy 2.0（**同步**）+ Alembic
- DB：MySQL 8.0（utf8mb4），连接池由 SQLAlchemy 管理；**驱动 pymysql + cryptography**
- 认证：JWT（python-jose），密码 bcrypt（passlib[bcrypt]）
- 异步任务：**FastAPI BackgroundTasks**（第一版不用 Celery，除非我明确要求）
- 前端：Vue 3 + Vite + TypeScript + Element Plus + Axios + Pinia + Vue Router + ECharts
- ML：pandas + numpy + scikit-learn + joblib + matplotlib/seaborn（**只做 sklearn 生态**）
- 其他：python-multipart（文件上传，FastAPI 不自带，必须显式安装）、loguru、pytest
- 依赖清单：`backend/requirements.txt`（这是白名单：没写在里面的包不许引入）
- **虚拟环境：所有项目依赖必须安装到项目本地的虚拟环境中（如 `venv/` 或 `.venv/`），严禁安装到全局 Python 环境。开发前必须先激活虚拟环境再执行 `pip install`。**
- **缓存与产物落盘位置（settings 约束）：凡不是必须装在 C 盘的依赖缓存/下载/临时产物，一律归入根目录 `settings/` 并按子目录分类，禁止默认写到 C 盘：**
  - `settings/pip-cache/`：pip 下载缓存（已通过用户级环境变量 `PIP_CONFIG_FILE` → `settings/pip/pip.ini` 全局重定向）
  - `settings/matplotlib/`：matplotlib 字体/配置缓存（已通过用户级环境变量 `MPLCONFIGDIR` 重定向）
  - `settings/logs/`：loguru 运行日志
  - `settings/pip/`：`pip.ini` 配置文件本体
  - 新增需要落盘的缓存类目录时，在 `settings/` 下建子目录并回来补本节清单

**一致性要求：**
- 依赖文件与本文必须一致：若本文写 SQLAlchemy 2.0，requirements.txt 里绝不能是 1.4.*；本文写同步 pymysql，驱动绝不能是 asyncmy。改一处同步另一处。
- **全链路同步：engine 用 create_engine，会话用 Session，路由处理函数用普通 def。不得混入 create_async_engine / AsyncSession / async def 查询。**
- 若 passlib / python-jose 在 3.12 下安装失败，允许替换为等效方案（固定版 bcrypt / PyJWT），但必须先说明差异并经我确认，且只许改 security.py。

## 1.x 版本冲突裁决
当本文、requirements.txt、AI 建议三者出现版本或模式冲突时，优先级为：
**docs/schema.sql / requirements.txt（已落盘的真实文件） > CONTEXT.md 文字描述 > AI 建议。**
遇到冲突必须停止执行，先列出三者的差异让我确认，不得擅自选择。

---

## 2. 目录结构（照这个建，不要自由发挥）

```
项目根/
  CONTEXT.md / CHANGELOG.md / DECISIONS.md / BUGS.md / METRICS.md / TODO.md
  settings/                    # 非 C 盘缓存/配置区（pip-cache、matplotlib、logs、pip/pip.ini）
  scripts/auto_log.py          # 自动归档与一致性校验脚本（只读 git 和真实文件）
  screenshots/                 # 图号命名：图6-4_检测报告页.png
  docs/
    schema.sql / api.md / images-list.md   # images-list.md 由脚本生成，不要手改
  backend/
    requirements.txt / .env.example
    app/
      __init__.py              # 前后各两个下划线
      main.py                  # 入口：注册路由、中间件、CORS
      config.py                # 从环境变量读配置，给默认值，缺配置报明确错误
      database.py              # 同步 engine（create_engine）/ SessionLocal
      models.py                # ORM 模型（与 schema.sql 严格一致）
      schemas.py               # Pydantic 请求/响应模型
      deps.py                  # get_db, get_current_user
      security.py              # pwd hash, jwt 签发/校验
      routers/
        auth.py / tasks.py / results.py / admin.py / model_api.py
      services/
        detection.py           # 预处理 + 调用 ml/predict.py + 写结果表 + 更新任务状态
      utils/
        file_io.py             # 校验后缀/大小、流式保存、失败清理临时文件
    ml/
      train.py                 # 离线训练脚本（不随 web 启动）
      predict.py               # load model + features.json 列序校验 + 单条/批量推理
      features.json            # 训练时使用的特征列序（由 train.py 生成）
    alembic/
  frontend/                    # 第二周再建，D1~D5 不许碰
```

---

## 3. 数据库（以 docs/schema.sql 为准，字段名下划线小写）

```sql
CREATE TABLE t_user (
  id          BIGINT PRIMARY KEY AUTO_INCREMENT,
  username    VARCHAR(50) NOT NULL UNIQUE,
  password    VARCHAR(100) NOT NULL COMMENT 'bcrypt 哈希',
  role        VARCHAR(10) NOT NULL DEFAULT 'user' COMMENT 'user|admin',
  status      TINYINT NOT NULL DEFAULT 1 COMMENT '1启用 0禁用',
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE t_detection_task (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id         BIGINT NOT NULL,
  file_name       VARCHAR(255) NOT NULL,
  file_path       VARCHAR(512) NOT NULL,
  total_rows      INT DEFAULT 0,
  attack_rows     INT DEFAULT 0,
  normal_rows     INT DEFAULT 0,
  status          VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending|running|success|failed',
  error_msg       VARCHAR(512) DEFAULT NULL,
  cost_seconds    FLOAT DEFAULT NULL,
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_user_time (user_id, created_at),
  INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE t_detection_result (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_id       BIGINT NOT NULL,
  row_no        INT NOT NULL COMMENT '文件中第几行',
  prediction    VARCHAR(20) NOT NULL COMMENT 'Normal|Attack',
  attack_type   VARCHAR(50) DEFAULT NULL COMMENT '多分类时才有值',
  confidence    FLOAT DEFAULT NULL,
  INDEX idx_task (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

约束：
- 密码绝不存明文；token 不入库。
- `t_detection_result` 可能几十万行：查询必须分页，禁止 `SELECT *` 拉全量；统计用聚合 SQL。
- 任务失败必须清理或保留临时文件并在 `error_msg` 写明原因，不允许出现 orphan 文件。
- **任何表结构变更必须先出 SQL，经我确认后再改 ORM。**
- 不加 FOREIGN KEY（逻辑关联即可，避免级联拖慢写入）。

---

## 4. 接口清单草案（docs/api.md，统一返回 {code, msg, data}）

认证
- POST /api/v1/auth/register → 201 / 409（用户名已存在）
- POST /api/v1/auth/login → data:{token, role}
- GET  /api/v1/auth/me → 当前用户信息

检测
- POST /api/v1/tasks → 上传文件，返回 task_id（异步，立即返回 pending）
- GET  /api/v1/tasks → 我的任务列表（分页）
- GET  /api/v1/tasks/{id} → 任务详情含 status（前端轮询用）
- GET  /api/v1/tasks/{id}/results → 结果分页（page, page_size）
- GET  /api/v1/tasks/{id}/stats → 聚合统计（攻击类型分布、趋势），供图表用

管理
- GET  /api/v1/admin/tasks → 全平台任务（admin）
- PUT  /api/v1/admin/users/{id}/status → 禁用/启用

模型
- GET /api/v1/model/info → 模型名、训练时间、特征数、版本（用于界面与指标展示）
- GET /health → 存活探针

约束：所有接口给请求/响应示例与错误码；文件上传限制 `.csv/.parquet`，单文件 ≤ 50MB；校验列是否包含 `features.json` 所需列，缺失则返回明确字段级错误。

---

## 5. 机器学习硬规则（违反即视为错误）

1. `train_test_split` 必须是第一步，`stratify=y, random_state=42`，且在**任何预处理之前**。
2. 归一化/SMOTE 只能 fit 训练集再 transform 测试集；必须用 Pipeline 包裹，杜绝泄漏。
3. **绝不只报 accuracy。** 必须输出各类别 precision/recall/F1、混淆矩阵、ROC-AUC、分类报告，并给出「全猜多数类」基线作对照。
4. 类别不平衡：先打印 label 分布，再决定 class_weight 或 SMOTE，并说明理由。
5. 特征分两类交付：A) 数据集现成列；B) 自行构造列（逐条说明物理含义）。
6. `train.py` 必须同时产出 `model.pkl` + `features.json`（列序）；`predict.py` 加载时校验列序一致，不一致抛明确错误。
7. 推理支持单条与批量，返回标签+置信度，并输出实测吞吐（条/秒）。
8. **若指标 >99.5%，主动怀疑泄漏并给出排查清单。**
9. 禁止深度学习框架；禁止自动换数据集；禁止美化数字；没有实测数据就用【待填】占位。
10. 模型第 3 周末锁死不再调参（随机森林默认参数即可）。

---

## 6. 记录规范（项目过程记录，与代码同等重要）

| 文件 | 记什么 | 规则 |
|---|---|---|
| CHANGELOG.md | 每日改动文件、说明、遗留问题、明日待办 | 只追加不改已有行；日期 YYYY-MM-DD；缺项用【待填】 |
| DECISIONS.md | 每个二选一决策 | 必须含「放弃的选项」和「代价」两列 |
| BUGS.md | 卡住超过 30 分钟的问题 | 「根因」必须写到具体机制，不能写「代码写错了」 |
| METRICS.md | 每次跑模型的指标 | 坏结果也必须记；`## FINAL` 区块的数字将进入摘要/结论/PPT，定型后不许改 |
| screenshots/ + docs/images-list.md | 界面与实验截图 | 命名 `图X-Y_说明.png`；index 由脚本生成，不手改 |
| DATASET.md / LITERATURE.md / advisor.md | 数据集档案、文献卡片、项目指导沟通记录 | 读一篇记一篇；每次沟通后立刻记 |
| TODO.md | 阶段任务与完成状态 | 只做勾选和加注，不删行、不改原文验收标准 |

触发口令（发给「项目记录员」智能体）：
`/log` 变更日志 ｜ `/decide` 决策 ｜ `/bug` 踩坑 ｜ `/metric` 录入指标 ｜ `/final` 定稿数字 ｜ `/report 本周` 汇总成项目周报

一致性校验：每周至少运行一次 `python scripts/auto_log.py check`（建议在 git commit 前）。它会抓四类问题：FINAL 数字与对外口径不一致、schema.sql 与 models.py 表数不一致、DECISIONS 缺列、截图 orphan。

---

## 7. 协作纪律

- **一次只开一个智能体。** 别让同一个对话既当后端又当前端。对话超 20 轮就开新的，带上 CONTEXT.md 全文 + 最近改过的两个文件全文重新开场。
- 新对话开场格式固定：【上下文】+【角色锁定】+【当前进度】+【本次任务】+【相关文件全文】+【输出要求】。末尾必须加一句「只在我给的文件范围内改动」。
- 不确定先列选项让我选，不要替我决定。代码必须完整可运行并标注文件路径；改完输出：启动命令 / 需新增的环境变量 / curl 验证步骤。
- 遇到报错：先解释原因 → 再给修复方案 → 最后说明如何避免同类问题。
- **给的代码先跑，再往下问。跑不通就把完整报错原文贴回去，不要自己猜着改。**
- 每天结束时输出变更摘要（改动文件清单 + 每文件一句话 + 遗留问题 + 下一步），写入 CHANGELOG.md。
- 一切以 git 为真相来源：每天 `git commit`，能完整演示时 `git tag`。md 只是注释，代码才是正文。
- 不许编造数字；没有实测数据就用【待填】占位。
- 卡住时的处理顺序：①贴完整报错问原因/修复/预防 → ②让它缩小范围（只改某一段，给 diff 式说明）→ ③两轮修不好就**换策略不换目标**（如复杂方案搞不定先用最简单实现让链路通）→ ④超 2 小时没进展，记入 DECISIONS.md 并跳过，先做下一天任务。

---

## 8. 降级预案（兜底，非万不得已不启用）

触发条件：学院强制换技术栈 / 模型长期推不动 / 时间不够。
原则：**最大化复用已有资产**。数据库三张表结构与真实数据原样保留；接口路径与返回结构保持映射表不变，使前端尽量少改；只重写后端语言层或砍掉非核心功能。启用前先列出「保留/重写/可砍」清单与工期估算，经我确认再动。

---

## 9. 进度

进度表与当前状态已移至 `TODO.md`，本节仅作引用，避免总纲被动态内容污染。

---

## 10. V2 产品化修正案（2026-10-12 追加，仅在 product 分支生效）

> 本节是用户批准的产品化边界修正。**只追加本节，上文 v1 资产条款原文一字不改**；
> v1 相关条款继续约束 v1 资产（见 10.3 冻结条款）。

### 10.1 定位升级

V2 目标：从「v1 演示系统」升级为「可用的安全初筛产品」——
支持现代数据集、多格式输入、召回优先调优、告警与处置建议。

### 10.2 边界修正（覆盖 §0/PROMPT_GLOBAL_DIRECTOR 中"本期不做"清单的对应项）

| 原边界条款 | V2 修正 |
|---|---|
| 实时流式检测（本期不做） | **解禁为「近实时告警」**：批量检测完成后即时产出告警（t_alert + webhook 通知），非逐包 inline 拦截 |
| 只做离线文件检测 | 保留：仍以文件（CSV/PCAP）批量检测为主形态 |
| 处置能力（原来没有） | **新增「告警 + 处置建议」**：生成防火墙封禁命令供人工一键复制，**绝不自动执行** |
| 自动阻断 | **永久禁止**：误封正常业务/自身网络的风险不可控，不做 |
| 模型在线更新/自动重训练 | 仍不做（离线训练、人工换版本） |
| 多租户/SaaS、商业部署、移动端、商业用途 | 仍不做 |

### 10.3 v1 资产冻结条款（最高优先级，与 §0 并列）

在 product 分支上，以下资产**不改、不删、不引用其数字进 V2 对比口径以外的地方**：
- `docs/api.md`（接口文档）
- `docs/schema.sql`（数据库结构）
- `METRICS.md` 的 `## FINAL` 区块（v1 定稿数字，永不改）
- `backend/ml/model.pkl` + `backend/ml/features.json`（v1 模型，与 v2 共存不覆盖）
- `screenshots/`（项目配图）

V2 实验一律写入 `METRICS.md` 新增的 `## V2-PRODUCT 实验区`（只追加）。

### 10.4 白名单扩充（覆盖 §1）

- `backend/requirements.txt` 新增：`scapy>=2.5.0`（流特征提取，playground 已实测本机可用并转正）
- 其余一律不加：webhook 用 stdlib urllib、模型保持 sklearn 生态（不引 XGBoost/LightGBM，效果不足再议）
- parquet 仍不做（pyarrow 不加）

### 10.5 表结构变更（覆盖 §3 的确认流程）

V2 新增 `t_alert` 表：SQL 已于计划评审时经用户批准（见 .trae/documents/V2产品化改造计划.md 第五节），走 alembic 迁移，不碰 v1 三表。

### 10.6 记录规则

- CHANGELOG/DECISIONS/TODO/METRICS 记录规则照旧：只追加、坏结果也记、【待填】不编造
- METRICS：`## FINAL`（v1）与 `## V2-PRODUCT 实验区`（产品）分区，互不污染
- DECISIONS：V2 每个二选一决策照记（含放弃的选项与代价）

---

## 11. V3 零门槛修正案（2026-10-17 追加，仅在 v3 分支生效）

> 用户批准的 V3 改造边界修正（含授权修改本宪法）。**只追加本节，上文原文一字不改**；
> §10.3 v1 资产冻结条款在 v3 分支继续全部有效。

### 11.1 定位升级

V3 目标：从「要会准备文件的产品」升级为「普通人零门槛」——
一键体检（无文件输入）+ 管理员下发制（账号安全）。

### 11.2 边界修正（覆盖 §10.2 的对应项）

| 原边界条款 | V3 修正 |
|---|---|
| 「只做离线文件检测（保留：仍以文件 CSV/PCAP 批量检测为主形态）」 | **新增「一键体检」**：服务端在部署机本机定长窗口抓包（30/60/120 秒可选）→ 临时 pcap → 复用 V2 已验证的流特征提取与 v2 模型链路。上传检测保留，两条输入路径并存 |
| 逐包 inline 拦截 | 仍禁止：一键体检是「定长窗口事后判定」，不是实时拦截，边界声明不变 |
| 自动阻断 | 仍永久禁止（同 §10.2） |

一键体检诚实边界（产品页必须明示）：
- 抓的是**部署机**网卡流量：本机部署=检测本机；远程部署只能检测服务器自身，页面需如实提示
- 体检窗口内无流量时任务失败并给出明确提示（属正常场景，非故障）
- 流特征为降级子集、告警为初筛非阻断（同 V2 声明）

### 11.3 管理员下发制（新增条款）

- 注册接口**永久只能**创建 role=user 普通用户（现有行为，V3 固化为宪法条款）
- 管理员账号唯一来源：服务器本地 CLI 下发命令 `python scripts/create_admin.py`，生成 16 位随机强密码，仅在创建时显示一次
- 已存在的普通用户不得通过任何 Web 接口提权为 admin；提权仅能由机器主人在服务器上操作
- 登录失败锁定（防爆破）：V3 本期不做（决策见 DECISIONS.md 2026-10-17，留待下期）

### 11.4 表结构与依赖

- V3 不新增表、不改 v1 三表；一键体检复用 t_detection_task（file_name 以 `live_` 前缀标识来源）
- 依赖不新增：scapy 已在 §10.4 白名单转正

