"""异常检测服务。

封装 ML 模型调用与结果组装逻辑，供 results 路由调用。
当前阶段为 pass 级别空函数 + 签名 + docstring。
"""
from typing import Any


def detect_anomaly(records: list[dict], model_path: str | None = None) -> list[dict]:
    """对一批网络流量记录做异常检测。

    Args:
        records: 待检测的流量记录列表，每条是一个 dict
        model_path: 模型文件路径，默认走配置中的 MODEL_PATH
    Returns:
        每条记录对应的检测结果列表，包含 score 与 label
    """
    pass


def load_model(model_path: str) -> Any:
    """加载 ML 模型到内存。"""
    pass
