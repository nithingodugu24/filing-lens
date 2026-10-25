from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)
    database_url: str = "sqlite:///./data/filinglens.db"
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
    max_pdf_pages: int = Field(default=500, ge=1, le=1000)
    max_page_text_chars: int = Field(default=250000, ge=1000, le=2000000)
    max_document_text_chars: int = Field(default=10000000, ge=1000, le=50000000)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
