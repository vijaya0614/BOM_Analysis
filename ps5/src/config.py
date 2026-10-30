import os
from pathlib import Path
from typing import List
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENV: str = Field("dev", alias="ENVIRONMENT")
    DATA_DIR: Path = Field(Path("data"), alias="DATA_DIR")
    LOG_LEVEL: str = Field("INFO", alias="LOG_LEVEL")
    API_HOST: str = Field("0.0.0.0", alias="API_HOST")
    API_PORT: int = Field(8000, alias="API_PORT")
    CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ],
        alias="CORS_ORIGINS",
    )
    # Default to local SQLite database so the prototype works immediately without external services.
    # When PostgreSQL is provided in DATABASE_URL, the application will use PostgreSQL.
    DATABASE_URL: str = Field("sqlite:///./data/ps5.db", alias="DATABASE_URL")
    JWT_SECRET_KEY: str = Field("", alias="JWT_SECRET_KEY")
    JWT_DEMO_USER: str = Field("", alias="JWT_DEMO_USER")
    JWT_DEMO_PASSWORD: SecretStr = Field(SecretStr(""), alias="JWT_DEMO_PASSWORD")
    JWT_REVIEWER_PASSWORD: SecretStr = Field(SecretStr(""), alias="JWT_REVIEWER_PASSWORD")
    JWT_AUDITOR_PASSWORD: SecretStr = Field(SecretStr(""), alias="JWT_AUDITOR_PASSWORD")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    REDIS_URL: str = Field("redis://localhost:6379", alias="REDIS_URL")
    SENTRY_DSN: str = Field("", alias="SENTRY_DSN")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, origins: List[str]) -> List[str]:
        cleaned = [origin.strip().rstrip("/") for origin in origins if origin.strip()]
        if "*" in cleaned:
            raise ValueError("CORS_ORIGINS cannot contain '*'; credentials require explicit origins.")
        return cleaned


settings = Settings()
