from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)
    database_url: str = "sqlite:///./data/filinglens.db"
    app_env: str = "development"
    storage_dir: Path = Path("data/documents")
    embedding_provider: str = "local"
    embedding_model: str = "hash-v1"
    embedding_dimensions: int = Field(default=256, ge=32, le=2000)
    answer_provider: str = "extractive"
    answer_model: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    sentiment_enabled: bool = False
    ner_enabled: bool = False
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, ge=5, le=1440)
    provider_api_key: str = ""
    provider_base_url: str = "https://api.openai.com/v1"
    provider_timeout: float = 30
    provider_max_output_tokens: int = Field(default=2048, ge=256, le=8192)
    provider_reasoning_effort: str = ""
    input_cost_per_million: float | None = None
    output_cost_per_million: float | None = None
    max_upload_mb: int = Field(default=100, ge=1, le=100)
    max_pdf_pages: int = Field(default=750, ge=1, le=1000)
    max_page_text_chars: int = Field(default=250000, ge=1000, le=2000000)
    max_document_text_chars: int = Field(default=10000000, ge=1000, le=50000000)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    def validate_deployment(self):
        if self.app_env not in {"development", "test", "production"}:
            raise ValueError("APP_ENV must be development, test or production")
        if self.app_env != "production":
            return
        if (
            len(self.jwt_secret_key) < 48
            or len(set(self.jwt_secret_key)) < 12
            or self.jwt_algorithm != "HS256"
        ):
            raise ValueError(
                "Production requires a strong JWT_SECRET_KEY of at least 48 characters and HS256"
            )
        origins = [urlsplit(o.strip()) for o in self.cors_origins.split(",") if o.strip()]
        if not origins or any(
            o.scheme != "https"
            or not o.hostname
            or o.hostname in {"localhost", "127.0.0.1"}
            or "*" in o.netloc
            or o.path not in {"", "/"}
            for o in origins
        ):
            raise ValueError("Production requires explicit HTTPS CORS_ORIGINS for your application")
        if not self.database_url.startswith("postgresql") or "local-demo-password" in self.database_url:
            raise ValueError("Production requires PostgreSQL with a private database password")
        if self.answer_provider == "extractive" or not (
            self.provider_api_key
            if self.answer_provider == "openai"
            else self.gemini_api_key
            if self.answer_provider == "gemini"
            else ""
        ):
            raise ValueError("Production requires a configured AI answer service")
        if self.embedding_model == "hash-v1":
            raise ValueError("Production requires semantic embeddings rather than hash fixtures")


@lru_cache
def get_settings() -> Settings:
    return Settings()
