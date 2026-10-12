"""应用配置。

从环境变量读取，未设置时使用默认值。生产环境通过 .env 注入。
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # 应用
    APP_NAME: str = "ml_network_anomaly_detection"
    DEBUG: bool = False

    # 数据库
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "anomaly_detection"

    # 安全
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ML
    MODEL_PATH: str = "ml/artifacts/model.pkl"
    FEATURES_PATH: str = "ml/features.json"

    # ML V2（product 分支，CONTEXT.md §10）：双模型共存，MODEL_VERSION 切换
    MODEL_VERSION: str = "v1"  # v1=NSL-KDD 项目模型（冻结）；v2=CIC-IDS2017
    MODEL_PATH_V2: str = "ml/artifacts/model_v2.pkl"
    FEATURES_PATH_V2: str = "ml/features_cicids.json"
    MODEL_DECISION_THRESHOLD: float = 0.5  # Attack 判定阈值（v2 经 threshold_optimizer 调优后回填 .env）

    # V2 告警与处置建议（Gap 4）
    ALERT_CONFIDENCE_THRESHOLD: float = 0.90  # 置信度 ≥ 此值且 Attack 才生成告警
    ALERT_WEBHOOK_URL: str = ""               # 空=不外发；支持 generic / feishu 群机器人
    ALERT_WEBHOOK_TYPE: str = "generic"       # generic | feishu

    # 上传（D5）。相对路径以 backend/ 为基准（cwd=backend 启动）
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_MB: int = 50  # CONTEXT.md §4：单文件 ≤ 50MB
    DETECTION_BATCH_SIZE: int = 2000  # 推理/写库分批大小，防大文件一次性占内存

    @property
    def active_model_path(self) -> str:
        """按 MODEL_VERSION 解析当前生效模型路径（相对 backend/）。"""
        return self.MODEL_PATH if self.MODEL_VERSION == "v1" else self.MODEL_PATH_V2

    @property
    def active_features_path(self) -> str:
        """按 MODEL_VERSION 解析当前生效特征契约路径（相对 backend/）。"""
        return self.FEATURES_PATH if self.MODEL_VERSION == "v1" else self.FEATURES_PATH_V2

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )


settings = Settings()
