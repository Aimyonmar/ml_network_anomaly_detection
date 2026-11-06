# 基于机器学习的网络异常检测系统

> 个人开源项目 | 网络流量异常检测 · 系统工程
> 一个「带智能检测模块的 Web 系统」：浏览器上传流量记录 CSV，后端调用机器学习模型逐条判定异常/攻击，前端以任务列表与可视化报告呈现结果。

**场景定位**：校园网旁路监测（管理员批量离线分析）+ 钓鱼 URL 自查（师生单次自助排查），两种模式共用同一套「上传 → 异步检测 → 轮询状态 → 报告可视化」链路。

---

## 界面预览

| 登录 / 注册 | 上传检测 | 任务列表（轮询） | 检测报告（三图） |
|---|---|---|---|
| ![登录页](screenshots/图6-1_登录页.png) | ![上传页](screenshots/图6-2_上传检测页.png) | ![任务列表](screenshots/图6-3_任务列表页.png) | ![报告页](screenshots/图6-4_检测报告页.png) |

报告页三张图：检测结果占比饼图、平均置信度对比柱图、置信度分布直方图，支撑人工复核排序。

---

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | Vue 3 + Vite + TypeScript + Element Plus + Pinia + Vue Router + ECharts |
| 后端 | FastAPI + Uvicorn + Pydantic v2 |
| 数据库 | MySQL 8.0（SQLAlchemy 2.0 同步 ORM + Alembic 迁移） |
| 认证 | JWT（python-jose）+ bcrypt 密码哈希 |
| 异步任务 | FastAPI BackgroundTasks（进程内任务 + 状态机轮询） |
| 检测模型 | scikit-learn 随机森林（二分类 Normal/Attack） |

---

## 核心特性

- **上传即秒回**：大文件流式落盘（边写边校验后缀/大小，≤50MB），立即返回 `task_id`，检测在后台异步执行，不阻塞请求。
- **任务状态机**：`pending → running → success/failed`，前端每 2 秒轮询刷新，失败原因字段级透出。
- **列序严格校验**：加载 `features.json` 特征契约，缺列/多列/乱序均抛精确到列位的错误，杜绝静默误判。
- **失败零残留**：异常路径回滚脏结果行、清理临时文件，不留 orphan。
- **越权防护**：任务/结果/统计三个读接口统一归属校验（非本人且非 admin 返回 403）。
- **安全存储**：密码仅存 bcrypt 不可逆哈希，令牌不入库；全链路参数化查询防注入。

---

## 实测指标

> 模型指标采用官方 KDDTest+ 跨数据集泛化口径（诚实口径，非同分布内插虚高值）。

| 指标 | 数值 |
|---|---|
| 准确率 Accuracy | 0.7691 |
| F1（Attack 类） | 0.7518 |
| ROC-AUC | 0.9600 |
| 批量推理吞吐 | 14,655 条/秒 |
| 基线对照（全猜多数类） | 0.5692 |
| 上传接口响应 | 0.043 ~ 0.063 s |
| 1 万行端到端检测 | 1.35 ~ 4.03 s |

同分布随机划分口径 Acc=0.9989 仅作泛化分析对照，不作为对外主指标。跨集攻击召回 61.4% 的漏报风险已在下方「已知局限」中如实声明。

---

## 快速开始

### 1. 环境准备

```bash
# Python 3.12.5，创建并激活虚拟环境
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/macOS

# 安装后端依赖
cd backend
pip install -r requirements.txt
```

### 2. 配置数据库

```bash
# 复制环境变量模板并按本机修改（DB_PASSWORD 等）
cp .env.example .env

# 建库（库名默认 anomaly_detection）
# MySQL 中执行：CREATE DATABASE anomaly_detection CHARACTER SET utf8mb4;

# 执行迁移，建三张表
alembic upgrade head
```

### 3. 训练检测模型（生成 model.pkl）

模型产物 `model.pkl` 与 NSL-KDD 数据集**不随仓库分发**，演示前需本地训练一次：

```bash
# 将 NSL-KDD 的 KDDTrain+.csv / KDDTest+.csv 放到 backend/ml/data/ 下
python -m ml.train --data ml/data/KDDTrain+.csv --test ml/data/KDDTest+.csv
# 产出 backend/ml/artifacts/model.pkl 与 backend/ml/features.json
```

