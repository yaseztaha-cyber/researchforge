"""Central application configuration (env-driven, no secrets committed)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "ResearchForge"
    APP_VERSION: str = "0.1.0"
    ENV: str = os.getenv("ENV", "development")

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./researchforge.db")

    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "mock")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4o-mini")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "hash-384")
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "hash")

    SEARCH_PROVIDER: str = os.getenv("SEARCH_PROVIDER", "mock")
    SEARCH_API_KEY: str = os.getenv("SEARCH_API_KEY", "")
    SEARCH_API_URL: str = os.getenv("SEARCH_API_URL", "")

    MAX_SEARCH_ROUNDS: int = int(os.getenv("MAX_SEARCH_ROUNDS", "2"))
    MAX_SOURCES: int = int(os.getenv("MAX_SOURCES", "12"))
    MAX_RELEVANT_SOURCES: int = int(os.getenv("MAX_RELEVANT_SOURCES", "6"))
    MAX_COST_PER_RESEARCH: float = float(os.getenv("MAX_COST_PER_RESEARCH", "2.00"))
    RESEARCH_TIMEOUT_SECONDS: int = int(os.getenv("RESEARCH_TIMEOUT_SECONDS", "300"))

    MOCK_MODE: bool = os.getenv("MOCK_MODE", "true").lower() in ("1", "true", "yes")
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "15"))

    @property
    def is_postgres(self) -> bool:
        return self.DATABASE_URL.startswith("postgresql")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    def upload_path(self) -> Path:
        p = Path(self.UPLOAD_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
