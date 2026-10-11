"""文件 IO 工具（D5）。

职责：
- 校验上传文件后缀（仅 .csv，决策见 DECISIONS.md 2026-10-11：parquet 需 pyarrow，
  不在 requirements.txt 白名单，D5 只支持 csv）
- 流式落盘（分块读写，不把整个文件读进内存），边写边累计字节数，超限立即清理
- 失败清理：任何异常路径下不留 orphan 文件（CONTEXT.md §3 约束）

约束：
- 单文件 ≤ settings.MAX_UPLOAD_MB（默认 50MB，CONTEXT.md §4）
- 落盘文件名用 uuid，防止原始文件名带来路径穿越/重名覆盖
"""
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import settings

CHUNK_SIZE = 1024 * 1024  # 1MB
ALLOWED_SUFFIXES = {".csv"}


class UploadValidationError(ValueError):
    """后缀/大小不合法时抛出，由路由层转成 4xx。"""


def validate_suffix(filename: str | None) -> str:
    """校验上传文件后缀，返回规范化小写后缀。不合法抛 UploadValidationError。"""
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise UploadValidationError(
            f"不支持的文件格式 {suffix or '(无后缀)'}，仅允许 {sorted(ALLOWED_SUFFIXES)}"
        )
    return suffix


def save_upload(upload: UploadFile, dest_dir: Path) -> Path:
    """流式保存上传文件到 dest_dir，返回最终路径。

    超限或写盘异常时自动删除半成品文件，绝不留 orphan。
    """
    suffix = validate_suffix(upload.filename)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid.uuid4().hex}{suffix}"

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    written = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = upload.file.read(CHUNK_SIZE)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise UploadValidationError(
                        f"文件超过大小限制 {settings.MAX_UPLOAD_MB}MB（已收到 {written} 字节）"
                    )
                out.write(chunk)
    except Exception:
        safe_remove(dest)
        raise
    if written == 0:
        safe_remove(dest)
        raise UploadValidationError("上传文件为空")
    return dest


def safe_remove(path: Path) -> bool:
    """安全删除文件，文件不存在或删除失败返回 False。"""
    try:
        path.unlink(missing_ok=True)
        return True
    except OSError:
        return False
