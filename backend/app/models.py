"""SQLAlchemy ORM 模型。

注意：auto_log.py check 会校验本文件中 `class Xxx(` 出现次数
与 docs/schema.sql 中 `CREATE TABLE` 出现次数一致。
新增表时两边同步。

当前阶段为骨架，不写具体模型类，等 D1 真正建表时再补。
"""
from sqlalchemy.orm import declarative_base

Base = declarative_base()
