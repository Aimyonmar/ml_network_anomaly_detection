"""文件 IO 工具。

封装上传文件落盘、读取、清理等操作。
当前阶段为 pass 级别空函数 + 签名 + docstring。
"""
from pathlib import Path


def save_upload(content: bytes, dest: Path) -> Path:
    """将上传内容写入目标路径，返回路径。"""
    pass


def read_lines(path: Path, encoding: str = "utf-8") -> list[str]:
    """按行读取文本文件，返回行列表。"""
    pass


def safe_remove(path: Path) -> bool:
    """安全删除文件，文件不存在返回 False。"""
    pass
