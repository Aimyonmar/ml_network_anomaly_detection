# 项目上下文：基于机器学习的网络异常检测系统设计与实现

> 本文件是项目唯一总纲。每次开启新对话时，必须将全文粘贴在第一条消息中。
> 版本：v0.2 | Python 3.12.5 | 最后更新：2026-09-21

---

## 0. 定位（最高优先级，违反即视为设计错误）

本项目是**「带智能检测模块的 Web 系统」**，不是「一个检测模型」。
评审口径走软件工程「需求—设计—实现—测试」，模型只是 4.x 节中的一个模块。
设计文档篇幅分配：系统部分约 65% / 算法约 20% / 其他约 15%。

任何功能决策优先保证：**系统能跑通、链路完整、可演示**。宁可功能降级，不能让链路断掉。

---

## 1. 技术栈（锁定，不许擅自更换或新增）

- 语言：**Python 3.12.5**（全部依赖需兼容 3.12，安装前核对版本；scikit-learn 用 1.5+）
- Web：FastAPI + Uvicorn + Pydantic v2
- ORM：SQLAlchemy 2.0（async）+ Alembic
- DB：MySQL 8.0（utf8mb4），连接池由 SQLAlchemy 管理；驱动 pymysql + cryptography
- 认证：JWT（python-jose），密码 bcrypt（passlib[bcrypt]）
- 异步任务：**FastAPI BackgroundTasks**（第一版不用 Celery，除非我明确要求）
- 前端：Vue 3 + Vite + TypeScript + Element Plus + Axios + Pinia + Vue Router + ECharts
- ML：pandas + numpy + scikit-learn + joblib + matplotlib/seaborn（**只做 sklearn 生态**）
- 其他：python-multipart（文件上传，FastAPI 不自带，必须显式安装）、loguru、pytest
- 依赖清单：`backend/requirements.txt`（这是白名单：没写在里面的包不许引入）

依赖文件与本文必须一致：若本文写 SQLAlchemy 2.0，requirements.txt 里绝不能是 1.4.*。改一处同步另一处。

---

## 2. 目录结构（照这个建，不要自由发挥）