### 4. 启动后端

```bash
# 仍在 backend/ 目录
uvicorn app.main:app --host 127.0.0.1 --port 8000
# 健康检查：curl http://127.0.0.1:8000/health → {"status":"ok"}
```

### 5. 启动前端

```bash
# 新开终端，项目根目录
cd frontend
npm install
npm run dev
# 浏览器访问 http://localhost:5173（Vite 代理 /api → 127.0.0.1:8000）
```

### 6. 演示动线

注册账号 → 登录 → 上传一份 1 万行 CSV（可用 `ml/data/KDDTest+.csv` 前 1 万行）→ 任务列表观察状态从"排队中"变"完成" → 进入报告页查看三张统计图。关掉后端时页面弹「无法连接后端服务」提示而非白屏。

---

## 接口概览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/auth/register` | 注册（用户名唯一，bcrypt 哈希入库） |
| POST | `/api/v1/auth/login` | 登录，返回 JWT |
| GET | `/api/v1/auth/me` | 当前用户信息 |
| POST | `/api/v1/tasks` | 上传 CSV 建检测任务（异步，秒回 task_id） |
| GET | `/api/v1/tasks` | 我的任务列表（分页） |
| GET | `/api/v1/tasks/{id}` | 任务详情（前端轮询 status） |
| GET | `/api/v1/tasks/{id}/results` | 检测结果分页 |
| GET | `/api/v1/tasks/{id}/stats` | 聚合统计（图表数据源） |
| GET | `/health` | 存活探针 |

统一返回结构 `{code, msg, data}`。完整请求/响应示例见 [`docs/api.md`](docs/api.md)。

---

## 项目结构

```
backend/
  app/
    main.py            # FastAPI 入口、路由注册、CORS
    config.py          # 环境变量配置
    database.py        # 同步 engine / SessionLocal
    models.py          # 三表 ORM（t_user / t_detection_task / t_detection_result）
    schemas.py         # Pydantic 请求/响应模型
    security.py        # bcrypt 哈希 + JWT 签发校验
    deps.py            # get_db / get_current_user
    routers/           # auth / tasks / results / admin / model_api
    services/          # detection.py（异步检测链路核心）
    utils/             # file_io.py（流式上传 + 失败清理）
  ml/                  # train.py / predict.py / features.json
  alembic/             # 数据库迁移
frontend/
  src/
    views/             # 登录注册 / 上传 / 任务列表 / 报告 四页
    api/               # axios 实例 + 拦截器（JWT/错误映射）
    stores/ router/    # Pinia 认证态 + 路由守卫
docs/
  schema.sql / api.md  # 数据库与接口文档
  diagrams/            # 系统设计图（架构 / 用例 / 时序 / E-R）
scripts/auto_log.py    # 记录一致性校验
```

---

## 已知局限（如实声明）

- **进程内任务模型**：BackgroundTasks 服务重启时 running 任务滞留、无自动恢复；并发压测实测上传 P95=1651ms，主因即队列积压抢占资源。生产应替换为 Celery + 消息队列。
- **二分类输出**：仅判定 Normal/Attack，`attack_type` 细分字段预留未填。
- **输入格式受限**：仅接受符合 NSL-KDD 41 列特征体系的 CSV（≤50MB）；.parquet 与原始 PCAP 报文不能直读。
- **跨集漏报**：攻击召回 61.4%，定位为旁路事后分析工具，不承诺实时拦截。

---

## 法律与合规注意事项

> 本节为公开仓库的必要声明，阅读或复用本项目前请先确认以下边界。

### 1. 开源协议

本仓库代码采用 [MIT License](LICENSE) 发布。选择理由：项目代码全部自研，依赖均为 MIT / BSD-3-Clause / Apache-2.0 等宽松许可，MIT 条款最短、与全部依赖兼容，且明确允许商业使用与修改再分发；本项目不含需专利授权或强传染性条款的组件，无需 Apache-2.0 的额外专利与 NOTICE 义务。协议覆盖**本仓库中的源代码与文档**，不覆盖数据集与第三方组件。

