import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Network Analysis Workbench"
    APP_VERSION: str = "0.1.0"

    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
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
