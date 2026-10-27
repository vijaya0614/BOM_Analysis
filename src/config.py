import os
from pathlib import Path
from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    ENV: str = Field("dev", env="ENVIRONMENT")
    DATA_DIR: Path = Field(Path("data"), env="DATA_DIR")
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    API_HOST: str = Field("0.0.0.0", env="API_HOST")
    API_PORT: int = Field(8000, env="API_PORT")
    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:3000"], env="CORS_ORIGINS")
    DATABASE_URL: str = Field("postgresql+asyncpg://postgres:postgres@localhost:5432/ps5", env="DATABASE_URL")
    JWT_SECRET_KEY: str = Field("", env="JWT_SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(60, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    REDIS_URL: str = Field("redis://localhost:6379", env="REDIS_URL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
