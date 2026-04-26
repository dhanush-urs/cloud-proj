from functools import lru_cache
from typing import Annotated, Any

from pydantic import BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "RepoBrain API"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # Railway injects PORT dynamically — respect it
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    DATABASE_URL: str = "postgresql+psycopg://repobrain:repobrain@postgres:5432/repobrain"
    REDIS_URL: str = "redis://redis:6379/0"

    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    GITHUB_TOKEN: str | None = None

    REPO_STORAGE_ROOT: str = "/data/repos"

    NEO4J_URI: str = "bolt://neo4j:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "repobrain123"

    # GitHub App
    GITHUB_APP_ID: str | None = None
    GITHUB_APP_PRIVATE_KEY: str | None = None
    GITHUB_WEBHOOK_SECRET: str | None = None

    # CORS — comma-separated list of allowed origins
    # Example for Railway: "https://your-frontend.up.railway.app,http://localhost:3000"
    CORS_ORIGINS: str = "http://localhost:3000"

    # Optional: explicit frontend URL (used for Railway CORS auto-config)
    FRONTEND_URL: str | None = None

    @property
    def cors_origins_list(self) -> list[str]:
        origins = set()
        if self.CORS_ORIGINS:
            if self.CORS_ORIGINS == "*":
                return ["*"]
            for o in self.CORS_ORIGINS.split(","):
                o = o.strip()
                if o:
                    origins.add(o)
        # Also include FRONTEND_URL if set
        if self.FRONTEND_URL:
            origins.add(self.FRONTEND_URL.rstrip("/"))
        return list(origins)

    # Provider selection
    LLM_PROVIDER: str = "gemini"           # gemini | none
    EMBEDDING_PROVIDER: str = "local"      # local | gemini

    # Gemini
    ENABLE_GEMINI: bool = False
    GEMINI_API_KEY: str | None = None
    GEMINI_CHAT_MODEL: str = "gemini-1.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "models/text-embedding-004"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()