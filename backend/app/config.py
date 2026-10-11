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

    # 上传（D5）。相对路径以 backend/ 为基准（cwd=backend 启动）
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_MB: int = 50  # CONTEXT.md §4：单文件 ≤ 50MB
    DETECTION_BATCH_SIZE: int = 2000  # 推理/写库分批大小，防大文件一次性占内存

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )


settings = Settings()
