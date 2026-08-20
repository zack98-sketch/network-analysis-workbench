import os
from pathlib import Path
from pydantic_settings import BaseSettings


def _resolve_base_dir() -> Path:
    """打包模式下从环境变量读取（run_standalone.py 注入）；开发模式下回退默认。"""
    env = os.environ.get("WORKBENCH_BASE_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent


def _resolve_data_dir() -> Path:
    """数据目录：打包模式放 exe 同级；开发模式放 backend/data。"""
    env = os.environ.get("WORKBENCH_DATA_DIR")
    if env:
        return Path(env)
    return _resolve_base_dir() / "data"


class Settings(BaseSettings):
    APP_NAME: str = "Network Analysis Workbench"
    APP_VERSION: str = "0.1.0"

    BASE_DIR: Path = _resolve_base_dir()
    DATA_DIR: Path = _resolve_data_dir()
    UPLOAD_DIR: Path = DATA_DIR / "uploads"
    EXPORT_DIR: Path = DATA_DIR / "exports"
    INDEX_DIR: Path = DATA_DIR / "index"

    DATABASE_URL: str = f"sqlite+aiosqlite:///{DATA_DIR / 'workbench.db'}"

    CORS_ORIGINS: list[str] = ["*"]

    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
settings.INDEX_DIR.mkdir(parents=True, exist_ok=True)