### 2. 数据集来源与引用要求

仓库**不包含**任何原始数据集（`backend/ml/data/` 已加入 `.gitignore`），需使用者自行从官方渠道获取并遵守其使用条款。

| 数据集 | 来源 | 引用要求 |
|---|---|---|
| NSL-KDD | 加拿大网络安全研究所（UNB CIC），源自 KDD Cup 1999，经 Tavallaee 等人修订去重 | 使用或发表结果时须引用：M. Tavallaee, E. Bagheri, W. Lu, A. A. Ghorbani, *"A Detailed Analysis of the KDD CUP 99 Data Set"*, IEEE CISDA, 2009；并注明数据来自 UNB CIC |
| CIC-IDS2017（`product` 分支） | 加拿大网络安全研究所（UNB CIC） | 须引用：I. Sharafaldin, A. H. Lashkari, A. A. Ghorbani, *"Toward Generating a New Intrusion Detection Dataset and Intrusion Traffic Characterization"*, ICISSP, 2018 |

- 上述数据集仅可用于研究、教学与评测，**不得将数据集本身再分发或用于商业用途**（具体以 UNB CIC 官方条款为准）。
- 数据集为公开采集的模拟/脱敏流量，不含真实受害者身份信息；使用者应自行确认其获取渠道合法。

### 3. 项目成果的知识产权归属

- 本仓库的源代码、文档与图表均由**项目作者本人创作并持有**，按 [MIT License](LICENSE) 授权使用；其中 `docs/`、`screenshots/` 等文档内容随代码一并授权，但作者保留署名权。
- 引用本项目或再分发时，请保留 `LICENSE` 与版权声明，并注明仓库地址。

### 4. 第三方代码与组件许可

- 仓库内**不含**第三方源码拷贝；依赖通过 `backend/requirements.txt` 与 `frontend/package.json` 声明、由包管理器安装。
- 主要依赖许可：FastAPI / Uvicorn / SQLAlchemy / Alembic / pandas 等（MIT 或 BSD-3-Clause）、scikit-learn（BSD-3-Clause）、bcrypt（Apache-2.0）、Vue / Vue Router / Pinia / Element Plus / Axios（MIT）、ECharts（Apache-2.0）。
- 上述许可均与 MIT 兼容，允许闭源商用；再分发时请保留各组件的版权与许可声明。

### 5. 免责声明与使用边界

- 本项目为**旁路事后分析工具**，仅用于对**合法获取、已获授权**的流量记录做离线检测与教学演示，**不承诺实时拦截能力**。
- **严禁**将本项目用于对任何未授权网络、主机或系统进行主动探测、扫描、入侵或攻击；由此产生的一切法律责任由使用者自行承担。
- 检测结果仅为统计意义上的异常提示，**不构成安全结论**，不得作为唯一处置依据。
- 仓库中的防火墙处置命令仅作人工参考，系统**永久禁用自动阻断**，必须由管理员核实后手工执行。
- 软件按 MIT 协议"按现状"提供，作者不对准确性、适用性或使用后果作任何明示或默示担保。

### 6. 隐私与数据合规

- 系统仅保存用户名、bcrypt 不可逆密码哈希、任务元数据与判定结果，不采集真实流量内容；JWT 不入库。
- 上传的 CSV 由使用者自行确保不含个人信息或涉密数据；如涉及个人信息处理，请遵守《个人信息保护法》《数据安全法》《网络安全法》及所在单位的保密规定。
- 仓库不包含任何真实密钥：`backend/.env` 已列入 `.gitignore`，仅提供占位模板 `backend/.env.example`。若发现泄露线索，请通过 Issue 联系维护者。

---

## 说明

- 本项目为个人开源项目，检测能力仅用于公开数据集（NSL-KDD）的离线分析与教学演示，**不对任何未授权网络发起主动探测**。
- 系统仅留存登录名、不可逆密码哈希与判定结果，令牌不入库。
- 依赖清单以 [`backend/requirements.txt`](backend/requirements.txt) 为白名单；开发全程记录见 [`CHANGELOG.md`](CHANGELOG.md)、技术决策见 [`DECISIONS.md`](DECISIONS.md)。
