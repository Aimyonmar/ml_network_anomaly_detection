"""模型训练脚本。

用法：python -m ml.train --config ml/features.json
当前阶段为空壳，仅声明函数签名与 docstring。
"""
from typing import Any


def load_dataset(path: str) -> Any:
    """加载训练数据集。

    Args:
        path: 数据集文件路径（csv/parquet）
    Returns:
        加载后的数据对象
    """
    pass


def train_model(features: list[str], dataset: Any) -> Any:
    """训练异常检测模型。

    Args:
        features: 训练用特征名列表（须与 features.json 中的 name 字段对齐）
        dataset: 已加载的数据集
    Returns:
        训练后的模型对象
    """
    pass


def save_model(model: Any, dest: str) -> None:
    """持久化模型到磁盘。

    Args:
        model: 训练后的模型对象
        dest: 模型文件保存路径
    """
    pass


if __name__ == "__main__":
    # CLI 入口占位
    pass
