"""Pydantic 请求/响应 schemas。

按业务模块分组组织，与 routers 一一对应。
当前阶段为空骨架，等业务字段稳定后填充。

示例结构（取消注释后使用）：

    from pydantic import BaseModel

    class Token(BaseModel):
        access_token: str
        token_type: str = "bearer"

    class TaskCreate(BaseModel):
        name: str
        source: str
"""
